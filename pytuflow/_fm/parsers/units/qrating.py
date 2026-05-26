from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Qrating(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'component'
        self.headers = ['flow', 'water level']
        self.ncol = len(self.headers)
        self.rating = pd.DataFrame()
        self.ndat = 0
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'QRATING'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self.uid = self._get_uid()
        self._set_attrs_int(self.read_line(), ['ndat'], log_errors=True)
        if self.ndat:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.ndat, dtype='f4')
            if a.shape != (self.ndat, self.ncol):
                a = np.reshape(a, (self.ndat, self.ncol))
            self.rating = pd.DataFrame(a, columns=self.headers)
            self.line_no += self.ndat
