from datetime import datetime

import pandas as pd

from ..abc.time_series import TimeSeries


class FMTimeSeries(TimeSeries):

    def __init__(self, name: str, df: pd.DataFrame, reference_time: datetime) -> None:
        super().__init__()
        self.reference_time = reference_time
        self._name = name
        self._load(df)

    def _load(self, df: pd.DataFrame) -> None:
        self.df = df.iloc[:, df.columns.str.contains(rf'^{self._name}::')]
        self.df.columns = self.df.columns.map(lambda x: x.split('::')[-1])
