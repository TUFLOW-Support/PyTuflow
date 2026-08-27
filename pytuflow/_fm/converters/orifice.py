import os
import typing
from collections import OrderedDict
from pathlib import Path

from .converter import Converter
from ..output import Output, OutputCollection
from ..helpers.tuflow_empty_files import tuflow_empty_field_map

if typing.TYPE_CHECKING:
    from ..parsers.units.handler import Handler


class Orifice(Converter):

    def __init__(self, unit: 'Handler' = None) -> None:
        super().__init__(unit)
        if unit:
            self.ecf = Output('CONTROL', unit.uid)
            self.nwk = Output('GIS', unit.uid)

    def convert(self) -> OutputCollection:
        out_col = OutputCollection()
        if self.unit.dns_units and self.unit.dns_units[0].type in ['CULVERT', 'CONDUIT']:
            return out_col
        out_col.append(self.get_nwk())
        out_col.append(self.get_ecf())
        return out_col

    def map_nwk_attributes(self, field_map: dict, unit: 'Handler') -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['ID'] = unit.uid
        d['Type'] = 'C' if unit.shape.upper() == 'CIRCULAR' else 'R'
        if unit.sub_type.upper() == 'FLAPPED':
            d['Type'] = f'{d["Type"]}U'
        d['Len_or_ANA'] = 0.01
        d['n_nf_Cd'] = 0.01
        d['US_Invert'] = unit.zinv
        d['DS_Invert'] = unit.zinv
        d['Number_of'] = 1
        height = unit.zsoff - unit.zinv
        d['Width_or_Dia'] = height if unit.shape.upper() == 'CIRCULAR' else unit.area / height
        d['Height_or_WF'] = height if unit.shape.upper() == 'RECTANGLE' else 0.
        d['HConF_or_WC'] = 0.6 if unit.shape.upper() == 'RECTANGLE' else 0.
        d['WConF_or_WEx'] = 0.9 if unit.shape.upper() == 'RECTANGLE' else 1.
        d['EntryC_or_WSa'] = 0.5
        d['ExitC_or_WSb'] = 1.0
        return d

    def get_nwk(self) -> Output:
        self.nwk.fpath, self.nwk.lyrname = self.output_gis_file('1d_nwk', 'ORIFICE')
        self.nwk.field_map = tuflow_empty_field_map('1d_nwk')
        self.nwk.geom_type = 2  # ogr.wkbLineString
        self.nwk.content.geom = self.channel_geom(self.unit)
        self.nwk.content.attributes = self.map_nwk_attributes(self.nwk.field_map, self.unit)
        return self.nwk

    def get_ecf(self) -> Output:
        self.ecf.fpath = self.settings.output_dir / f'{self.settings.outname}.ecf'
        self.ecf.content = 'Read GIS Network == {0}'.format(
            self.output_gis_ref(
                Path(os.path.relpath(self.nwk.fpath, self.ecf.fpath.parent)).as_posix(), self.nwk.lyrname
            )
        )
        return self.ecf
