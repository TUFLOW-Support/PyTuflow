import typing

import numpy as np

from .converter import Converter

if typing.TYPE_CHECKING:
    from ..parsers.units.handler import Handler


class CulvertBend(Converter):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'CULVERT_BEND'

    @staticmethod
    def bend_loss(unit: 'Handler') -> float:
        if unit.dns_units:
            unit_ = unit.dns_units[0]
            if (unit_.dns_units and unit_.dns_units[0].type == 'CULVERT' and unit_.dns_units[0].sub_type.upper() == 'BEND' and
                    unit_.dns_units[0].keyword.upper() == 'UPSTREAM'):
                return unit_.dns_units[0].kb
        if (unit.ups_units and unit.ups_units[0].type == 'CULVERT' and unit.ups_units[0].sub_type.upper() == 'BEND' and
                unit.ups_units[0].keyword.upper() == 'DOWNSTREAM'):
            return unit.ups_units[0].kb
        return np.nan
