from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import pandas as pd
except ImportError:
    from .pymesh.stubs import pandas as pd

if TYPE_CHECKING:
    from sqlite3 import Cursor

import re
import sqlite3

_VALID_IDENTIFIER = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\s\\-]*$")

def _safe_identifier(name: str) -> str:
    if not _VALID_IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    return '"' + name.replace('"', '""') + '"'


class GPKGBase:

    def __init__(self, *args, **kwargs):
        self._cached = {}  # 'table_name': pd.DataFrame
        self._group_cached = {}  # 'table_name': df.groupby
        self._wide = {}  # 'table_name': (time index, id index, [time, id, dtype] array, dtypes)
        super().__init__(*args, **kwargs)

    @staticmethod
    @contextmanager
    def connect(fpath: str | Path):
        import sqlite3
        conn = None
        try:
            conn = sqlite3.connect(fpath)
            yield conn
        finally:
            if conn is not None:
                conn.close()

    @staticmethod
    def _looks_empty(fpath: str | Path) -> bool:
        # docstring inherited
        import sqlite3
        try:
            with GPKGBase.connect(fpath) as conn:
                cur = conn.cursor()
                cur.execute('SELECT DISTINCT Table_name, Count FROM Timeseries_info;')
                count = sum([int(x[1]) for x in cur.fetchall()])
                empty = count == 0
        except sqlite3.Error:
            empty = True
        return empty

    @staticmethod
    def _resolve_base_tables(cur: 'Cursor', table_name: str) -> tuple[str, str, str, str] | None:
        """Work out the base tables behind a TUFLOW time series view.

        Returns (dataset_table, dataset_fid_col, feature_table, feature_fid_col) or None if the
        view doesn't have the expected layout.
        """
        row = cur.execute("SELECT sql FROM sqlite_master WHERE type = 'view' AND name = ?;", (table_name,)).fetchone()
        if not row or not row[0]:
            return None
        sql = row[0]
        m = re.search(r'FROM\s+(\w+)\s+LEFT JOIN\s+(\w+)\s+ON\s+\1\.(\w+)\s*=\s*\2\.fid\b', sql, re.I)
        if not m or 'DatasetTimes' not in sql:
            return None
        return m.group(1), m.group(3), m.group(2), 'fid'

    def _read_base_tables_fast(self, cur: 'Cursor', data_types: list[str], table_name: str) -> 'tuple | None':
        """Read the time series straight from the base tables into a dense numpy array, avoiding the
        slow pandas row conversion. Returns (time index, ID index, array) or None if this isn't possible (e.g. non-numeric or NULL data).
        """
        import itertools
        import numpy as np
        try:
            base = self._resolve_base_tables(cur, table_name)
            if base is None:
                return None
            ds_tbl, ds_fid, ft_tbl, ft_fid = (_safe_identifier(x) for x in base)
            cols = ', '.join(_safe_identifier(x) for x in data_types)
            n = cur.execute(f'SELECT COUNT(*) FROM {ds_tbl};').fetchone()[0]  # nosec B608
            ncols = 2 + len(data_types)
            rows = cur.execute(f'SELECT {ds_fid}, TimeId, {cols} FROM {ds_tbl};')  # nosec B608
            arr = np.fromiter(itertools.chain.from_iterable(rows), dtype=np.float64, count=n * ncols)
            arr = arr.reshape(n, ncols)
            ids = pd.read_sql_query(f'SELECT {ft_fid} AS fid, ID FROM {ft_tbl};', cur.connection)  # nosec B608
            times = pd.read_sql_query('SELECT TimeId, Time_relative FROM DatasetTimes;', cur.connection)
        except (TypeError, ValueError, KeyError, IndexError, ImportError, sqlite3.Error):
            return None
        # build a dense [time, id, data type] array once so each data type is just a slice
        try:
            feat_idx = pd.Index(ids['fid']).get_indexer(arr[:, 0].astype(np.int64))
            time_idx = pd.Index(times['TimeId']).get_indexer(arr[:, 1].astype(np.int64))
            if (feat_idx < 0).any() or (time_idx < 0).any():
                return None
            uid, id_inv = np.unique(ids['ID'].to_numpy(dtype=object), return_inverse=True)
            utime, time_inv = np.unique(times['Time_relative'].to_numpy(dtype=np.float64), return_inverse=True)
            rows, cols = time_inv[time_idx], id_inv[feat_idx]
            if len(utime) * len(uid) > 4 * max(n, 1):  # too ragged for a dense array
                return None
            flat = rows * len(uid) + cols
            if len(np.unique(flat)) != n:  # duplicate (ID, time) pairs
                return None
            cube = np.full((len(utime), len(uid), len(data_types)), np.nan)
            cube[rows, cols, :] = arr[:, 2:]
        except (TypeError, ValueError):
            return None
        return pd.Index(utime, name='time'), pd.Index(uid), cube

    def _read_gpkg_table_to_memory(self, cur: 'Cursor', data_types: list[str], table_name):
        """Read a table from a GPKG/sqlite3 database into memory in one I/O operation."""
        data_types = list(dict.fromkeys(data_types))  # unique, order preserved
        fast = self._read_base_tables_fast(cur, data_types, table_name)
        if fast is not None:
            self._wide[table_name] = (fast[0], fast[1], fast[2], data_types)
            return

        # fallback to the generic (slower) route
        cols = ['ID', 'Time_relative'] + [_safe_identifier(x) for x in data_types]
        query = 'SELECT {0} FROM {1}'.format(','.join(cols), _safe_identifier(table_name))  # nosec B608
        df = pd.read_sql_query(query, cur.connection)  # nosec B608
        df = df.rename(columns={'Time_relative': 'time'})

        # do some post-processing to make the data easier to work with
        df = df.sort_values(['ID', 'time'])

        # ensure there are no duplicated columns
        df = df.loc[:, ~df.columns.duplicated()]

        # cache data
        self._cached[table_name] = df
        self._group_cached[table_name] = df.groupby('ID', sort=False)

    def _gpkg_time_series_extractor(self, cur: 'Cursor', dtype_name: str, table_name: str) -> pd.DataFrame:
        """Extract the time series data from a TUFLOW GeoPackage Time Series file for
        a given data type from a given table.
        """
        def fast_pivot(df, dtype_name):
            try:
                out = df.pivot(index='time', columns='ID', values=dtype_name)
            except ValueError:  # duplicate (ID, time) pairs
                out = None
            if out is not None:
                return out.rename_axis(columns=None)

            result = []
            col_names = []
            groupby = self._group_cached.get(table_name) if table_name in self._cached else None
            if groupby is None:
                groupby = df.groupby('ID', sort=False)
            for id_val, group in groupby:
                result.append(group.set_index('time')[dtype_name])
                col_names.append(id_val)
            out = pd.concat(result, axis=1)
            out.columns = col_names
            return out

        if table_name in self._wide and dtype_name in self._wide[table_name][3]:
            times, ids, cube, dtypes = self._wide[table_name]
            return pd.DataFrame(cube[:, :, dtypes.index(dtype_name)], index=times, columns=ids)

        if table_name in self._cached:
            df = self._cached[table_name][['ID', 'time', dtype_name]]
        else:
            col_quoted = _safe_identifier(dtype_name)
            tbl_quoted = _safe_identifier(table_name)
            sql = f'SELECT ID, Time_relative, {col_quoted} FROM {tbl_quoted};'  # nosec B608
            df = pd.read_sql_query(sql, cur.connection)
            df = df.rename(columns={'Time_relative': 'time'})
            df = df.sort_values(['ID', 'time'])
            df = df.loc[:, ~df.columns.duplicated()]

        df = fast_pivot(df, dtype_name)
        df.columns.name = None  # to be consistent with other outputs
        return df
