import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Breach(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'structure'
        self.headers = ['Time', 'Horizontal Offset', 'Bottom Width', 'Elevation Lowest Point', 'Depth of Base', 'Side Slope', 'Type']
        self.ncol = len(self.headers)
        self.breach_table = pd.DataFrame()
        self.ups_label = None
        self.dns_label = None
        self.method = ''
        self.cdweir = np.nan
        self.cdorifice = np.nan
        self.modlimit = np.nan
        self.interp = 'SINE'
        self.fcollapse = np.nan
        self.h = np.nan
        self.elvmin = np.nan
        self.shape = ''
        self.n1 = 0
        self.tlag = 0.
        self.tm = 'SECONDS'
        self.repeat = 'NOEXTEND'
        self.trigger_flag = ''
        self.trigger_level = np.nan
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'BREACH'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label'], log_errors=True)
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs(self.read_line(),
                        ['method', 'cdweir', 'cdorifice', 'modlimit', 'interp', 'fcollapse', 'h', 'elvmin', 'shape'],
                        [str, float, float, float, str, float, float, float, str], log_errors=[0])
        self._set_attrs(self.read_line(), ['n1', 'tlag', 'tm', 'repeat', 'trigger_flag', 'trigger_level'],
                        [int, float, str, str, str, float], log_errors=[0, 4, 5])
        if self.n1:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10, 10, 10, 10, 10), max_rows=self.n1, dtype='f4')
            if a.shape != (self.n1, self.ncol):
                a = np.reshape(a, (self.n1, self.ncol))
            self.breach_table = pd.DataFrame(a, columns=self.headers)
            self.line_no += self.n1
            self.bed_level = float(str(self.breach_table['Elevation Lowest Point'].iloc[0]))
