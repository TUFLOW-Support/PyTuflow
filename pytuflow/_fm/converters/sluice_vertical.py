import os
import typing
from collections import OrderedDict
from pathlib import Path

from .converter import Converter
from ..output import Output, OutputCollection
from ..helpers.tuflow_empty_files import tuflow_empty_field_map

if typing.TYPE_CHECKING:
    from ..parsers.units.sluice import Sluice as SluiceHandler


class SluiceVertical(Converter):

    def __init__(self, unit: 'SluiceHandler' = None) -> None:
        super().__init__(unit)
        if unit:
            self.ecf = Output('CONTROL', unit.uid)
            self.nwk = Output('GIS', unit.uid)

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'SLUICE_VERTICAL'

    def convert(self) -> OutputCollection:
        out_col = OutputCollection()
        out_col.append(self.get_nwk())
        out_col.append(self.get_ecf())
        return out_col

    def map_nwk_attributes(self, field_map: dict, unit: 'SluiceHandler') -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['ID'] = unit.uid
        d['TYPE'] = 'SGWB'
        d['US_Invert'] = unit.zc
        d['DS_Invert'] = unit.zc
        d['Width_or_Dia'] = unit.b
        d['Height_or_WF'] = unit.gates[0].gate_operation['Opening'].iloc[0]
        d['Number_of'] = unit.ngates
        return d

    def get_nwk(self) -> Output:
        self.nwk.fpath, self.nwk.lyrname = self.output_gis_file('1d_nwk', 'SLUICE')
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
