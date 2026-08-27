import typing
from collections import OrderedDict

from .weir import Weir


if typing.TYPE_CHECKING:
    from ..parsers.units.handler import Handler


class Rnweir(Weir):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'RNWEIR_'

    def map_nwk_attributes(self, field_map: dict, unit: 'Handler') -> OrderedDict:
        d = super().map_nwk_attributes(field_map, unit)
        d['Type'] = 'WB'
        d['Height_or_WF'] = unit.cv
        return d
