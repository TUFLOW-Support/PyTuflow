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

    def us_invert(self, *args, **kwargs) -> float:
        return self.bed_level(*args, **kwargs)

    def ds_invert(self, *args, **kwargs) -> float:
        return self.bed_level(*args, **kwargs)

    def upstream_defined(self, *args, **kwargs) -> tuple['Unit', float]:
        pass

    def downstream_defined(self, *args, **kwargs) -> tuple['Unit', float]:
        pass
