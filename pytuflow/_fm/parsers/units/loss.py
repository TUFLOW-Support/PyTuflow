from typing import TextIO

import numpy as np

from .handler import Handler


class Loss(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.ups_label = None
        self.dns_label = None
        self.remote_label = None
        self.keyword = ''
        self.k = 0.
        self.rfmode = ''
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'LOSS'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label', 'remote_label'], log_errors=[0, 1])
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs_str(self.read_line(True), ['keyword'], log_errors=True)
        self._set_attrs(self.read_line(), ['k', 'rfmode'], [float, str], log_errors=True)
