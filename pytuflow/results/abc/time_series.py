from datetime import datetime
from typing import Union


class TimeSeries:

    def __init__(self):
        self.reference_time = None

    def timesteps(self, dtype: str) -> list[Union[float, datetime]]:
        raise NotImplementedError
