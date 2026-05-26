from typing import TextIO

import numpy as np

from .handler import Handler


class Syphon(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'structure'
        self.ups_label = None
        self.dns_label = None
        self.zc = np.nan
        self.zsoff = np.nan
        self.area = np.nan
        self.zmax = np.nan
        self.cweir = np.nan
        self.cfull = np.nan
        self.m = np.nan
        self.zprime = np.nan
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'SYPHON'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label'], log_errors=True)
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs_float(self.read_line(), ['zc', 'zsoff', 'area', 'zmax'], log_errors=[0])
        self._set_attrs_float(self.read_line(), ['cweir', 'cfull', 'm', 'zprime'], log_errors=[0, 1])
        self.bed_level = self.zc
