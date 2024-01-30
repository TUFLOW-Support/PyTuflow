from os import PathLike

from .time_series_result_item import TimeSeriesResultItem


class RL(TimeSeriesResultItem):
    """Abstract base class for RL result item."""

    def __init__(self, fpath: PathLike) -> None:
        super().__init__(fpath)
        self.name = 'RL'
        self.domain = '0d'
        self.domain_2 = 'rl'
