import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Floodplain(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'unit'
        self.headers = ['x', 'y', 'n']
        self.ncol = len(self.headers)
        self.xs = pd.DataFrame()
        self.ups_label = None
        self.dns_label = None
        self.cd = 1.
        self.m = np.nan
        self.d1 = 0.
        self.d2 = 0.
        self.friction = ''
        self.ds_constraint = np.nan
        self.n = 0
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'FLOODPLAIN'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['sub_type'], log_errors=True)
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label'], log_errors=True)
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs(self.read_line(), ['cd', 'm', 'd1', 'd2', 'friction', 'ds_constraint'],
                        [float, float, float, float, str, float], log_errors=[0, 1, 2, 3])
        self._set_attrs_int(self.read_line(), ['n'], log_errors=True)
        if self.n:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10), max_rows=self.n, dtype='f4')
            if a.shape != (self.n, self.ncol):
                a = np.reshape(a, (self.n, self.ncol))
            self.xs = pd.DataFrame(a, columns=self.headers)
            self.line_no += self.n
            self.bed_level = float(str(self.xs.y.min()))
