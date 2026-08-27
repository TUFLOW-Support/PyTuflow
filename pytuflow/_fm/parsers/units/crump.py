from typing import TextIO

import numpy as np

from .handler import Handler


class Crump(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'structure'
        self.ups_label = None
        self.dns_label = None
        self.ups_remote_label = None
        self.dns_remote_label = None
        self.cc = np.nan
        self.b = np.nan
        self.zc = np.nan
        self.m = np.nan
        self.p1 = np.nan
        self.p2 = np.nan
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'CRUMP'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True),
                            ['ups_label', 'dns_label', 'ups_remote_label', 'dns_remote_label'], log_errors=[0, 1])
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs_float(self.read_line(), ['cc', 'b', 'zc', 'm'], log_errors=[0, 1, 2])
        self._set_attrs_float(self.read_line(), ['p1', 'p2'], log_errors=True)
        self.bed_level = self.zc
