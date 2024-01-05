from pathlib import Path
from typing import Union


class TimeSeriesResultItem:

    def __init__(self, fpath: Union[str, Path]) -> None:
        self.fpath = fpath
        self.maximums = None
        self.time_series = {}
        self.load()

    def load(self) -> None:
        raise NotImplementedError

    def load_time_series(self, *args, **kwargs):
        raise NotImplementedError