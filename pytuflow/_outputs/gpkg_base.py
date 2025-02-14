from contextlib import contextmanager
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from sqlite3 import Cursor


class GPKGBase:

    @contextmanager
    def _connect(self):
        import sqlite3
        conn = None
        try:
            conn = sqlite3.connect(self.fpath)
            yield conn
        finally:
            if conn is not None:
                conn.close()

    def _gpkg_time_series_extractor(self, cur: 'Cursor', dtype_name: str, table_name: str) -> pd.DataFrame:
        """Extract the time series data from a TUFLOW GeoPackage Time Series file for
        a given data type from a given table.
        """
        cur.execute(f'SELECT ID, Time_relative, "{dtype_name}" FROM "{table_name}";')
        df = pd.DataFrame(cur.fetchall(), columns=['ID', 'time', dtype_name])
        df = df.pivot(index='time', columns='ID', values=dtype_name)
        df.columns.name = None  # to be consistent with other outputs
        return df
