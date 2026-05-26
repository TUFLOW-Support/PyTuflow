from typing import TextIO

import numpy as np

from .handler import Handler


class FlatVWeir(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'structure'
        self.ups_label = None
        self.dns_label = None
        self.ups_remote_label = None
        self.dns_remote_label = None
        self.cc = 1.
        self.b = 0.
        self.zc = np.nan
        self.r = 0.
        self.m = np.nan
        self.n = 0.
        self.ds_fslope = 5
        self.alpha = 1.2
        self.zbank = np.nan
        self.p1 = 0.
        self.p2 = 0.
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'FLAT'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True),
                            ['ups_label', 'dns_label', 'ups_remote_label', 'dns_remote_label'], log_errors=[0, 1])
        self.id = self.ups_label
        self.uid = f'FLAT-V WEIR__{self.id}'
        self._set_attrs_float(self.read_line(),
                              ['cc', 'b', 'zc', 'r', 'm', 'n', 'ds_fslope', 'alpha', 'zbank'], log_errors=[2, 8])
        if isinstance(self.ds_fslope, float):
            self.ds_fslope = int(self.ds_fslope)
        self._set_attrs_float(self.read_line(), ['p1', 'p2'])
        self.bed_level = self.zc
