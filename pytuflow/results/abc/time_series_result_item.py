from datetime import datetime
from pathlib import Path
from typing import Union

import pandas as pd


class TimeSeriesResultItem:

    def __init__(self, fpath: Union[str, Path]) -> None:
        self.fpath = fpath
        self.maximums = None
        self.time_series = {}
        self.load()

    def load(self) -> None:
        raise NotImplementedError

    def load_time_series(self, *args, **kwargs):
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    def ids(self, result_type: Union[str, None]) -> list[str]:
        raise NotImplementedError

    def result_types(self, id: Union[str, None]) -> list[str]:
        raise NotImplementedError

    def timesteps(self, dtype: str) -> list[Union[float, datetime]]:
        raise NotImplementedError

    def get_time_series(self, id: str, result_type: str) -> pd.DataFrame:
        raise NotImplementedError

    def val(self, result_type: str, ids: list[str], timestep_index: int) -> pd.DataFrame:
        raise NotImplementedError

    @staticmethod
    def conv_result_type_name(result_type: str) -> str:
        raise NotImplementedError
