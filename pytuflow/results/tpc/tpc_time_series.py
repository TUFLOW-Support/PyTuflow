import re
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
            with self.fpath.open() as f:
                ncol = len(f.readline().split(','))
            self.df = pd.read_csv(
                self.fpath,
                index_col=self._index_col-1,
                header=0,
                delimiter=',',
                na_values='**********',
                usecols=range(1,ncol)
            )
            self.df.rename(columns={x: self._name(x) for x in self.df.columns}, inplace=True)
        except Exception as e:
            raise f'Error loading CSV file: {e}'

    def _name(self, name: str) -> str:
        name = ' '.join(name.split(' ')[1:])
        name = re.sub(r'\[.*]', '', name).strip()
        return name
