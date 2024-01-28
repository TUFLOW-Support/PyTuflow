from datetime import datetime
from typing import Union


class TimeSeries:

    def __init__(self, *args, **kwargs) -> None:
        self.reference_time = None
        self.df = None

    def timesteps(self, dtype: str) -> list[Union[float, datetime]]:
        raise NotImplementedError
