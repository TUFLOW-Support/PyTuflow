import re

from .bc_tables_boundary import Boundary
from ..abc.time_series_result import TimeSeriesResult
from ..types import PathLike


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
