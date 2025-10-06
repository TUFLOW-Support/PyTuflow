from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from sqlite3 import Cursor


class GPKGBase:

    def __init__(self, *args, **kwargs):
        self.fpath = None
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
    def _gpkg_time_series_extractor(cur: 'Cursor', dtype_name: str, table_name: str) -> pd.DataFrame:
        """Extract the time series data from a TUFLOW GeoPackage Time Series file for
        a given data type from a given table.
        """
        cur.execute(f'SELECT ID, Time_relative, "{dtype_name}" FROM "{table_name}";')
        df = pd.DataFrame(cur.fetchall(), columns=['ID', 'time', dtype_name])
        df = df.pivot(index='time', columns='ID', values=dtype_name)
        df.columns.name = None  # to be consistent with other outputs
        return df
