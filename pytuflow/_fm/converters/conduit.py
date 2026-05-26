import os
import typing
from pathlib import Path

from ..helpers.scanner import Scanner, ScanRule
from .converter import Converter
from ..output import Output
from ..helpers.tuflow_empty_files import tuflow_empty_field_map

if typing.TYPE_CHECKING:
    from ..parsers.units.conduit import Conduit as ConduitHandler
    from ..parsers.units.handler import Handler


class Conduit(Converter):

    def __init__(self, unit: 'ConduitHandler' = None) -> None:
        super().__init__(unit)
        self.unit = unit

    def get_nwk(self) -> Output:
        self.nwk.fpath, self.nwk.lyrname = self.output_gis_file('1d_nwk', 'CONDUIT')
        self.nwk.field_map = tuflow_empty_field_map('1d_nwk')
        self.nwk.geom_type = 2  # ogr.wkbLineString (gdal may not be installed)
        self.nwk.content.geom = self.channel_geom(self.unit)
        self.nwk.content.attributes = self.map_nwk_attributes(self.nwk.field_map, self.unit)
        return self.nwk

    def get_ecf(self) -> Output:
        self.ecf.fpath = self.settings.output_dir / f'{self.settings.outname}.ecf'
        nwk_cmd = 'Read GIS Network == {0}'.format(
            self.output_gis_ref(
                Path(os.path.relpath(self.nwk.fpath, self.ecf.fpath.parent)).as_posix(), self.nwk.lyrname
            )
        )
        self.ecf.content = nwk_cmd
        return self.ecf

    def get_ups_node(self, unit: 'Handler', consider_self: bool) -> 'Handler':
        nd = super().get_ups_node(unit, consider_self)
        if nd.type in ['CULVERT', 'ORIFICE'] and nd.sub_type.upper() != 'BEND':
            if nd.ups_units and nd.ups_units[0].type == 'JUNCTION':
                return self._consider_ups_junction(nd, unit)
            else:
                return nd.ups_units[0] if nd.ups_units else nd
        else:
            return self._consider_ups_junction(nd, nd)

    def get_dns_node(self, unit: 'Handler', consider_self: bool = False) -> 'Handler':
        nd = super().get_dns_node(unit, consider_self)
        if nd.type == 'CULVERT' and nd.sub_type.upper() != 'BEND':
            if nd.dns_units and nd.dns_units[0].type == 'JUNCTION':
                return self._consider_dns_junction(nd, nd.ups_units[0])
            else:
                return nd.dns_units[0] if nd.dns_units else nd
        else:
            return self._consider_dns_junction(nd, nd)
