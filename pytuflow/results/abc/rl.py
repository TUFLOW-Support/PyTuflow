from pytuflow.types import PathLike

from .time_series_result_item import TimeSeriesResultItem


class RL(TimeSeriesResultItem):
    """Abstract base class for RL result item."""

    def __init__(self, fpath: PathLike) -> None:
        super().__init__(fpath)
        #: str: Name or Source of the result item. Always 'RL'.
        self.name = 'RL'
        #: str: Domain of the result item. Always '0d'.
        self.domain = '0d'
        #: str: Domain of the result item. Always 'rl'.
        self.domain_2 = 'rl'
