import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Rebdy(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'boundary'
        self.rtypes = []
        self.n = 0
        self.data = []
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'REBDY'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(), ['id'], log_errors=True)
        self.uid = self._get_uid()
        self.rtypes = self.read_line()
        self.n = len(self.rtypes)
        for _ in range(self.n):
            data = RebdyData()
            data.load(line, fo, fixed_field_len)
            self.data.append(data)
            self.line_no = data.line_no


class RebdyData(Handler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rtype = ''
        self.tlag = 0.
        self.ndat = 0
        self.tm = 'SECONDS'
        self.repeat = 'NOEXTEND'
        self.smooth = 'LINEAR'
        self.qmult = 1.
        self.intenstr = 'HOURS'
        self.diflag = 'INTENSITY'
        self.table = pd.DataFrame()
        self.headers = ['Depth', 'Time', 'Date']
        self.ncol = len(self.headers)

    @staticmethod
    def unit_type_name() -> str:
        return 'NOT A UNIT'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs(self.read_line(), ['ndat', 'tlag', 'z', 'tm', 'repeat', 'smooth', 'qmult'],
                        [int, float, float, str, str, str, float], log_errors=[0])
        self._set_attrs_str(self.read_line(), ['intenstr', 'diflag'])
        if self.ndat:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10), max_rows=self.ndat)
            if a.shape != (self.ndat, self.ncol):
                a = np.reshape(a, (self.ndat, self.ncol))
            self.table = pd.DataFrame(a, columns=self.headers)
            self.table[['Depth', 'Time']] = self.table[['Depth', 'Time']].astype(float)
            self.line_no += self.ndat
