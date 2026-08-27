import typing
from collections import OrderedDict

from .weir import Weir


if typing.TYPE_CHECKING:
    from ..parsers.units.handler import Handler


class GatedWeir(Weir):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'GATED WEIR_'

    def map_nwk_attributes(self, field_map: dict, unit: 'Handler') -> OrderedDict:
        d = super().map_nwk_attributes(field_map, unit)
        d['Type'] = 'WRO'
        return d
