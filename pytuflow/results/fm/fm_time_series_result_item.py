from datetime import datetime
from pathlib import Path
from typing import Union

from .fm_maximums import FMMaximums
from ..types import PathLike

import pandas as pd

from .fm_time_series import FMTimeSeries
from ..abc.time_series_result_item import TimeSeriesResultItem
from .dat import Dat
from .gxy import GXY


RESULT_SHORT_NAME = {'h': 'stage', 'water level': 'stage', 'q': 'flow', 'v': 'velocity', 'vel': 'velocity',
                     'f': 'froude', 'fr': 'froude', 's': 'state', 'm': 'mode'}


class FMResultItem(TimeSeriesResultItem):
    """A class for FM result items."""

    def __init__(self, fpath: PathLike, id_list: list[str], gxy: GXY, dat: Dat) -> None:
        self._ids = id_list
        self.gxy = gxy
        self.dat = dat
        self.maximums = FMMaximums()
        super().__init__(fpath)

    def count(self) -> int:
        return len(self._ids)

    def ids(self, result_type: Union[str, None]) -> list[str]:
        return self._ids

    def load_time_series(self, name: str, df: pd.DataFrame, reference_time: datetime, timesteps: list[float]) -> None:
        if name not in self.time_series or self.time_series[name].df.empty:
            self.time_series[name] = FMTimeSeries(name, df, reference_time, timesteps)
            self.maximums.append(name, self.time_series[name].df)

    def conv_result_type_name(self, result_type: str) -> str:
        return RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())
