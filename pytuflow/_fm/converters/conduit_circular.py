import typing
from collections import OrderedDict

import numpy as np

from .culvert_bend import CulvertBend
from .conduit import Conduit
from ..output import Output, OutputCollection


if typing.TYPE_CHECKING:
    from ..parsers.units.conduit import Conduit as ConduitHandler


class ConduitCircular(Conduit):

    def __init__(self, unit: 'ConduitHandler' = None) -> None:
        super().__init__(unit)
        if unit:
            self.ecf = Output('CONTROL', unit.uid)
            self.nwk = Output('GIS', unit.uid)

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'CONDUIT_CIRCULAR'

    def convert(self) -> OutputCollection:
        out_col = OutputCollection()
        if not self.unit or not self.dat or self.unit.dx == 0:
            return out_col
        out_col.append(self.get_nwk())
        out_col.append(self.get_ecf())
        return out_col

    def map_nwk_attributes(self, field_map: dict, unit: 'ConduitHandler') -> OrderedDict:
        d = OrderedDict()
        for key, value in field_map.items():
            d[key] = None
        d['ID'] = unit.id
        d['Type'] = 'C'
        d['Len_or_ANA'] = unit.dx
        d['n_nf_Cd'] = unit.fribot
        d['US_Invert'] = unit.bed_level
        d['DS_Invert'] = unit.dns_units[0].bed_level
        bend_loss = CulvertBend.bend_loss(unit)
        if not np.isnan(bend_loss):
            d['Form_Loss'] = bend_loss
        d['Number_of'] = 1
        d['Width_or_Dia'] = unit.dia
        d['WConF_or_WEx'] = 1.
        d['EntryC_or_WSa'] = 0.5
        d['ExitC_or_WSb'] = 1.0
        return d
