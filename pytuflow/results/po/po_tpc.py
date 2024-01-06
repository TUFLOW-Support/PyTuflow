import re

import pandas as pd

from ..abc.tpc_abc import TPCResultItem


class TPCPO(TPCResultItem):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Po: {self.fpath.stem}>'
        return '<TPC PO>'

    def load(self) -> None:
        pass

    def count(self) -> int:
        if self._df is None and self.time_series:
            self._create_df()
        return super().count()

    def ids(self, result_type: str) -> list[str]:
        if self._df is None and self.time_series:
            self._create_df()
        return super().ids(result_type)

    def _create_df(self) -> None:
        ids = []
        for ts in self.time_series.values():
            ids.extend([x for x in ts.df.columns if x.lower() not in [y.lower() for y in ids]])
        self._df = pd.DataFrame(ids, columns=['id'])
        self._df.set_index('id', inplace=True)
