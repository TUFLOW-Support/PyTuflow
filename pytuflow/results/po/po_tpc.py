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
            ids.extend([self._po_name(x) for x in ts.df.columns[2:] if self._po_name(x) not in ids])
        self._df = pd.DataFrame(ids, columns=['id'])
        self._df.set_index('id', inplace=True)

    def _po_name(self, name: str) -> str:
        name = ' '.join(name.split(' ')[1:])
        name = re.sub(r'\[.*]', '', name).strip()
        return name
