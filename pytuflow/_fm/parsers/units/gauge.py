import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Gauge(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'component'
        self.measured_headers = ['', 'Time']
        self.ncol_measured = len(self.measured_headers)
        self.measured_data = pd.DataFrame()
        self.rating_headers = ['Flow', 'Stage']
        self.ncol_rating = len(self.rating_headers)
        self.rating = pd.DataFrame()
        self.method = ''
        self.cf_identifier = ''
        self.keyword = ''
        self.limit_strategy = 'STRICT'
        self.limit_q = np.nan
        self.lower = np.nan
        self.upper = np.nan
        self.missing_stategy = 'INTERP'
        self.n1 = 0
        self.tlag = 0.
        self.hoffset = 0.
        self.tm = 'SECONDS'
        self.smooth = 'LINEAR'
        self.qmult = 1.
        self.qfmax = 9e29
        self.tmiss = np.nan
        self.qmin = -9e29
        self.n2 = 0
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'GAUGE'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self.uid = self._get_uid()
        self._set_attrs_str(self.read_line(True), ['method'], log_errors=True)
        self._set_attrs_str(self.read_line(True), ['cf_identifier'], log_errors=True)
        self._set_attrs_str(self.read_line(True), ['keyword'], log_errors=True)
        self.measured_headers[0] = self.keyword[0] + self.keyword[1:].lower()
        self._set_attrs(self.read_line(),
                        ['n1', 'tlag', 'hoffset', 'tm', 'smooth', 'qmult', 'qfmax', 'tmiss', 'qmin'],
                        [int, float, float, str, str, float, float, float, float], log_errors=[0])
        if self.n1:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.n1, dtype='f4')
            if a.shape != (self.n1, self.ncol_measured):
                a = np.reshape(a, (self.n1, self.ncol_measured))
            self.measured_data = pd.DataFrame(a, columns=self.measured_headers)
            self.line_no += self.n1

        self._set_attrs_int(self.read_line(), ['n2'], log_errors=True)
        if self.n2:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.n2, dtype='f4')
            if a.shape != (self.n2, self.ncol_rating):
                a = np.reshape(a, (self.n2, self.ncol_rating))
            self.rating = pd.DataFrame(a, columns=self.rating_headers)
            self.line_no += self.n2
