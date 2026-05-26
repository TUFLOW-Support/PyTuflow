from typing import TextIO

import numpy as np

from .handler import Handler


class Manhole(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'component'
        self.revision = 1
        self.manhole_label = None
        self.ups_label = None
        self.dns_label = None
        self.z = np.nan
        self.dia = np.nan
        self.cd = np.nan
        self.r = np.nan
        self.k = np.nan
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'MANHOLE'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self.revision = self._get_revision()
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label', 'manhole_label'], log_errors=[0, 1])
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs_float(self.read_line(), ['z', 'dia', 'cd', 'r', 'k'], log_errors=True)
