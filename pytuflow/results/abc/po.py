from ..types import PathLike

from .time_series_result_item import TimeSeriesResultItem


class PO(TimeSeriesResultItem):
    """Abstract base class for PO result item."""

    def __init__(self, fpath: PathLike) -> None:
        super().__init__(fpath)
        self.name = 'PO'
        self.domain = '2d'
        self.domain_2 = 'po'
