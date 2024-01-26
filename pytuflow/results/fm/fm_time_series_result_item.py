from pathlib import Path
from typing import Union

from ..abc.time_series_result_item import TimeSeriesResultItem
from .dat import Dat
from .gxy import GXY


RESULT_SHORT_NAME = {'h': 'stage', 'water level': 'stage', 'q': 'flow', 'v': 'velocity', 'vel': 'velocity',
                     'f': 'froude', 'fr': 'froude', 's': 'state', 'm': 'mode'}


class FMResultItem(TimeSeriesResultItem):
    """A class for FM result items."""

    def __init__(self, fpath: Union[str, Path], id_list: list[str], gxy: GXY, dat: Dat) -> None:
        self._ids = id_list
        self.gxy = gxy
        self.dat = dat
        super().__init__(fpath)

    def count(self) -> int:
        return len(self._ids)

    def ids(self, result_type: Union[str, None]) -> list[str]:
        return self._ids

    @staticmethod
    def conv_result_type_name(result_type: str) -> str:
        return RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())
