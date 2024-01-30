from pathlib import Path
from os import PathLike

import numpy as np
import pandas as pd

from ..abc.maximums import Maximums


COLUMN_MAP = {'Hmax': 'Water Level Max', 'Emax': 'Energy Max', 'Time Hmax': 'Water Level TMax',
              'Qmax': 'Flow Max', 'Vmax': 'Velocity Max', 'Time Qmax': 'Flow TMax', 'Time Vmax': 'Velocity TMax'}


class TPCMaximums(Maximums):

    def __init__(self, fpath: PathLike) -> None:
        super().__init__(fpath)
        self.fpath = Path(fpath)
        self.load()

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Maximum: {self.fpath.stem}>'
        return '<TPC Maximum>'

    def _load(self, fpath: PathLike) -> pd.DataFrame:
        fpath = Path(fpath)
        try:
            with self.fpath.open() as f:
                ncol = len(f.readline().split(','))
            df = pd.read_csv(fpath, index_col=0, header=0, delimiter=',', na_values='**********', usecols=range(1,ncol))
            columns = {x: COLUMN_MAP.get(x, x) for x in df.columns}
            df.rename(columns=columns, inplace=True)
            if 'Energy Max' in df.columns:
                df['Energy TMax'] = [np.nan for x in range(len(df))]
        except Exception as e:
            raise Exception(f'Error loading TPC 1d_Nmx.csv file: {e}')

        return df

    def load(self):
        self.df = self._load(self.fpath)

    def append(self, fpath: PathLike) -> None:
        df = self._load(fpath)
        self.df = pd.concat([self.df, df], join="outer")
