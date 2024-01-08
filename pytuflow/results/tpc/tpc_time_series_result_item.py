from datetime import datetime
from pathlib import Path
from typing import Union

import pandas as pd

from .tpc_time_series_csv import TPCTimeSeriesCSV
from .tpc_time_series_nc import TPCTimeSeriesNC
from ..abc.time_series_result_item import TimeSeriesResultItem


RESULT_SHORT_NAME = {'h': 'water level', 'q': 'flow', 'v': 'velocity', 'e': 'energy', 'vol': 'volume',
                     'mb': 'mass balance error', 'qa': 'flow area', 'nf': 'node regime', 'cf': 'channel regime',
                     'loss': 'channel losse', 'losses': 'channel losse', 'l': 'channel losse', 'cl': 'channel losse'}


class TPCResultItem(TimeSeriesResultItem):

    def __init__(self, fpath: Union[str, Path]) -> None:
        self._df = None
        self.nc = None
        super().__init__(fpath)

    def load_time_series(self, name: str, fpath: Union[str, Path], reference_time: datetime, index_col=None, id: str = '') -> None:
        if self.nc is not None:
            self.time_series[name] = TPCTimeSeriesNC(self.nc, id)
        else:
            self.time_series[name] = TPCTimeSeriesCSV(fpath, reference_time, index_col)

    def count(self) -> int:
        if self._df is None:
            return 0
        return self._df.shape[0]

    def ids(self, result_type: Union[str, None]) -> list[str]:
        if result_type is not None:
            result_type = RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())
        if self._df is None:
            return []
        if not result_type:
            return self._df.index.tolist()
        if result_type.lower() in self.time_series:
            return self.time_series[result_type.lower()].df.columns.tolist()
        return []

    def result_types(self, id: Union[str, None]) -> list[str]:
        if not self.time_series:
            return []
        if not id:
            return list(self.time_series.keys())
        result_types = []
        for result_type, ts in self.time_series.items():
            if result_type not in result_types and id in [x.lower() for x in ts.df.columns]:
                result_types.append(result_type)
        return result_types

    def timesteps(self, dtype: str) -> list[Union[float, datetime]]:
        if not self.time_series:
            return []

        for ts in self.time_series.values():
            return ts.timesteps(dtype)

    def val(self, result_type: str, ids: list[str], timestep_index: int) -> pd.DataFrame:
        result_type_ = RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())
        if result_type_ in self.time_series:
            time = self.time_series[result_type_].df.index[timestep_index]
            return self.time_series[result_type].df[ids].iloc[timestep_index].to_frame().rename(columns={time: result_type})
        return pd.DataFrame([], columns=result_type)

    @staticmethod
    def conv_result_type_name(result_type: str) -> str:
        return RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())
