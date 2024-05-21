from datetime import datetime, timedelta
from typing import Union

import pandas as pd

from ..abc.time_series import TimeSeries
from pytuflow.types import TimeLike


class FMTimeSeries(TimeSeries):
    """Class to handle individual Flood Modeller result time series data. e.g. Flow."""

    def __init__(self, name: str, df: pd.DataFrame, reference_time: datetime, timesteps: list[float]) -> None:
        """
        Parameters
        ----------
        name : str
            Name of the result type.
        df : pd.DataFrame
            DataFrame containing the time series data.
        reference_time : datetime
            Reference time.
        timesteps : list[float]
            List of relative timesteps.
        """
        super().__init__()
        self.reference_time = reference_time
        self._timesteps = timesteps
        self._name = name
        self._load(df)

    def _load(self, df: pd.DataFrame) -> None:
        self.df = df.iloc[:, df.columns.str.contains(rf'^{self._name}::')]
        self.df.columns = self.df.columns.map(lambda x: x.split('::')[-1])

    def timesteps(self, dtype: str) -> list[TimeLike]:
        # docstring inherited
        if dtype == 'absolute':
            return [self.reference_time + timedelta(hours=x) for x in self._timesteps]
        return self._timesteps
