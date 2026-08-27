import io
import os
import typing
from pathlib import Path

import numpy as np

from .replicate import Replicate
from ..helpers.geometry import interpolate_hw_tables, Line, Point, get_right_angle_line
from ..output import OutputCollection, Output


if typing.TYPE_CHECKING:
    from ..parsers.units.handler import Handler


class Interpolate(Replicate):

    def __init__(self, unit: 'Handler' = None, *args, **kwargs) -> None:
        super().__init__(unit, *args, **kwargs)
        if unit:
            self.nwk = Output('GIS', unit.uid)
            self.tab = Output('GIS', unit.uid)
            self.hw = Output('FILE', unit.uid)
            self.ecf = Output('CONTROL', unit.uid)
        self._ups_unit = None
        self._dns_unit = None
        self._w1 = np.nan  # ups weighting
        self._w2 = np.nan  # dns weighting

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'INTERPOLATE_'

    def convert(self) -> OutputCollection:
        out_col = OutputCollection()
        self.get_interp_properties()
        if self.unit.dx > 0:
            ups_conv = self._ups_unit.convert()
            dns_conv = self._dns_unit.convert()
            out_col.append(self.get_nwk(ups_conv.find_output('1d_nwk')))
            if self._ups_unit.type == 'CONDUIT':
                out_col.append(self.get_hw(ups_conv.find_output('csv', 'FILE'), dns_conv.find_output('csv', 'FILE')))
                out_col.append(self.get_tab(ups_conv.find_output('1d_hw')))
            out_col.append(ups_conv.find_output('ecf'))
        return out_col

    def get_nwk(self, nwk: Output) -> Output:
        nwk.content.geom = self.channel_geom(self.unit)
        nwk.content.attributes['ID'] = self.unit.id
        if self._ups_unit.type == 'CONDUIT':
            nwk.content.attributes['US_Invert'] = self.unit.bed_level
            nwk.content.attributes['DS_Invert'] = self.unit.dns_units[0].bed_level
        return nwk

    def get_hw(self, hw1: Output, hw2: Output) -> Output:
        self.hw.fpath = self.settings.output_dir / 'csv' / f'{self.unit.id}.csv'
        ahw1 = np.loadtxt(io.StringIO(hw1.content), delimiter=',', skiprows=2)
        ahw2 = np.loadtxt(io.StringIO(hw2.content), delimiter=',', skiprows=2)
        hw = interpolate_hw_tables(ahw1, ahw2, [self._w1, self._w2], as_df=True)
        buf = io.StringIO()
        hw.to_csv(buf, index=False, lineterminator='\n', float_format='%.3f')
        self.hw.content = buf.getvalue()
        return self.hw

    def get_tab(self, tab: Output) -> Output:
        link_id = self.unit.dns_link_ids[0]
        line = Line.from_wkt(self.dat.link(link_id).wktgeom)
        point = Point.from_wkt(self.unit.wktgeom)
        tab.content.geom = get_right_angle_line(line, point, self.settings.xs_gis_length, True).to_wkt()
        tab.content.attributes['Source'] = Path(os.path.relpath(self.hw.fpath, tab.fpath.parent)).as_posix()
        return tab

    def get_interp_properties(self) -> None:
        self._ups_unit = self.first_ups_not_interp(self.unit)
        if self._ups_unit.type == 'REPLICATE':
            self._ups_unit = self.replicate_ups_unit(self._ups_unit)
        ups_dx = self.dist_between_units(self._ups_unit, self.unit)
        self._dns_unit = self.first_dns_not_interp(self.unit)
        dns_dx = self.dist_between_units(self.unit, self._dns_unit)
        self._w1 = ups_dx / (ups_dx + dns_dx)
        self._w2 = dns_dx / (ups_dx + dns_dx)

    def first_ups_not_interp(self, unit: 'Handler') -> 'Handler':
        ups_unit = unit.ups_units[0]
        while ups_unit.type == 'INTERPOLATE':
            ups_unit = ups_unit.ups_units[0]
        return ups_unit

    def first_dns_not_interp(self, unit: 'Handler') -> 'Handler':
        dns_unit = unit.dns_units[0]
        while dns_unit.type == 'INTERPOLATE':
            dns_unit = dns_unit.dns_units[0]
        return dns_unit
