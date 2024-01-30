import io
from typing import TextIO, TYPE_CHECKING

import numpy as np
import pandas as pd

from ._unit import Unit
from ..unpack_fixed_field import unpack_fixed_field

if TYPE_CHECKING:
    from ..gxy import GXY
    from ..dat import Dat


SUB_UNIT_NAME = ''


class Interpolate(Unit):

    def __init__(self, fo: TextIO, fixed_field_len: int) -> None:
        self.headers = ['dx', 'easting', 'northing']
        super().__init__(fo, fixed_field_len)

    def __repr__(self) -> str:
        return f'<Interpolate {self._id}>'

    @property
    def id(self) -> str:
        return f'INTERPOLATE__{self._id}'

    @property
    def type(self) -> str:
        return 'Interpolate'

    def bed_level(self, dat: 'Dat', gxy: 'GXY', *args, **kwargs) -> float:
        if dat is not None and gxy is not None and self.id in gxy.node_df.index:
            ups_z, ups_dist, dns_z, dns_dist = None, None, None, None

            # upstream
            unit, ups_dist = self.upstream_defined(0, dat, gxy)
            if unit:
                ups_z = unit.bed_level(dat, gxy)

            # downstream
            unit, dns_dist = self.downstream_defined(self.dx, dat, gxy)
            if unit:
                dns_z = unit.bed_level(dat, gxy)

            if ups_z is not None and ups_dist is not None and dns_z is not None and dns_dist is not None:
                x = ups_dist
                xp = [0, ups_dist + dns_dist]
                fp = [ups_z, dns_z]
                return float(np.interp(x, xp, fp))

        return np.nan

    def upstream_defined(self, dist: float, dat: 'Dat', gxy: 'GXY', *args, **kwargs) -> tuple['Unit', float]:
        if dat is not None and gxy is not None and self.id in gxy.node_df.index:
            unit = self._upstream_unit(dat, gxy)
            if unit:
                dist += unit.dx
                return unit.upstream_defined(dist, dat, gxy)

    def downstream_defined(self, dist: float, dat: 'Dat', gxy: 'GXY', *args, **kwargs) -> tuple['Unit', float]:
        if dat is not None and gxy is not None and self.id in gxy.node_df.index:
            unit = self._downstream_unit(dat, gxy)
            dist += self.dx
            if unit:
                return unit.downstream_defined(dist, dat, gxy)

    def _load(self, fo, fixed_field_len: int) -> None:
        self._id = unpack_fixed_field(fo.readline(), [fixed_field_len]*3)[0].strip()
        data = io.StringIO(fo.readline())  # otherwise pandas will read an extra line when nrows=1 !!!
        self.df = pd.read_fwf(data, widths=[10]*2, names=self.headers[:2], nrows=1, header=None, skip_footer=0)
        self.dx = self.df['dx'].values[0]

    def _upstream_unit(self, dat: 'Dat', gxy: 'GXY') -> Unit:
        df = gxy.link_df[gxy.link_df['dns_node'] == self.id]
        df = df[df['ups_node'].str.contains(r'^RIVER_SECTION_|^REPLICATE|^INTERPOLATE')]
        if df.shape[0] > 0:
            return dat.unit(df['ups_node'].values[0])

    def _downstream_unit(self, dat: 'Dat', gxy: 'GXY') -> Unit:
        df = gxy.link_df[gxy.link_df['ups_node'] == self.id]
        df = df[df['dns_node'].str.contains(r'^RIVER_SECTION_|^REPLICATE|^INTERPOLATE')]
        if df.shape[0] > 0:
            return dat.unit(df['dns_node'].values[0])
