from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from ..abc.maximums import Maximums


COLUMN_MAP = {'Hmax': 'Water Level Max', 'Emax': 'Energy Max', 'Time Hmax': 'Water Level TMax',
              'Qmax': 'Flow Max', 'Vmax': 'Velocity Max', 'Time Qmax': 'Flow TMax', 'Time Vmax': 'Velocity TMax'}


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
            with self.fpath.open() as f:
                ncol = len(f.readline().split(','))
            self.df = pd.read_csv(self.fpath, index_col=0, header=0, delimiter=',', na_values='**********', usecols=range(1,ncol))
            columns = {x: COLUMN_MAP.get(x, x) for x in self.df.columns}
            self.df.rename(columns=columns, inplace=True)
            if 'Energy Max' in self.df.columns:
                self.df['Energy TMax'] = [np.nan for x in range(len(self.df))]
        except Exception as e:
            raise Exception(f'Error loading TPC 1d_Nmx.csv file: {e}')

    def append(self, fpath: Union[str, Path]) -> None:
        try:
            df = pd.read_csv(fpath, index_col=1, header=0, delimiter=',', na_values='**********')
        except Exception as e:
            raise Exception(f'Error loading TPC 1d_Nmx.csv file: {e}')
        self.df = pd.concat([self.df, df], join="outer")
