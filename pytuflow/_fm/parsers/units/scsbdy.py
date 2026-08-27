import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Scsbdy(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'hydrology'
        self.uh_headers = ['unit hydrograph']
        self.ncols_uh = len(self.uh_headers)
        self.unit_hydrograph = pd.DataFrame()
        self.rp_headers = ['rainfall']
        self.ncols_rp = len(self.rp_headers)
        self.rainfall = pd.DataFrame()
        self.z = np.nan
        self.tdelay = np.nan
        self.t = np.nan
        self.carea = np.nan
        self.stdur = np.nan
        self.p = np.nan
        self.cn = np.nan
        self.pr = np.nan
        self.tp = np.nan
        self.bfadjs = -9e29
        self.bf = 0.
        self.uhflag = ''
        self.nuh = 0
        self.rpflag = ''
        self.nrp = 0
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'SCSBDY'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self.uid = self._get_uid()
        self._set_attrs_float(self.read_line(), ['z'])
        self._set_attrs_float(self.read_line(), ['tdelat', 't'])
        self._set_attrs_float(self.read_line(), ['carea', 'stdur'])
        self._set_attrs_float(self.read_line(), ['p'])
        self._set_attrs_float(self.read_line(), ['cn'])
        if self.cn > 0.:
            self.pr = self.cn
            self.cn = np.nan
        self._set_attrs_float(self.read_line(), ['tp'])
        self._set_attrs_float(self.read_line(), ['bfadjs', 'bf'])
        self._set_attrs_str(self.read_line(), ['uhflag'])
        self._set_attrs_int(self.read_line(), ['nuh'], log_errors=True)
        if self.nuh:
            a = np.genfromtxt(self.fo, delimiter=(10,), max_rows=self.nuh, dtype='f4')
            if a.shape != (self.nuh, self.ncols_uh):
                a = np.reshape(a, (self.nuh, self.ncols_uh))
            self.unit_hydrograph = pd.DataFrame(a, columns=self.uh_headers)
            self.line_no += self.nuh

        self._set_attrs_str(self.read_line(True), ['rpflag'])
        self._set_attrs_int(self.read_line(), ['nrp'], log_errors=True)
        if self.nrp:
            a = np.genfromtxt(self.fo, delimiter=(10,), max_rows=self.nrp, dtype='f4')
            if a.shape != (self.nrp, self.ncols_rp):
                a = np.reshape(a, (self.nrp, self.ncols_rp))
            self.rainfall = pd.DataFrame(a, columns=self.rp_headers)
            self.line_no += self.nrp
