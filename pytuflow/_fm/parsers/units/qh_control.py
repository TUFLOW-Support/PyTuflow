import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class QhControl(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'structure'
        self.headers = ['Flow', 'Elevation']
        self.ncol = len(self.headers)
        self.qh = pd.DataFrame()
        self.ups_label = None
        self.dns_label = None
        self.zc = np.nan
        self.m = np.nan
        self.smooth = 'LINEAR'
        self.n1 = 0
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'QH CONTROL'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label'], log_errors=True)
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs(self.read_line(), ['zc', 'm', 'smooth'], [float, float, str], log_errors=[0])
        self._set_attrs_int(self.read_line(), ['n1'], log_errors=True)
        if self.n1:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.n1, dtype='f4')
            if a.shape != (self.n1, self.ncol):
                a = np.reshape(a, (self.n1, self.ncol))
            self.qh = pd.DataFrame(a, columns=self.headers)
            self.line_no += self.n1
