from typing import TextIO, TYPE_CHECKING
import io

import numpy as np
import pandas as pd

from ._unit import Unit
from ..unpack_fixed_field import unpack_fixed_field

if TYPE_CHECKING:
    from ..gxy import GXY
    from ..dat import Dat


SUB_UNIT_NAME = ''


class Replicate(Unit):

    def __init__(self, fo: TextIO, fixed_field_len: int) -> None:
        self.headers = ['dx', 'dz'  'easting', 'northing']
        super().__init__(fo, fixed_field_len)

    def __repr__(self) -> str:
        return f'<Replicate {self._id}>'

    @property
    def id(self) -> str:
        return f'REPLICATE__{self._id}'

    @property
    def type(self) -> str:
        return 'Replicate'

    def bed_level(self, dat: 'Dat', gxy: 'GXY', *args, **kwargs) -> float:
        if dat is not None and gxy is not None and self.id in gxy.node_df.index:
            df = gxy.link_df[gxy.link_df['dns_node'] == self.id]
            df = df[df['ups_node'].str.startswith('RIVER_SECTION_')]
            if df.shape[0] > 0:
                unit = dat.unit(df['ups_node'].values[0])
                if unit:
                    return unit.bed_level(dat, gxy) - df.loc[0, 'dz']
        return np.nan

    def upstream_defined(self, dist: float, *args, **kwargs) -> tuple['Unit', float]:
        return self, dist

    def downstream_defined(self, dist: float, *args, **kwargs) -> tuple['Unit', float]:
        return self, dist

    def _load(self, fo: TextIO, fixed_field_len: int) -> None:
        self._id = unpack_fixed_field(fo.readline(), [fixed_field_len] * 3)[0].strip()
        data = io.StringIO(fo.readline())  # otherwise pandas will read an extra line when nrows=1 !!!
        self.df = pd.read_fwf(data, widths=[10] * 4, names=self.headers, nrows=1, header=None)
        self.dx = self.df['dx'].values[0]
