from datetime import datetime
from typing import Union
from ..types import TimeLike


class TimeSeries:

    def __init__(self, *args, **kwargs) -> None:
        self.reference_time = None
        self.df = None
        self.empty_results = []

    def timesteps(self, dtype: str) -> list[TimeLike]:
        raise NotImplementedError
