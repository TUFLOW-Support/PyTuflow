import typing
from collections import OrderedDict

from .weir import Weir


if typing.TYPE_CHECKING:
    from ..parsers.units.handler import Handler


class Notweir(Weir):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'NOTWEIR_'

    def map_nwk_attributes(self, field_map: dict, unit: 'Handler') -> OrderedDict:
        d = super().map_nwk_attributes(field_map, unit)
        d['Type'] = 'WW'
        d['Height_or_WF'] = unit.cv
        d['HConF_or_WC'] = unit.cd
        d['WConF_or_WEx'] = unit.e
        return d
