from pathlib import Path
from typing import Union

import pandas as pd

from ..abc.time_series import TimeSeries


class TPCTimeSeries(TimeSeries):

    def __init__(self, fpath: Union[str, Path], index_col: str) -> None:
        super().__init__()
        self._index_col = index_col
        self.df = None
        self.fpath = Path(fpath)
        self.load()

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Time Series: {self.fpath.stem}>'
        return '<TPC Time Series>'

    def load(self):
        try:
            self.df = pd.read_csv(self.fpath, index_col=self._index_col, header=0, delimiter=',', na_values='**********')
        except Exception as e:
            raise f'Error loading CSV file: {e}'
