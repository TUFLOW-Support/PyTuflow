from datetime import datetime
from pathlib import Path
from typing import Union

from .gpkg_time_series import GPKGTimeSeries
from .gpkg_ts_base import GPKGBase
from .gpkg_maximums import GPKGMaximums
from ..abc.time_series_result_item import TimeSeriesResultItem


class GPKGResultItem(GPKGBase, TimeSeriesResultItem):

    def __init__(self, fpath: Union[str, Path], layer_name: str) -> None:
        self._df = None
        self._layer_name = layer_name

        # properties
        self._count = None
        self._ids = None
        self._result_types = None
        self._time_series = None
        self._maximums = None

        super(GPKGResultItem, self).__init__(fpath)

    def load_time_series(self, name: str, id: str):
        self.time_series[name] = GPKGTimeSeries(self.fpath, id, self)

    def count(self) -> int:
        if self._count is None:
            try:
                self._open_db()
                self._cur.execute(
                    f'SELECT "Count" FROM "Timeseries_info" WHERE "Table_name" = "{self._layer_name}" LIMIT 1;'
                )
                ret = self._cur.fetchone()
                if ret:
                    self._count = int(ret[0])
                else:
                    self._count = 0
            except Exception as e:
                raise Exception(f'Error getting count: {e}')
            finally:
                self._close_db()
        return self._count

    def ids(self, result_type: Union[str, None]) -> list[str]:
        if self._ids is None:
            try:
                self._open_db()
                self._cur.execute(f'SELECT "ID" FROM "{self._layer_name}" LIMIT {self.count()};')
                ret = self._cur.fetchall()
                if ret:
                    self._ids = [x[0] for x in ret]
                else:
                    self._ids = []
            except Exception as e:
                raise Exception(f'Error getting IDs: {e}')
            finally:
                self._close_db()
        return self._ids

    def result_types(self, id: Union[str, None]) -> list[str]:
        if self._result_types is None:
            try:
                self._open_db()
                self._cur.execute(
                    f'SELECT "Series_Name" FROM "Timeseries_info" WHERE "Table_name" = "{self._layer_name}";'
                )
                ret = self._cur.fetchall()
                if ret:
                    self._result_types = [x[0] for x in ret]
                else:
                    self._result_types = []
            except Exception as e:
                raise Exception(f'Error getting result types: {e}')
            finally:
                self._close_db()
        return self._result_types

    def timesteps(self, dtype: str) -> list[Union[float, datetime]]:
        if not self.time_series:
            return []

        for ts in self.time_series.values():
            return ts.timesteps(dtype)

    @property
    def time_series(self) -> dict[str, GPKGTimeSeries]:
        if self._time_series is None:
            self._time_series = {}
            for result_type in self.result_types(None):
                self.load_time_series(result_type, result_type)
        return self._time_series

    @time_series.setter
    def time_series(self, value: dict[str, GPKGTimeSeries]) -> None:
        return

    @property
    def maximums(self) -> GPKGMaximums:
        if self._maximums is None:
            self._maximums = GPKGMaximums(self.fpath, self._layer_name, self)
        return self._maximums

    @maximums.setter
    def maximums(self, value: GPKGMaximums) -> None:
        return
