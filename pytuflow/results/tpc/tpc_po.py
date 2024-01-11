from pathlib import Path
from typing import Union

import pandas as pd

from .tpc_time_series_result_item import TPCResultItem


class TPCPO(TPCResultItem):

    def __init__(self, fpath: Union[str, Path]) -> None:
        super().__init__(fpath)
        self._df = None

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Po: {self.fpath.stem}>'
        return '<TPC PO>'

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
