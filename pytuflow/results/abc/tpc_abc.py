import re
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

    def ids(self, result_type: str) -> list[str]:
        if self._df is None:
            return []
        if not result_type:
            return self._df.index.tolist()
        if result_type.lower() in self.time_series:
            return self._df_columns_to_ids(self.time_series[result_type.lower()].df)
        return []

    def result_types(self, id: str) -> list[str]:
        if not self.time_series:
            return []
        if not id:
            return list(self.time_series.keys())
        result_types = []
        for result_type, ts in self.time_series.items():
            if result_type not in result_types and id in [x.lower() for x in self._df_columns_to_ids(ts.df)]:
                result_types.append(result_type)
        return result_types

    def _df_columns_to_ids(self, df: pd.DataFrame) -> list[str]:
        return [self._name(x) for x in df.columns[2:]]

    def _name(self, name: str) -> str:
        name = ' '.join(name.split(' ')[1:])
        name = re.sub(r'\[.*]', '', name).strip()
        return name
