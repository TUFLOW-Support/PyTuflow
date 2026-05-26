import os
import typing
from collections import OrderedDict
from pathlib import Path

from .converter import Converter
from ..output import Output, OutputCollection
from ..helpers.geometry import Line, Point
from ..helpers.tuflow_empty_files import tuflow_empty_field_map

if typing.TYPE_CHECKING:
    from ..parsers.units.handler import Handler


class Weir(Converter):

    def __init__(self, unit: 'Handler' = None) -> None:
        super().__init__(unit)
        if unit:
            self.ecf = Output('CONTROL', unit.uid)
            self.qh = Output('FILE', unit.uid)
            self.nwk = Output('GIS', unit.uid)
            self.tab = Output('GIS', unit.uid)
            self.xs = Output('FILE', unit.uid)

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'WEIR_'

    def convert(self) -> OutputCollection:
        out_col = OutputCollection()
        if self.has_qh():
            out_col.append(self.get_qh())
        out_col.append(self.get_nwk())
        if self.has_xs():
            out_col.append(self.get_xs())
            out_col.append(self.get_tab())
        out_col.append(self.get_ecf())
        return out_col

    def has_xs(self) -> bool:
        return False

    def has_qh(self) -> bool:
        return False

    def map_nwk_attributes(self, field_map: dict, unit: 'Handler') -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['Type'] = 'WW'
        d['ID'] = unit.uid
        if hasattr(unit, 'zc'):
            d['US_Invert'] = unit.zc
            d['DS_Invert'] = unit.zc
        if hasattr(unit, 'b'):
            d['Width_or_Dia'] = unit.b
        if self.has_qh():
            d['Inlet_Type'] = Path(os.path.relpath(self.qh.fpath, self.nwk.fpath.parent)).as_posix()
        if self.unit.type == 'WEIR':
            d['Height_or_WF'] = unit.cv
            d['HConF_or_WC'] = unit.cd
            d['WConF_or_Wex'] = unit.e
        return d

    def map_tab_attributes(self, field_map: dict, unit: 'Handler') -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['Source'] = Path(os.path.relpath(self.xs.fpath, self.tab.fpath.parent)).as_posix()
        d['Type'] = 'XZ'
        d['Column_1'] = 'x'
        d['Column_2'] = 'y'
        return d

    def get_qh(self) -> Output:
        self.qh.fpath = self.settings.output_dir / 'csv' / f'{self.unit.uid}.csv'
        return self.qh

    def get_nwk(self) -> Output:
        self.nwk.fpath, self.nwk.lyrname = self.output_gis_file('1d_nwk', 'WEIR')
        self.nwk.field_map = tuflow_empty_field_map('1d_nwk')
        self.nwk.geom_type = 2  # ogr.wkbLineString
        self.nwk.content.geom = self.channel_geom(self.unit)
        self.nwk.content.attributes = self.map_nwk_attributes(self.nwk.field_map, self.unit)
        return self.nwk

    def get_xs(self) -> Output:
        self.xs.fpath = self.settings.output_dir / 'csv' / f'{self.unit.uid}.csv'
        return self.xs

    def get_tab(self) -> Output:
        self.tab.fpath, self.tab.lyrname = self.output_gis_file('1d_xs', 'WEIR')
        self.tab.field_map = tuflow_empty_field_map('1d_tab')
        self.tab.geom_type = 2  # ogr.wkbLineString (gdal may not be installed)
        self.tab.content.geom = self.mid_cross_section_geometry(self.unit)
        self.tab.content.attributes = self.map_tab_attributes(self.tab.field_map, self.unit)
        return self.tab

    def get_ecf(self) -> Output:
        self.ecf.fpath = self.settings.output_dir / f'{self.settings.outname}.ecf'
        self.ecf.content = 'Read GIS Network == {0}'.format(
            self.output_gis_ref(
                Path(os.path.relpath(self.nwk.fpath, self.ecf.fpath.parent)).as_posix(), self.nwk.lyrname
            )
        )
        if self.has_xs():
            self.ecf.content = '{0}\nRead GIS Table Links == {1}'.format(
                self.ecf.content,
                self.output_gis_ref(
                    Path(os.path.relpath(self.tab.fpath, self.ecf.fpath.parent)).as_posix(), self.tab.lyrname
                )
            )
        return self.ecf
