from typing import TextIO

import pandas as pd

from ._unit import Unit
from ..unpack_fixed_field import unpack_fixed_field


class Interpolate(Unit):

    def __init__(self, fo: TextIO, fixed_field_len: int) -> None:
        self.headers = ['dx', 'easting', 'northing']
        super().__init__(fo, fixed_field_len)

    def __repr__(self) -> str:
        return f'<Interpolate {self._id}>'

    @property
    def id(self) -> str:
        return f'INTERPOLATE__{self._id}'

    def _load(self, fo, fixed_field_len: int) -> None:
        self._id = unpack_fixed_field(fo.readline(), [fixed_field_len]*3)[0].strip()
        self.df = pd.read_fwf(fo, widths=[10]*3, names=self.headers, nrows=1)
        self.dx = self.df['dx'].values[0]
