import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Fehbdy(Handler):

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
        self.easting = np.nan
        self.northing = np.nan
        self.tdelay = 0.
        self.t = np.nan
        self.bfonly = ''
        self.scflag = ''
        self.scfact = ''
        self.hymode = ''
        self.cyflag = ''
        self.carea = 0.
        self._dummy = ''
        self.urbext = np.nan
        self.altbar = np.nan
        self.starea = np.nan
        self.stdur = np.nan
        self.snrate = np.nan
        self.sn100 = np.nan
        self.temp = np.nan
        self.amrate = np.nan
        self.calcrates = ''
        self.saar = np.nan
        self.force = ''
        self.erflag = ''
        self.p = 0.
        self.tf = np.nan
        self.ts = np.nan
        self.arf = 1.
        self.c = np.nan
        self.d1 = np.nan
        self.d2 = np.nan
        self.d3 = np.nan
        self.e = np.nan
        self.f = np.nan
        self.cwflag = ''
        self.cwi = 0.
        self.prflag =''
        self.prvar = ''
        self.pr = np.nan
        self.spr = np.nan
        self.tpflag = ''
        self.calib = 1.
        self.tp = 1.
        self.dplbar = np.nan
        self.dpsbar = np.nan
        self.popwet = np.nan
        self.bfflag = ''
        self.bfadjs = -9e29
        self.bf = 0.
        self.uhflag = ''
        self.units = ''
        self.uhfctr = 0.
        self.nuh = 0
        self.rpflag = ''
        self.em2h = np.nan
        self.em24h = np.nan
        self.em25d = np.nan
        self.nrp = 0
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'FEHBDY'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self.uid = self._get_uid()
        self._set_attrs_float(self.read_line(), ['z', 'easting', 'northing'])
        self._set_attrs(self.read_line(), ['tdelay', 't', 'bfonly', 'scflag', 'scfact', 'hymode'],
                        [float, float, str, str, str, str], log_errors=True)
        self._set_attrs_str(self.read_line(True), ['cyflag'], log_errors=True)
        self._set_attrs(self.read_line(), ['carea', '_dummy', '_dummy', '_dummy', 'urbext', 'altbar'],
                        [float, str, str, str, float, float])
        self._set_attrs(self.read_line(),
                        ['starea', 'stdur', '_dummy', 'snrate', 'sn100', 'temp', 'amrate', 'calcrates'],
                        [float, float, str, float, float, float, float, str])
        self._set_attrs(self.read_line(), ['saar', '_dummy', '_dummy', '_dummy', 'force'],
                        [float, str, str, str, str])
        self._set_attrs_str(self.read_line(True), ['erflag'])
        if self.erflag.upper() == 'OBSER':
            self._set_attrs_float(self.read_line(), ['p'])
        elif self.erflag.upper() == 'FEHER':
            self._set_attrs_float(self.read_line(), ['tf', 'ts', 'arf', 'c', 'd1', 'd2', 'd3', 'e', 'f'])
        elif self.erflag.upper() == 'PMFER':
            self._set_attrs(self.read_line(), ['_dummy', '_dummy', 'arf'], [str, str, float])
        else:
            _ = self.read_line()
        self._set_attrs_str(self.read_line(True), ['cwflag'])
        if self.cwflag.upper() == 'OBSCW':
            self._set_attrs_float(self.read_line(), ['cwi'])
        elif self.cwflag.upper() in ['FSRCW', 'PMFCW']:
            _ = self.read_line()
        else:
            _ = self.read_line()
        self._set_attrs_str(self.read_line(), ['prflay', 'prvar'])
        if self.prflag.upper() == 'OBSPR':
            self._set_attrs_float(self.read_line(), ['pr'])
        elif self.prflag.upper() == 'FEHPR':
            self._set_attrs_float(self.read_line(), ['spr'])
        else:
            _ = self.read_line()
        self._set_attrs_str(self.read_line(True), ['tpflag'])
        if self.tpflag.upper() == 'OBSTP':
            self._set_attrs_float(self.read_line(), ['calib', 'tp'])
        elif self.tpflag.upper() == 'FEHTP':
            self._set_attrs_float(self.read_line(), ['calib', 'dplbar', 'dpsbar', 'popwet'])
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
        self._set_attrs(self.read_line(), ['nuh', 'units', 'uhfctr'], [int, str, float], log_errors=[0])
        if self.nuh:
            a = np.genfromtxt(self.fo, delimiter=(10,), max_rows=self.nuh, dtype='f4')
            if a.shape != (self.nuh, self.ncols_uh):
                a = np.reshape(a, (self.nuh, self.ncols_uh))
            self.unit_hydrograph = pd.DataFrame(a, columns=self.uh_headers)
            self.line_no += self.nuh

        self._set_attrs_str(self.read_line(True), ['rpflag'])
        if self.rpflag.upper() == 'PMFER':
            self._set_attrs_float(self.read_line(), ['em2h', 'em24h', 'em25d'], ind=1)
        elif self.rpflag.upper() == 'WINRP':
            _  = self.read_line()
        elif self.rpflag.upper() == 'SUMRP':
            _ = self.read_line()
        elif self.rpflag.upper() == 'OBSRP':
            self._set_attrs_int(self.read_line(), ['nrp'], log_errors=True)
        else:
            _ = self.read_line()

        if self.nrp:
            a = np.genfromtxt(self.fo, delimiter=(10,), max_rows=self.nrp, dtype='f4')
            if a.shape != (self.nrp, self.ncols_rp):
                a = np.reshape(a, (self.nrp, self.ncols_rp))
            self.rainfall = pd.DataFrame(a, columns=self.rp_headers)
            self.line_no += self.nrp
