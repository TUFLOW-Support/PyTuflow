import typing
from collections import OrderedDict
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .conduit import Conduit
from .converter import Converter
from ..output import Output, OutputCollection
from ..helpers.geometry import Point, Line
from ..helpers.tuflow_empty_files import tuflow_empty_field_map
from ..helpers.scanner import Scanner, ScanRule

if typing.TYPE_CHECKING:
    from ..parsers.units.junction import Junction as JunctionHandler
    from ..parsers.units.handler import Handler


class Junction(Conduit, Converter):

    def __init__(self, handler: 'JunctionHandler' = None) -> None:
        super(Junction, self).__init__(handler)

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'JUNCTION_OPEN'


    def convert(self) -> OutputCollection:
        out_col = OutputCollection()
        if self.need_x_connector():
            out_col.extend(self.get_nwk())
        return out_col

    def map_nwk_attributes(selfs, field_map: dict) -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['Type'] = 'X'
        return d

    def get_nwk(self) -> OutputCollection:
        out_col = OutputCollection()
        # work out the file and layer name and which unit will act as the central unit
        # (i.e. all other units will connect to this unit with x-connector lines)
        if len(self.unit.ups_units) == 1:  # place x-connectors in downstream unit nwk layer
            ups_unit = self.get_ups_unit(self.unit, False)
            fpath, lyrname = self.output_gis_file('1d_nwk', ups_unit.type)
            central_unit = self.unit
        elif len(self.unit.dns_units) == 1:  # place x-connectors in upstream unit nwk layer
            dns_unit = self.get_dns_unit(self.unit, False)
            fpath, lyrname = self.output_gis_file('1d_nwk', dns_unit.type)
            central_unit = self.unit
        else:  # use majority
            maj_type = self.majority_unit_type_connected()
            fpath, lyrname = self.output_gis_file('1d_nwk', maj_type)
            central_unit = [x for x in self.ups_connections() + self.dns_connections() if x.type == maj_type][0]

        ups_units = self.ups_connections()
        if len(ups_units) > 1:
            for unit in ups_units:
                if unit.uid == central_unit.uid or unit.TYPE != 'unit':
                    continue
                out_col.append(self.create_x_connector(fpath, lyrname, unit, central_unit))
        dns_units = self.dns_connections()
        if len(dns_units) > 1:
            for unit in dns_units:
                if unit.uid == central_unit.uid or unit.TYPE != 'unit':
                    continue
                out_col.append(self.create_x_connector(fpath, lyrname, unit, central_unit))

        return out_col

    def ups_connections(self) -> list['Handler']:
        ups_units = [self.get_ups_unit(x, True) for x in self.unit.ups_units]
        ups_units = [x for x in ups_units if x.TYPE not in ['boundary', 'hydrology']]
        return ups_units

    def dns_connections(self) -> list['Handler']:
        dns_units = [self.get_dns_unit(x, True) for x in self.unit.dns_units]
        dns_units = [x for x in dns_units if x.TYPE != 'boundary']
        return dns_units

    def need_x_connector(self) -> bool:
        if len(self.unit.ups_units) < 2 and len(self.unit.dns_units) < 2:
            return False
        ups_units = self.ups_connections()
        if len(ups_units) > 1 and 'unit' in [x.TYPE for x in ups_units]:
            return True
        dns_units = self.dns_connections()
        if len(dns_units) > 1 and 'unit' in [x.TYPE for x in dns_units] and ups_units:
            return True
        return False

    def majority_unit_type_connected(self) -> str:
        maj_ups, cnt_ups = self.majority_type([self.get_ups_unit(x, True).type for x in self.unit.ups_units])
        maj_dns, cnt_dns = self.majority_type([self.get_dns_unit(x, True).type for x in self.unit.dns_units])
        if cnt_ups or cnt_dns:
            if cnt_ups > cnt_dns:
                return maj_ups
            else:
                return maj_dns

    def majority_type(self, types: list[str]) -> tuple[str, int]:
        if len(types) > 0:
            df = pd.DataFrame(types)
            counts = df.value_counts()
            return counts.index[0][0], counts.iloc[0]
        return None, 0

    def create_x_connector(self, fpath: Path, lyrname: str, unit: 'Handler', central_unit: 'Handler') -> 'Output':
        nwk = Output('GIS', self.unit.uid)
        nwk.fpath = fpath
        nwk.lyrname = lyrname
        nwk.field_map = tuflow_empty_field_map('1d_nwk')
        nwk.geom_type = 2  # ogr.wkbLineString
        nwk.content.geom = Line(points=[Point(node.x, node.y) for node in (unit, central_unit)]).to_wkt()
        nwk.content.attributes = self.map_nwk_attributes(nwk.field_map)
        return nwk

    def get_ups_unit(self, unit: 'Handler', consider_self: bool = False) -> 'Handler':
        scanner = Scanner()
        rules = [
            ScanRule(('CULVERT_OUTLET', 'CONDUIT')),
        ]
        return scanner.scan(unit, 'upstream', rules, consider_self, True, False)

    def get_dns_unit(self, unit: 'Handler', consider_self: bool = False) -> 'Handler':
        scanner = Scanner()
        rules = [
            ScanRule(('CULVERT_INLET', 'CONDUIT')),
            ScanRule(('ORIFICE', 'CONDUIT')),
        ]
        return scanner.scan(unit, 'downstream', rules, consider_self, True, False)
