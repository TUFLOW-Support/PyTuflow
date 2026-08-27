import logging
import typing

from .converter import Converter
from ..output import OutputCollection, Output
from ..helpers.scanner import Scanner, ScanRule

if typing.TYPE_CHECKING:
    from ..parsers.units.handler import Handler


logger = logging.getLogger('pytuflow')


class Replicate(Converter):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'REPLICATE_'

    def convert(self) -> OutputCollection:
        unit = self.replicate_ups_unit(self.unit)
        return unit.convert()

    def replicate_ups_unit(self, unit: 'Handler') -> 'Handler':
        ups_unit = self.get_ups_unit(unit)
        dz = self.elev_drop(ups_unit, unit)
        unit_repl = self.replicate(ups_unit)
        if unit_repl.type == 'RIVER':
            unit_repl.xs['y'] = unit_repl.xs['y'] - dz
        elif unit_repl.type == 'CONDUIT':
            if unit_repl.sub_type in ['SECTION', 'ASYMMETRIC']:
                unit_repl.section['y'] = unit_repl.section['y'] - dz
            else:
                unit_repl.inv -= dz
        else:
            logger.error(f'Cannot replicate {unit_repl.type} units: {unit_repl.uid}')

        return unit_repl

    def replicate(self, ref_unit: 'Handler') -> 'Handler':
        unit_repl = ref_unit.copy()
        unit_repl.bed_level = self.unit.bed_level
        unit_repl.ups_units = self.unit.ups_units
        unit_repl.dns_units = self.unit.dns_units
        unit_repl.dns_link_ids = self.unit.dns_link_ids
        unit_repl.ups_link_ids = self.unit.ups_link_ids
        unit_repl.id = self.unit.id
        unit_repl.uid = self.unit.uid
        unit_repl.x = self.unit.x
        unit_repl.y = self.unit.y
        unit_repl.wktgeom = self.unit.wktgeom
        return unit_repl

    def elev_drop(self, first_unit: 'Handler', second_unit: 'Handler') -> float:
        dns_unit = first_unit.dns_units[0]
        dz = dns_unit.dz
        while dns_unit.type == 'REPLICATE' and dns_unit.uid != second_unit.uid:
            dns_unit = dns_unit.dns_units[0]
            dz += dns_unit.dz
        return dz

    def get_ups_unit(self, unit: 'Handler', consider_self: bool = False) -> 'Handler':
        scanner = Scanner()
        rules = [
            ScanRule('INTERPOLATE'),
            ScanRule('REPLICATE'),
        ]
        return scanner.scan(unit, 'upstream', rules, consider_self, True, True)
