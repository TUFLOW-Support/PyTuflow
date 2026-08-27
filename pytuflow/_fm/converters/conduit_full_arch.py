import io
import typing
from collections import OrderedDict
from pathlib import Path

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .conduit_symmetrical import ConduitSymmetrical
from ..helpers.geometry import create_hw_table, parabolic_arch_conduit


if typing.TYPE_CHECKING:
    from ..parsers.units.handler import Handler


class ConduitFullArch(ConduitSymmetrical):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'CONDUIT_FULLARCH'

    def map_nwk_attributes(self, field_map: dict, unit: 'ConduitHandler') -> OrderedDict:
        d = super().map_nwk_attributes(field_map, unit)
        d['n_nf_Cd'] = 1.
        return d

    def map_tab_attributes(selfs, field_map: dict, unit: 'ConduitHandler', tab_fpath: Path, hw_fpath: Path) -> OrderedDict:
        d = super().map_tab_attributes(field_map, unit, tab_fpath, hw_fpath)
        d['Flags'] = 'n'
        d['Column_3'] = 'n'
        return d

    def get_hw(self) -> None:
        self.hw.fpath = self.settings.output_dir / 'csv' / f'{self.unit.id}.csv'
        u1 = self.unit
        u2 = self.get_dns_unit(self.unit)
        hw1 = self.arch_hw_table(u1)
        hw2 = self.arch_hw_table(u2)
        self.hw.content = self.generate_hw_table(u1, u2, hw1, hw2)
        return self.hw

    def arch_hw_table(self, unit: 'Handler') -> pd.DataFrame:
        base = pd.DataFrame([[0., unit.inv, unit.fribot], [unit.width, unit.inv, unit.fribot]], columns=['x', 'z', 'n'])
        arch = parabolic_arch_conduit(unit.width, unit.inv + unit.archyt, unit.inv, as_df=True)
        arch['n'] = unit.friarc
        section = pd.concat([base, arch[::-1]], axis=0)
        return create_hw_table(section, as_df=True)
