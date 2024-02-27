import re
from pathlib import Path
from typing import Union

import pandas as pd

from .bc_tables_boundary import Boundary
from ..abc.time_series_result import TimeSeriesResult
from ..types import PathLike, TimeLike
from ..iterator_util import Iterator


class BCTables(TimeSeriesResult):

    def __init__(self, fpath: PathLike) -> None:
        self.boundary = None
        super().__init__(fpath)
        self.sim_id = re.sub(r'_[12]d_bc_tables_check', '', self.fpath.stem)

    def __repr__(self) -> str:
        if hasattr(self, 'fpath') and self.fpath:
            return f'<BCTables: {self.fpath.stem}>'
        return '<BCTables>'

    @staticmethod
    def looks_like_self(fpath: Path) -> bool:
        """Return True if the file looks like this class."""
        try:
            if not re.findall(r'_[12]d_bc_tables_check$', fpath.stem):
                return False
            with fpath.open() as f:
                line = f.readline()
                if not re.findall(r'^"?Generated by', line):
                    return False
        except Exception as e:
            return False
        return True

    def looks_empty(self, fpath: Path) -> bool:
        """Return True if the file looks empty."""
        try:
            with fpath.open() as f:
                for _ in range(3):
                    line = f.readline()
                if not re.findall(r'^BC\d{6}', line):
                    return True
        except Exception:
            return True
        return False

    def load(self) -> None:
        self.boundary = Boundary(self.fpath)
        if self.boundary.units:
            self.units = self.boundary.units

    def init_iterator(self, *args) -> Iterator:
        """Initialise the class iterator."""
        if args:
            return Iterator(*args)
        return Iterator(self.boundary)

    def result_types(self, id: Union[str, list[str]] = '', domain: str = '') -> list[str]:
        id = self._correct_id(id)  # need to convert cross-section names to their ids
        result_types = super().result_types(id, domain)
        return result_types

    def boundary_ids(self, boundary_type: Union[str, list[str]] = '') -> list[str]:
        if self.boundary:
            if not boundary_type:
                return self.boundary.ids(None)
            return self.ids(boundary_type, f'{self.boundary.domain} boundary')
        return []

    def time_series(self,
                    id: Union[str, list[str]],
                    result_type: Union[str, list[str]],
                    domain: str = None,
                    use_common_index: bool = True
                    ) -> pd.DataFrame:
        if not isinstance(id, list):
            id = [id] if id else []
        if not id:
            id = self.boundary_ids(None)
        id_ = id.copy()
        id = self._correct_id(id)
        correct_df_header = id_ != id
        df = super().time_series(id, result_type, domain, use_common_index)
        if correct_df_header:  # convert cross-section ids (e.g. 'XS00001') back to name (e.g. '1d_xs_C109')
            ids = [list(x) for x in df.columns.values.tolist()]
            for bcid in ids:
                name = self.boundary.bcid2name(bcid[2])
                if name in id_:
                    bcid[2] = name
            df.columns = pd.MultiIndex.from_tuples(ids, names=df.columns.names)

        return df

    def long_plot(self,
                  ids: Union[str, list[str]],
                  result_type: Union[str, list[str]],
                  time: TimeLike
                  ) -> pd.DataFrame:
        raise NotImplementedError('long_plot not available for BCTables.')

    def maximum(self, id: Union[str, list[str]], result_type: Union[str, list[str]], domain: str = '') -> pd.DataFrame:
        raise NotImplementedError('maximum not available for HydTables.')

    def _correct_id(self, id: Union[str, list[str]] = '') -> list[str]:
        """Convert cross-section names to their ids as they are stored in the 1d_ta_tables_check.csv file."""
        if not id:
            return []
        if not isinstance(id, list):
            id = [id]
        for i, id_ in enumerate(id):
            if id_.lower() in [x.lower() for x in self.boundary.ids(None)]:
                id[i] = self.boundary.name2bcid(id_)
        return id
