from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import pandas as pd
except ImportError:
    from .pymesh.stubs import pandas as pd

if TYPE_CHECKING:
    from sqlite3 import Cursor


class GPKGBase:

    def __init__(self, *args, **kwargs):
        self.fpath = None
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
        df = df.sort_values(['ID', 'time'])
        groupby = df.groupby('ID', sort=False)
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
            cur.execute(f'SELECT ID, Time_relative, "{dtype_name}" FROM "{table_name}";')
            df = pd.DataFrame(cur.fetchall(), columns=['ID', 'time', dtype_name])
            df = df.sort_values(['ID', 'time'])
        # df = df.pivot(index='time', columns='ID', values=dtype_name)
        df = fast_pivot(df, dtype_name)
        df.columns.name = None  # to be consistent with other outputs
        return df
