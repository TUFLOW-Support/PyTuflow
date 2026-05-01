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

_VALID_IDENTIFIER = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_\s\\-]*$")

def _safe_identifier(name: str) -> str:
    if not _VALID_IDENTIFIER.match(name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    return '"' + name.replace('"', '""') + '"'


class GPKGBase:

    def __init__(self, *args, **kwargs):
        self._cached = {}  # 'table_name': pd.DataFrame
        self._group_cached = {}  # 'table_name': df.groupby
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

    def _read_gpkg_table_to_memory(self, cur: 'Cursor', data_types: list[str], table_name):
        """Read a table from a GPKG/sqlite3 database into memory in one I/O operation."""
        cols = ['ID', 'Time_relative'] + [f'"{x}"' for x in data_types]
        query = 'SELECT {0} FROM "{1}"'.format(','.join(cols), table_name)
        df = pd.read_sql_query(query, cur.connection)
        df = df.rename(columns={'Time_relative': 'time'})

        # do some post-processing to make the data easier to work with
        df = df.sort_values(['ID', 'time'])

        # ensure there are no duplicated columns
        df = df.loc[:, ~df.columns.duplicated()]

        groupby = df.groupby('ID', sort=False)

        # cache data
        self._cached[table_name] = df
        self._group_cached[table_name] = groupby

    def _gpkg_time_series_extractor(self, cur: 'Cursor', dtype_name: str, table_name: str) -> pd.DataFrame:
        """Extract the time series data from a TUFLOW GeoPackage Time Series file for
        a given data type from a given table.
        """
        def fast_pivot(df, dtype_name):
            result = []
            col_names = []

            if table_name in self._group_cached:
                groupby = self._group_cached[table_name]
            else:
                groupby = df.groupby('ID', sort=False)

            for id_val, group in groupby:
                s = group.set_index('time')[dtype_name]
                result.append(s)
                col_names.append(id_val)

            out = pd.concat(result, axis=1)
            out.columns = col_names

            return out

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
