import re
from typing import Union

from .bc_tables_boundary import Boundary
from ..abc.time_series_result import TimeSeriesResult
from ..types import PathLike
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
