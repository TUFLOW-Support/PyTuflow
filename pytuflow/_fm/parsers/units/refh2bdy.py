import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Refh2bdy(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'hydrology'
        self.ifd_headers = []
        self.ncol_ifd = 0
        self.ifd = pd.DataFrame()
        self.rainfall = pd.DataFrame()
        self.minrev = np.nan
        self.refh2version = ''
        self.z = np.nan
        self.easting = np.nan
        self.northing = np.nan
        self.ngr = ''
        self.t = np.nan
        self.d = np.nan
        self.dt = np.nan
        self.season = ''
        self.urbanised = ''
        self.plotscale = ''
        self.override = ''
        self.desctype = ''
        self.ccuplift = np.nan
        self.xmlflag = ''
        self.xmlfile = ''
        self.reportflag = ''
        self.reportfolder = ''
        self.carea = np.nan
        self.country = ''
        self.saar = np.nan
        self.urbext2000 = np.nan
        self.ddfmethod = ''
        self.c = np.nan
        self.d1 = np.nan
        self.d2 = np.nan
        self.d3 = np.nan
        self.e = np.nan
        self.f = np.nan
        self.dplbar = np.nan
        self.dbpsbar = np.nan
        self.propwet = np.nan
        self.bfihost = np.nan
        self.bfihost19 = np.nan
        self.tdelay = 0.
        self.bfonly = ''
        self.scflag = ''
        self.scfact = np.nan
        self.hymode = ''
        self.scaling = ''
        self.minflow = -9e29
        self.altbar = np.nan
        self.aspbar = np.nan
        self.aspvar = ''
        self.farl = np.nan
        self.fpext = np.nan
        self.fpdbar = np.nan
        self.fploc = ''
        self.ldp = np.nan
        self.rmed_1h = np.nan
        self.rmed_1d = np.nan
        self.rmed_2d = np.nan
        self.saar4170 = np.nan
        self.sprhost = np.nan
        self.urbconc2000 = np.nan
        self.urbloc2000 = ''
        self.urbext1990 = np.nan
        self.urbconc1990 = np.nan
        self.urbloc1990 = ''
        self.c_1km = np.nan
        self.d1_1km = np.nan
        self.d2_1km = np.nan
        self.d3_1km = np.nan
        self.e_1km = np.nan
        self.f_1km = np.nan
        self.usescf = ''
        self.usearf = ''
        self.usesc = ''
        self.useeda = ''
        self.useurbanarea = ''
        self.useirf = ''
        self.useif = ''
        self.usetpscaling = ''
        self.useds = ''
        self.scf = np.nan
        self.arf = np.nan
        self.sc = np.nan
        self.eda = np.nan
        self.urbanarea = np.nan
        self.irf = np.nan
        self.if_ = np.nan
        self.tpscaling = np.nan
        self.ds = np.nan
        self.mddf2013d = 0
        self.nddf2013t = 0
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'REFH2BDY'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self.uid = self._get_uid()
        self._set_attrs(self.read_line(), ['minrev', 'refhversion'], [float, str])
        self._set_attrs_float(self.read_line(), ['z', 'easting', 'northing'])
        self._set_attrs(self.read_line(),
                        ['t', 'd', 'dt', 'season', 'urbanised', 'plotscale', 'override', 'desctype', 'ccuplift'],
                        [float, float, float, str, str, str, str, str, float])
        self._set_attrs_str(self.read_line(), ['xmlflag'])
        self._set_attrs_str(self.read_line(), ['xmlfile'])
        self._set_attrs_str(self.read_line(), ['reportflag'])
        self._set_attrs_str(self.read_line(), ['reportfolder'])
        self._set_attrs(self.read_line(), ['carea', 'country', 'saar', 'urbext2000'],
                        [float, str, float, float])
        self._set_attrs(self.read_line(), ['ddfmethod', 'c', 'd1', 'd2', 'd3', 'e', 'f'],
                        [str, float, float, float, float, float, float])
        self._set_attrs_float(self.read_line(), ['dplbar', 'dbpsbar', 'propwet', 'bfihost', 'bfihost19'])
        self._set_attrs(self.read_line(), ['tdelay', 'bfonly', 'scflag', 'scfact', 'hymode', 'scaling', 'minflow'],
                        [float, str, str, float, str, str, float])
        self._set_attrs(self.read_line(), ['altbar', 'aspbar', 'aspvar', 'farl', 'fpext', 'fpdbar', 'fploc', 'ldp'],
                        [float, float, float, float, float, float, str, float])
        self._set_attrs(self.read_line(),
                        ['rmed_1h', 'rmed_1d', 'rmed_2d', 'saar4170', 'sprhost', 'urbconc2000', 'urbloc2000'],
                        [float, float, float, float, float, float, str])
        self._set_attrs(self.read_line(), ['urbext1990', 'urbconc1990', 'urbloc1990'],
                        [float, float, str])
        self._set_attrs_float(self.read_line(), ['c_1km', 'd1_1km', 'd2_1km', 'd3_1km', 'e_1km', 'f_1km'])
        if self.minrev >= 5.1:
            self._set_attrs_str(self.read_line(),
                                ['usescf', 'usearf', 'usesc', 'useeda', 'useurbanarea', 'useirf', 'useif', 'usetpscaling', 'useds'])
            self._set_attrs_float(self.read_line(), ['scf', 'arf', 'sc', 'eda', 'urbanarea', 'irf', 'if_', 'tpscaling', 'ds'])
            self._set_attrs_int(self.read_line(), ['mddf2013d', 'nddf2013t'])
            if self.mddf2013d > 0 and self.nddf2013t > 0:
                self.ifd_header = self.read_line(data_length=self.nddf2013t)
                self.ifd_header.insert(0, 'duration')
                self.ncol_ifd = self.nddf2013t
                if self.mddf2013d > 0:
                    a = np.genfromtxt(self.fo, delimiter=[10] * self.ncol_ifd, max_rows=self.mddf2013d, dtype='f4')
                    if a.shape != (self.mddf2013d, self.ncol_ifd):
                        a = np.reshape(a, (self.mddf2013d, self.ncol_ifd))
                    self.ifd = pd.DataFrame(a, columns=self.ifd_header)
                    self.ifd.set_index('duration', inplace=True)
                    self.line_no += self.mddf2013d
