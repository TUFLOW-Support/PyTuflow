import io
import os
import typing
from collections import OrderedDict
from pathlib import Path

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from ..helpers.geometry import create_hw_table, Line, Point, get_right_angle_line, interpolate_hw_tables
from ..helpers.tuflow_empty_files import tuflow_empty_field_map
from .culvert_bend import CulvertBend
from .conduit import Conduit
from ..output import Output, OutputCollection


if typing.TYPE_CHECKING:
    from ..parsers.units.conduit import Conduit as ConduitHandler


class ConduitSymmetrical(Conduit):

    def __init__(self, unit: 'ConduitHandler' = None) -> None:
        super().__init__(unit)
        if unit:
            self.ecf = Output('CONTROL', unit.uid)
            self.nwk = Output('GIS', unit.uid)
            self.hw = Output('FILE', unit.uid)
            self.tab = Output('GIS', unit.uid)

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'CONDUIT_SECTION'

    def convert(self) -> OutputCollection:
        out_col = OutputCollection()
        if not self.unit or not self.dat or self.unit.dx == 0:
            return out_col
        if self.unit.dx > 0.:
            out_col.append(self.get_nwk())
            out_col.append(self.get_hw())
            out_col.append(self.get_tab())
            out_col.append(self.get_ecf())
        return out_col

    def map_nwk_attributes(self, field_map: dict, unit: 'ConduitHandler') -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['ID'] = unit.id
        d['Type'] = 'I'
        d['Len_or_ANA'] = unit.dx
        d['n_nf_Cd'] = 0.02  # hard-coded - unit uses ks and not sure how to convert to manning's n
        d['US_Invert'] = unit.bed_level
        d['DS_Invert'] = unit.dns_units[0].bed_level
        bend_loss = CulvertBend.bend_loss(unit)
        if not np.isnan(bend_loss):
            d['Form_Loss'] = bend_loss
        d['Number_of'] = 1
        d['HConF_or_WC'] = 0.6
        d['WConF_or_WEx'] = 0.9
        d['EntryC_or_WSa'] = 0.5
        d['ExitC_or_WSb'] = 1.0
        return d

    def map_tab_attributes(selfs, field_map: dict, unit: 'ConduitHandler', tab_fpath: Path, hw_fpath: Path) -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['Source'] = Path(os.path.relpath(hw_fpath, tab_fpath.parent)).as_posix()
        d['Type'] = 'HW'
        d['Column_1'] = 'h'
        d['Column_2'] = 'w'
        return d

    def get_hw(self) -> Output:
        self.hw.fpath = self.settings.output_dir / 'csv' / f'{self.unit.id}.csv'
        u1 = self.unit
        u2 = self.get_dns_unit(self.unit)
        hw1 = self.create_hw_from_sym_section(u1.section[['x', 'y']])
        hw2 = self.create_hw_from_sym_section(u2.section[['x', 'y']])
        self.hw.content = self.generate_hw_table(u1, u2, hw1, hw2)
        return self.hw

    def get_tab(self) -> Output:
        self.tab.fpath, self.tab.lyrname = self.output_gis_file('1d_hw', 'CONDUIT')
        self.tab.field_map = tuflow_empty_field_map('1d_tab')
        self.tab.geom_type = 2  # ogr.wkbLineString (gdal may not be installed)
        link_id = self.unit.dns_link_ids[0]
        line = Line.from_wkt(self.dat.link(link_id).wktgeom)
        point = Point.from_wkt(self.unit.wktgeom)
        self.tab.content.geom = self.mid_cross_section_geometry(self.unit)
        self.tab.content.attributes = self.map_tab_attributes(self.tab.field_map, self.unit, self.tab.fpath, self.hw.fpath)
        return self.tab

    def get_ecf(self) -> Output:
        self.ecf.fpath = self.settings.output_dir / f'{self.settings.outname}.ecf'
        nwk_cmd = 'Read GIS Network == {0}'.format(
            self.output_gis_ref(
                Path(os.path.relpath(self.nwk.fpath, self.ecf.fpath.parent)).as_posix(), self.nwk.lyrname
            )
        )
        tab_cmd = 'Read GIS Table Links == {0}'.format(
            self.output_gis_ref(
                Path(os.path.relpath(self.tab.fpath, self.ecf.fpath.parent)).as_posix(), self.tab.lyrname
            )
        )
        self.ecf.content = '\n'.join([nwk_cmd, tab_cmd])
        return self.ecf

    def create_hw_from_sym_section(self, section: pd.DataFrame) -> pd.DataFrame:
        hw = pd.concat([section, (section * [-1, 1])[::-1]], axis=0)
        return create_hw_table(hw, as_df=True)

    def get_weightings(self, unit1: 'Handler', unit2: 'Handler') -> tuple[float, float]:
        dns = unit1.dns_units[0]
        if dns.uid == unit2.uid:
            return 0.5, 0.5
        if dns.type == 'REPLICATE':
            return 1., 0.
        # must therefore be an INTERPOLATE
        # calculate interpolate section weightings
        d1 = unit1.dx
        d2 = self.dist_between_units(dns, self.get_dns_unit(dns))
        w1_ = d1 / (d1 + d2)
        w2_ = d2 / (d1 + d2)

        # upstream section is 50% + 50% of it's influence on the INTERPOLATE section
        w1 = 0.5 + 0.5 * w1_
        w2 = 1. - w1  # should equal 0.5 * w2_
        assert np.isclose(w2, 0.5 * w2_)
        return w1, w2

    def generate_hw_table(self, unit1: 'Handler', unit2: 'Handler', hw1: pd.DataFrame, hw2: pd.DataFrame) -> str:
        w1, w2 = self.get_weightings(unit1, unit2)
        hw = interpolate_hw_tables(hw1, hw2, [w1, w2], as_df=True)
        buf = io.StringIO()
        buf.write(
            f'! Generated by fm_to_estry. Source: {self.dat.name}/{self.unit.uid}. '
            f'HW interpolated from {unit1.id} ({w1 * 100:.0f}%) {unit2.id} ({w2 * 100:.0f}%).\n'
        )
        hw.to_csv(buf, index=False, lineterminator='\n', float_format='%.3f')
        return buf.getvalue()
