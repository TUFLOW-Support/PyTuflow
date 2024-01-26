from typing import TextIO

import numpy as np


class Unit:

    def __init__(self, fo: TextIO, fixed_field_len: int) -> None:
        self.df = None
        self.dx = None
        self._id = ''
        self._load(fo, fixed_field_len)

    @property
    def id(self) -> str:
        return ''

    def _load(self, fo: TextIO, fixed_field_len: int) -> None:
        pass

    def bed_level(self, *args, **kwargs) -> float:
        return np.nan
