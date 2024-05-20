import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Union
from pytuflow.types import PathLike, TimeLike

import pandas as pd

from ..abc.time_series import TimeSeries


class TPCTimeSeriesCSV(TimeSeries):
    """TPC Time Series class for storing CSV format results."""

    def __init__(self, fpath: PathLike, reference_time: datetime, index_col: Union[str, int], loss_type: str = '') -> None:
        super().__init__()
        self._index_col = index_col
        self.fpath = Path(fpath)
        self.reference_time = reference_time
        #: str: Loss type - can be one of 'Entry', 'Additional', or 'Exit' (default is '').
        self.loss_type = loss_type
        self.load()

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Time Series (CSV): {self.fpath.stem}>'
        return '<TPC Time Series (CSV)>'

    def load(self):
        try:
            with self.fpath.open() as f:
                ncol = len(f.readline().split(','))
            df = pd.read_csv(
                self.fpath,
                index_col=self._index_col-1,
                header=0,
                delimiter=',',
                na_values='**********',
                usecols=range(1,ncol)
            )
            if self.loss_type:
                df = df[df.columns[df.columns.str.contains(self.loss_type)]]
                df.rename(columns={x: x.replace(self.loss_type, '').strip() for x in df.columns}, inplace=True)
            df.rename(columns={x: self._name(x) for x in df.columns}, inplace=True)
            self.df = df
        except Exception as e:
            raise Exception(f'Error loading CSV file: {e}')

    def timesteps(self, dtype: str) -> list[TimeLike]:
        if dtype == 'absolute':
            return [self.reference_time + timedelta(hours=x) for x in self.df.index]
        return self.df.index.tolist()

    def _name(self, name: str) -> str:
        name = ' '.join(name.split(' ')[1:])
        name = re.sub(r'\[.*]', '', name).strip()
        return name
