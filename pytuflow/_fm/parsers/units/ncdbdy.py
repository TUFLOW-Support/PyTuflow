import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Ncdbdy(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.type = 'boundary'
        self.xs_headers = ['Chainage', 'Elevation', 'n', 'panel_marker']
        self.ncol_xs = len(self.xs_headers)
        self.xs = pd.DataFrame()
        self.override_table_headers = ['Elevation', 'Time']
        self.ncol_override_table = len(self.override_table_headers)
        self.override_table = pd.DataFrame()
        self.ups_label = None
        self.dns_label = None
        self.remote_label_1 = None
        self.remote_label_2 = None
        self.ctype = ''
        self.clptyp = ''
        self.slope = 0.
        self.ndat = 0
        self.novdat = 0
        self.tm = 'SECONDS'
        self.repeat = 'NOEXTEND'
        self.ovrmth = ''
        self.tlag = 0.
        self.smooth = 'LINEAR'
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'NCDBDY'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label', 'remote_label_1', 'remote_label_2'],
                            log_errors=[0])
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs_str(self.read_line(), ['ctype'], log_errors=True)
        if self.ctype.upper() == 'NORMAL':
            self._set_attrs(self.read_line(), ['slptyp', 'slope'], [str, float], log_errors=[0])
        self._set_attrs_int(self.read_line(), ['ndat'], log_errors=True)
        if self.ndat:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10), max_rows=self.ndat)
            if a.shape != (self.ndat, 3):
                a = np.reshape(a, (self.ndat, 3))
            self.xs = pd.DataFrame(a, columns=self.xs_headers)
            self.line_no += self.ndat

        self._set_attrs(self.read_line(), ['novdat', 'tm', 'repeat', 'ovrmth', 'tlag', 'smooth'],
                        [int, str, str, str, float, str], log_errors=[0, 3])
        if self.novdat:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.novdat)
            if a.shape != (self.novdat, self.ncol_override_table):
                a = np.reshape(a, (self.novdat, self.ncol_override_table))
            self.override_table = pd.DataFrame(a, columns=self.override_table_headers)
            self.line_no += self.novdat
