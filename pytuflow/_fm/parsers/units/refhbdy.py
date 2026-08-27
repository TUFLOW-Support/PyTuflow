import io
import re
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler, SubHandler


class Refhbdy(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'hydrology'
        self.revision = 1
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
        self.dt = np.nan
        self.bfonly = ''
        self.scflag = ''
        self.scfact = np.nan
        self.hymode = ''
        self.scaling = ''
        self.minflow = -9e29
        self.carea = np.nan
        self.saar = np.nan
        self.urbext = np.nan
        self.seasonflag = ''
        self.method = ''
        self.starea = np.nan
        self.stdur = np.nan
        self.snrate = np.nan
        self.erflag = ''
        self.arfflag = ''
        self.comment = ''
        self.p = np.nan
        self.t = np.nan
        self.arf = np.nan
        self.c = np.nan
        self.d1 = np.nan
        self.d2 = np.nan
        self.d3 = np.nan
        self.e = np.nan
        self.f = np.nan
        self.rpflag = ''
        self.scfflag = ''
        self.scf = np.nan
        self.nrp = 0
        self.cmaxflag = ''
        self.ciniflag = ''
        self.alphaflag = ''
        self.cmdcf = np.nan
        self.cmax = np.nan
        self.cini = np.nan
        self.alpha = np.nan
        self.bfihost = np.nan
        self.uhflag = ''
        self.tpflag = ''
        self.upflag = ''
        self.ukflag = ''
        self.tpdcf = np.nan
        self.tp0 = np.nan
        self.tpt = np.nan
        self.dplbar = np.nan
        self.dpsbar = np.nan
        self.popwet = np.nan
        self.up = np.nan
        self.uk = np.nan
        self.nuh = 0
        self.units = ''
        self.uhfctr = np.nan
        self.blflag = ''
        self.brflag = ''
        self.bf0flag = ''
        self.bldcf = np.nan
        self.bl = np.nan
        self.brdcf = np.nan
        self.br = np.nan
        self.bf0 = np.nan
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'REFHBDY'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        if '#REVISION#2' in line.upper():
            self.revision = 2
            self._sub_obj = ReFHRevised(self.parent)
        else:
            self._sub_obj = ReFH(self.parent)
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self.uid = self._get_uid()
        self._set_attrs_float(self.read_line(), ['z', 'easting', 'northing'])
        self._set_attrs(self.read_line(),
                        ['tdelay', 'dt', 'bfonly', 'scflag', 'scfact', 'hymode', 'scaling', 'minflow'],
                        [float, float, str, str, float, str, str, float], log_errors=True)
        self._set_attrs(self.read_line(),
                        ['carea', 'saar', 'urbext', 'seasonflag', 'method'],
                        [float, float, float, str, str], log_errors=True)
        self._sub_obj._sync_obj(self)
        if self.revision == 2:
            self._sub_obj.load(line, fo, fixed_field_len, self.line_no)
            self._sync_obj(self._sub_obj)
        self._set_attrs_float(self.read_line(), ['starea', 'stdur', 'snrate'])
        self._set_attrs_str(self.read_line(), ['erflag', 'arfflag'])
        self._set_attrs_float(self.read_line(), ['p', 't', 'arf', 'c', 'd1', 'd2', 'd3', 'e', 'f'])
        self._set_attrs(self.read_line(), ['rpflag', 'scfflag', 'scf'],[str, str, float])
        self._set_attrs_int(self.read_line(), ['nrp'], log_errors=True)
        if self.nrp:
            a = np.genfromtxt(self.fo, delimiter=(10,), max_rows=self.nrp, dtype='f4')
            if a.shape != (self.nrp, self.ncols_rp):
                a = np.reshape(a, (self.nrp, self.ncols_rp))
            self.rainfall = pd.DataFrame(a, columns=self.rp_headers)
            self.line_no += self.nrp

        self._set_attrs_str(self.read_line(), ['cmaxflag', 'ciniflag', 'alphaflag'])
        self._set_attrs_float(self.read_line(), ['cmdcf', 'cmax', 'cini', 'alpha', 'bfihost'])
        self._set_attrs_str(self.read_line(), ['uhflag', 'tpflag', 'upflag', 'ukflag'])
        self._set_attrs_float(self.read_line(), ['tpdcf', 'tp0', 'tpt', 'dplbar', 'dpsbar', 'popwet', 'up', 'uk'])
        self._set_attrs(self.read_line(), ['nuh', 'units', 'uhfctr'], [int, str, float], log_errors=[0])
        if self.nuh:
            a = np.genfromtxt(self.fo, delimiter=(10,), max_rows=self.nuh, dtype='f4')
            if a.shape != (self.nuh, self.ncols_uh):
                a = np.reshape(a, (self.nuh, self.ncols_uh))
            self.unit_hydrograph = pd.DataFrame(a, columns=self.uh_headers)
            self.line_no += self.nuh

        self._set_attrs_str(self.read_line(), ['blflag', 'brflag', 'bf0flag'])
        self._set_attrs_float(self.read_line(), ['bldcf', 'bl', 'brdcf', 'br', 'bf0'])

class ReFH(SubHandler):
    pass


class ReFHRevised(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        self.subarea1 = np.nan
        self.dplbar1 = np.nan
        self.suburbext1 = np.nan
        self.calib1 = np.nan
        self.subbr1 = np.nan
        self._dummy = ''
        self.subarea2 = np.nan
        self.dplbar2 = np.nan
        self.suburbext2 = np.nan
        self.calib2 = np.nan
        self.subpr2 = np.nan
        self.rpordepth = np.nan
        self.rpdvalue = np.nan
        self.loss_by = ''
        self.subbr2 = np.nan
        self.subarea3 = np.nan
        self.dplbar3 = np.nan
        self.suburbext3 = np.nan
        self.calib3 = np.nan
        self.subpr3 = np.nan
        self.subbr3 = np.nan

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs(self.read_line(),
                        ['subarea1', 'dplbar1', 'suburbext1', 'calib1', '_dummy', '_dummy', '_dummy', '_dummy', 'subbr1'],
                        [float, float, float, float, str, str, str, str, float], log_errors=True)
        self._set_attrs(self.read_line(),
                        ['subarea2', 'dplbar2', 'suburbext2', 'calib2', 'subpr2', 'rpordepth', 'rpdvalue', 'loss_by', 'subbr2'],
                        [float, float, float, float, float, float, float, str, float], log_errors=True)
        self._set_attrs(self.read_line(),
                        ['subarea3', 'dplbar3', 'suburbext3', 'calib3', 'subpr3', '_dummy', '_dummy', '_dummy', 'subbr3'],
                        [float, float, float, float, float, str, str, str, float], log_errors=True)
