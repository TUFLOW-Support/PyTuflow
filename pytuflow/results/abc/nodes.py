from ..types import PathLike

from .time_series_result_item import TimeSeriesResultItem


class Nodes(TimeSeriesResultItem):
    """Abstract base class for node result item."""

    def __init__(self, fpath: PathLike, *args, **kwargs) -> None:
        super().__init__(fpath)
        #: str: Name or Source of the result item. Always 'Node'.
        self.name = 'Node'
        #: str: Domain of the result item. Always '1d'.
        self.domain = '1d'
        #: str: Domain of the result item. Always 'node'.
        self.domain_2 = 'node'
