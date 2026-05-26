import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler, SubHandler


id_inc = 0


class WindData(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'boundary'
        self.revision = -1
        self.windmethod = ''
        self.centreline = ''
        self.fpath = ''
        self.rw = np.nan
        self.rair = np.nan
        self.cd = np.nan
        self.nwinds = 0
        self.winds = []

    @staticmethod
    def unit_type_name() -> str:
        return 'SPILL'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        line = self.read_line_raw()
        self.line = line
        self.revision = self._get_revision()
        global id_inc
        id_inc += 1
        self.uid = f'{self.unit_type_name()}_{id_inc}'
        self._set_attrs_str(self.read_line(), ['windmethod', 'centreline'], log_errors=True)
        self.fpath = self.read_line_raw().strip()
        self._set_attrs_float(self.read_line(), ['rw', 'rair', 'cd'], log_errors=True)
        self._set_attrs_int(self.read_line(), ['nwinds'], log_errors=True)
        for i in range(self.nwinds):
            wind = Wind()
            wind.load(self.line, fo, fixed_field_len, line_no)
            self.winds.append(wind)
            self.line_no = wind.line_no


class Wind(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['Wind Speed', 'Bearing', 'Time', 'Date']
        self.ncol = len(self.headers)
        self.table = pd.DataFrame()
        self.nd_headers = ['Node1', 'Node2']
        self.ncol_nds = len(self.nd_headers)
        self.nodes = pd.DataFrame()
        self.windnod = ''
        self.n = 0
        self.tlag = 0.
        self.tm = 'SECONDS'
        self.repeat = 'NOEXTEND'
        self.smooth = 'LINEAR'
        self.wsmulti = 1.
        self.bearing_type = ''
        self.globflag = ''
        self.nodecount = 0

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(), ['windnod'], log_errors=True)
        self._set_attrs(self.read_line(),
                        ['n', 'tlag', 'tm', 'repeat', 'smooth', 'wsmult', 'bearing_type', 'globflag'],
                        [int, float, str, str, str, float, str, str], log_errors=[0])
        if self.n:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10, 10), max_rows=self.n)
            if a.shape != (self.n, self.ncol):
                a = np.reshape(a, (self.n, self.ncol))
            self.table = pd.DataFrame(a, columns=self.headers)
            self.table[['Wind Speed', 'Bearing', 'Time']] = self.table[['Wind Speed', 'Bearing', 'Time']].astype(float)
            self.line_no += self.n

        _ = self.read_line()
        self._set_attrs_int(self.read_line(), ['nodecount'], log_errors=True)
        if self.nodecount:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.nodecount)
            if a.shape != (self.nodecount, self.ncol_nds):
                a = np.reshape(a, (self.nodecount, self.ncol_nds))
            self.nodes = pd.DataFrame(a, columns=self.nd_headers)
            self.line_no += self.nodecount
