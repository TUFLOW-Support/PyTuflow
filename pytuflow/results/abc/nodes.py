from ..types import PathLike

from .time_series_result_item import TimeSeriesResultItem


class Nodes(TimeSeriesResultItem):
    """Abstract base class for node result item."""

    def __init__(self, fpath: PathLike, *args, **kwargs) -> None:
        super().__init__(fpath)
        self.name = 'Node'
        self.domain = '1d'
        self.domain_2 = 'node'
