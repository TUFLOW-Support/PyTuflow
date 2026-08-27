import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Htbdy(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'boundary'
        self.headers = ['Stage', 'Time']
        self.ncol = len(self.headers)
        self.table = pd.DataFrame()
        self.n1 = 0
        self.z = 0.
        self.tm = 'SECONDS'
        self.repeat = 'NOEXTEND'
        self.smooth = 'LINEAR'
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'HTBDY'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self.uid = self._get_uid()
        self._set_attrs(self.read_line(), ['n1', 'z', 'tm', 'repeat', 'smooth'],
                        [int, float, str, str, str], log_errors=[0])
        if self.n1:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.n1, dtype='f4')
            if a.shape != (self.n1, self.ncol):
                a = np.reshape(a, (self.n1, self.ncol))
            self.table = pd.DataFrame(a, columns=self.headers)
            self.line_no += self.n1
