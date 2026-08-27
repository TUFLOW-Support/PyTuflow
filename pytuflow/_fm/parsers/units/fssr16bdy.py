import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Fssr16bdy(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'boundary'
        self.uh_headers = ['unit hydrograph']
        self.ncols_uh = len(self.uh_headers)
        self.unit_hydrograph = pd.DataFrame()
        self.rp_headers = ['rainfall']
        self.ncols_rp = len(self.rp_headers)
        self.rainfall = pd.DataFrame()
        self.z = np.nan
        self.tdelay = 0.
        self.t = np.nan
        self.bfonly = ''
        self.country = ''
        self.carea = np.nan
        self.s1085 = np.nan
        self.msl = 0.
        self.soil = np.nan
        self.urban = np.nan
        self.starea = np.nan
        self.stdur = np.nan
        self.rsmd = np.nan
        self.snrate = np.nan
        self.saar = np.nan
        self.m5_2d = np.nan
        self.r = np.nan
        self.m5_25d = np.nan
        self.force = ''
        self.erflag = ''
        self.p = np.nan
        self.tf = np.nan
        self.ts = np.nan
        self.arf = 1.
        self.cwflag = ''
        self.cwi = np.nan
        self.prflag = ''
        self.pr = np.nan
        self.spr = np.nan
        self.tpflag = ''
        self.calib = 1.
        self.tp = np.nan
        self.bfflag = ''
        self.bfadjs = -9e29
        self.bf = 0.
        self.uhflag = ''
        self.nuh = 0
        self.rpflag = ''
        self.nrp = 0
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'FSSR16BDY'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self.uid = self._get_uid()
        self._set_attrs_float(self.read_line(), ['z'])
        self._set_attrs(self.read_line(), ['tdelay', 't', 'bfonly'], [float, float, str])
        self._set_attrs_str(self.read_line(), ['country'], log_errors=True)
        self._set_attrs_float(self.read_line(), ['carea', 's1085', 'msl', 'soil', 'urban'])
        self._set_attrs_float(self.read_line(), ['starea', 'stdur', 'rsmd', 'snrate'])
        self._set_attrs(self.read_line(), ['saar', 'm5_2d', 'r', 'm5_25d', 'force'],
                        [float, float, float, float, str])
        self._set_attrs_str(self.read_line(True), ['erflag'])
        if self.erflag.upper() == 'OBSER':
            self._set_attrs_float(self.read_line(), ['p'])
        elif self.erflag.upper() == 'FSRER':
            self._set_attrs_float(self.read_line(), ['tf', 'ts', 'arf'])
        else:
            _ = self.read_line()
        self._set_attrs_str(self.read_line(True), ['cwflag'])
        if self.cwflag.upper() == 'OBSCW':
            self._set_attrs_float(self.read_line(), ['cwi'])
        else:
            _ = self.read_line()
        self._set_attrs_str(self.read_line(True), ['prflag'])
        if self.prflag.upper() == 'OBSPR':
            self._set_attrs_float(self.read_line(), ['pr'])
        elif self.prflag.upper() == 'F16PR':
            self._set_attrs_float(self.read_line(), ['spr'])
        else:
            _ = self.read_line()
        self._set_attrs_str(self.read_line(True), ['tpflag'])
        if self.tpflag.upper() == 'OBSTP':
            self._set_attrs_float(self.read_line(), ['calib', 'tp'])
        elif self.tpflag.upper() == 'R124TP':
            self._set_attrs_float(self.read_line(), ['calib'])
        else:
            _ = self.read_line()
        self._set_attrs_str(self.read_line(True), ['bfflag'])
        if self.bfflag.upper() == 'OBSBF':
            self._set_attrs_float(self.read_line(), ['bfadjs', 'bf'])
        elif self.bfflag.upper() == 'F16BF':
            self._set_attrs_float(self.read_line(), ['bfadjs'])
        else:
            _ = self.read_line()
        self._set_attrs_str(self.read_line(True), ['uhflag'])
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
