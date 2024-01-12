from pathlib import Path
from typing import Union

from .time_series_result_item import TimeSeriesResultItem


class PO(TimeSeriesResultItem):
    """Abstract base class for PO result item."""

    def __init__(self, fpath: Union[str, Path]) -> None:
        super().__init__(fpath)
        self.name = 'PO'
        self.domain = '2d'
        self.domain_2 = 'po'
