from pathlib import Path
from typing import Union

import pandas as pd

from ..time_series.time_series_tpc import TPCTimeSeries
from .time_series_result_item import TimeSeriesResultItem


class TPCResultItem(TimeSeriesResultItem):

    def __init__(self, fpath: Union[str, Path]) -> None:
        self._df = None
        super().__init__(fpath)

    def load_time_series(self, name: str, fpath: Union[str, Path], index_col=None) -> None:
        self.time_series[name] = TPCTimeSeries(fpath, index_col)

    def count(self) -> int:
        if self._df is None:
            return 0
        return self._df.shape[0]

    def ids(self) -> list[str]:
        if self._df is None:
            return []
        return self._df.index.tolist()

    def result_types(self) -> list[str]:
        if not self.time_series:
            return []
        return list(self.time_series.keys())
