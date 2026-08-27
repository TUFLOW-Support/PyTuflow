import io
from collections import OrderedDict
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .conduit_symmetrical import ConduitSymmetrical
from ..helpers.geometry import create_hw_table, interpolate_hw_tables


class ConduitAsymmetrical(ConduitSymmetrical):

    @staticmethod
    def complete_unit_type_name() -> str:
        return 'CONDUIT_ASYMMETRIC'

    def map_nwk_attributes(self, field_map: dict, unit: 'ConduitHandler') -> OrderedDict:
        d = super().map_nwk_attributes(field_map, unit)
        if unit.method.upper() == 'MANNING':
            d['n_nf_Cd'] = 1.
        return d

    def map_tab_attributes(self, field_map: dict, unit: 'ConduitHandler', tab_fpath: Path, hw_fpath: Path) -> OrderedDict:
        d = super().map_tab_attributes(field_map, unit, tab_fpath, hw_fpath)
        if unit.method.upper() == 'MANNING' and self.get_dns_unit(unit).method.upper() == 'MANNING':
            d['Flags'] = 'n'
            d['Column_3'] = 'n'
        return d

    def get_hw(self) -> None:
        self.hw.fpath = self.settings.output_dir / 'csv' / f'{self.unit.id}.csv'
        u1 = self.unit
        u2 = self.get_dns_unit(self.unit)
        if u1.method.upper() == 'MANNING':
            u1.section.rename(columns={'ks': 'n'})
            hw1 = create_hw_table(u1.section, as_df=True)
        else:
            hw1 = create_hw_table(u1.section[['x', 'y']], as_df=True)
        if u2.method.upper() == 'MANNING':
            u2.section.rename(columns={'ks': 'n'})
            hw2 = create_hw_table(u2.section, as_df=True)
        else:
            hw2 = create_hw_table(u2.section[['x', 'y']], as_df=True)
        self.hw.content = self.generate_hw_table(u1, u2, hw1, hw2)
        return self.hw
