from datetime import datetime
from pathlib import Path
from typing import Union

import pandas as pd


class TimeSeriesResultItem:

    def __init__(self, fpath: Union[str, Path]) -> None:
        self.df = None
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

    def get_time_series(self, id: list[str], result_type: list[str]) -> pd.DataFrame:
        df = pd.DataFrame()
        for rt in result_type:
            if rt in self.time_series:
                alias_ids = [f'{rt}::{x}' for x in id]
                df_ = self.time_series[rt].df[id].rename(columns={x: y for x, y in zip(id, alias_ids)})
                if df.empty:
                    df = df_
                else:
                    df = pd.concat([df, df_], axis=1)
        return df

    def get_maximum(self, id: list[str], result_type: list[str]) -> pd.DataFrame:
        return self.maximums.df.loc[id, result_type]

    def val(self, result_type: str, ids: list[str], timestep_index: int) -> pd.DataFrame:
        result_type_ = self.conv_result_type_name(result_type)
        if result_type_ in self.time_series:
            time = self.time_series[result_type_].df.index[timestep_index]
            return self.time_series[result_type].df[ids].iloc[timestep_index].to_frame().rename(
                columns={time: result_type})
        return pd.DataFrame([], columns=result_type)

    @staticmethod
    def conv_result_type_name(result_type: str) -> str:
        raise NotImplementedError

    @staticmethod
    def result_type_to_max(result_type: str) -> str:
        raise NotImplementedError

    @staticmethod
    def result_type_to_tmax(result_type: str) -> str:
        raise NotImplementedError
