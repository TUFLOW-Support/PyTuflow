from pathlib import Path
from typing import Union
from os import PathLike

import pandas as pd

from .tpc_time_series_result_item import TPCResultItem
from .tpc_maximums_po import TPCMaximumsPO
from ..abc.po import PO


class TPCPO_Base(TPCResultItem):

    def __init__(self, fpath: PathLike) -> None:
        super().__init__(fpath)
        self._df = None

    def load(self) -> None:
        pass

    @property
    def df(self):
        if self._df is None:
            self._create_df()
        return self._df

    @df.setter
    def df(self, value: pd.DataFrame) -> None:
        return

    def _create_df(self) -> None:
        ids = []
        for ts in self.time_series.values():
            ids.extend([x for x in ts.df.columns if x.lower() not in [y.lower() for y in ids]])
        self._df = pd.DataFrame(ids, columns=['id'])
        self._df.set_index('id', inplace=True)


class TPCPO(PO, TPCPO_Base):

    def __init__(self, fpath: PathLike) -> None:
        super(TPCPO, self).__init__(fpath)
        self._maximums = None

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Po: {self.fpath.stem}>'
        return '<TPC PO>'

    @property
    def maximums(self) -> TPCMaximumsPO:
        if self._maximums is None:
            self._maximums = TPCMaximumsPO(self)
        return self._maximums

    @maximums.setter
    def maximums(self, value: TPCMaximumsPO) -> None:
        return
