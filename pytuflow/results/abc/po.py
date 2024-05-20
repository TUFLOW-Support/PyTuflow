from pytuflow.types import PathLike

from .time_series_result_item import TimeSeriesResultItem


class PO(TimeSeriesResultItem):
    """Abstract base class for PO result item."""

    def __init__(self, fpath: PathLike) -> None:
        super().__init__(fpath)
        #: str: Name or Source of the result item. Always 'PO'.
        self.name = 'PO'
        #: str: Domain of the result item. Always '2d'.
        self.domain = '2d'
        #: str: Domain of the result item. Always 'po'.
        self.domain_2 = 'po'
