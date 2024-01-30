from datetime import datetime
from pathlib import Path
from typing import Union, TYPE_CHECKING
from ..types import PathLike

import numpy as np
import pandas as pd

from ..abc.time_series import TimeSeries
from .gpkg_ts_base import GPKGBase

if TYPE_CHECKING:
    from .gpkg_time_series_result_item import GPKGResultItem


class GPKGTimeSeries(GPKGBase, TimeSeries):

    def __init__(self, fpath: PathLike, id: str, parent: 'GPKGResultItem') -> None:
        super(GPKGTimeSeries, self).__init__()
        self.fpath = Path(fpath)
        self._df = None
        self._parent = parent
        self._id = id  # result type id
        self._timesteps_rel = None
        self._timesteps_abs = None

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<GPKG TS Time Series: {self.fpath.stem}>'
        return '<GPKG TS Time Series>'

    def load(self) -> None:
        pass

    def timesteps(self, dtype: str) -> list[Union[float, datetime]]:
        if self._timesteps_rel is None:
            try:
                self._open_db()
                self._cur.execute(f'SELECT "Time_relative", "Datetime" FROM "DatasetTimes";')
                ret = self._cur.fetchall()
                if ret:
                    self._timesteps_rel = [float(x[0]) for x in ret]
                    self._timesteps_abs = [datetime.strptime(x[1], '%Y-%m-%dT%H:%M:%SZ') for x in ret]
                else:
                    self._timesteps_abs = []
                    self._timesteps_rel = []
            except Exception as e:
                raise Exception(f'Error getting timesteps: {e}')
            finally:
                self._close_db()
        if dtype == 'absolute':
            return self._timesteps_abs
        return self._timesteps_rel

    @property
    def df(self):
        if self._df is None:
            try:
                ids = ' OR "ID" = '.join([f'"{x}"' for x in self._parent.ids(None)])
                self._open_db()
                self._cur.execute(f'SELECT "ID", "{self._id}" FROM "{self._parent._layer_name}" WHERE "ID" = {ids};')
                ret = self._cur.fetchall()
                d = {x: [] for x in self._parent.ids(None)}
                if ret:
                    for row in ret:
                        try:
                            d[row[0]].append(float(row[1]))
                        except ValueError:
                            d[row[0]].append(np.nan)
                    self._df = pd.DataFrame(d)
                    self._df['Time (h)'] = self.timesteps('relative')
                    self._df.set_index('Time (h)', inplace=True)
                else:
                    self._df = pd.DataFrame([], columns=self._parent.ids(None))
            except Exception as e:
                raise Exception(f'Error getting dataframe: {e}')
            finally:
                self._close_db()
        return self._df

    @df.setter
    def df(self, value: pd.DataFrame) -> None:
        return
