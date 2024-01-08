from pathlib import Path
from typing import Union

import pandas as pd

from ..abc.maximums import Maximums


class TPCMaximums(Maximums):

    def __init__(self, fpath: Union[str, Path]) -> None:
        super().__init__(fpath)
        self.fpath = Path(fpath)
        self.load()

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Maximum: {self.fpath.stem}>'
        return '<TPC Maximum>'

    def load(self):
        try:
            self.df = pd.read_csv(self.fpath, index_col=1, header=0, delimiter=',', na_values='**********')
        except Exception as e:
            raise Exception(f'Error loading TPC 1d_Nmx.csv file: {e}')

    def append(self, fpath: Union[str, Path]) -> None:
        try:
            df = pd.read_csv(fpath, index_col=1, header=0, delimiter=',', na_values='**********')
        except Exception as e:
            raise Exception(f'Error loading TPC 1d_Nmx.csv file: {e}')
        self.df = pd.concat([self.df, df], join="outer")
