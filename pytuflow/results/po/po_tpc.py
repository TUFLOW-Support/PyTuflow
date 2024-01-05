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
        if not self._df and self.time_series:
            self._create_df()
        return super().count()

    def ids(self) -> list[str]:
        if not self._df and self.time_series:
            self._create_df()
        return super().ids()

    def _create_df(self) -> None:
        ids = []
        for ts in self.time_series.values():
            ids.extend([x for x in self._df_columns_to_ids(ts.df) if x not in ids])
        self._df = pd.DataFrame(ids, columns=['id'])
        self._df.set_index('id', inplace=True)
