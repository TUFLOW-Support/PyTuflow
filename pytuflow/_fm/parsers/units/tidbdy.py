import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler



class Tidbdy(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'boundary'
        self.surge_headers = ['Start Time', 'Duration', 'Amplitude', 'Cosine Power']
        self.ncol_surge = len(self.surge_headers)
        self.surges = pd.DataFrame()
        self.rise_headers = ['Year', 'Rate']
        self.ncol_rise = len(self.rise_headers)
        self.rises = pd.DataFrame()
        self.tide_headers = ['Amplitude', 'Phase']
        self.ncol_tide = len(self.tide_headers)
        self.tides = pd.DataFrame()
        self.z = 0.
        self.nsurges = 0
        self.nrises = 0
        self.x0 = np.nan
        self.hour = np.nan
        self.idat = 0
        self.iy = 0
        self.tidbdy_dates = 0
        self.nh = 0
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'TIDBDY'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self.uid = self._get_uid()
        self._set_attrs_int(self.read_line(), ['nsurges', 'nrises'], log_errors=True)
        if self.nsurges:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10, 10), max_rows=self.nsurges, dtype='f4')
            if a.shape != (self.nsurges, self.ncol_surge):
                a = np.reshape(a, (self.nsurges, self.ncol_surge))
            self.surges = pd.DataFrame(a, columns=self.surge_headers)
            self.line_no += self.nsurges
        else:
            _ = self.read_line()  # according to manual line must be repeated once
            buf = io.StringIO()

        self._set_attrs_float(self.read_line(), ['x0'], log_errors=True)
        self._set_attrs(self.read_line(), ['hour', 'idat', 'iy', 'tidbdy_dates'], [float, int, int, int],
                        log_errors=True)
        self._set_attrs_int(self.read_line(), ['nh'], log_errors=True)
        if self.nh:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.nh, dtype='f4')
            if a.shape != (self.nh, self.ncol_tide):
                a = np.reshape(a, (self.nh, self.ncol_tide))
            self.tides = pd.DataFrame(a, columns=self.tide_headers)
            self.line_no += self.nh
        if self.nrises:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.nrises)
            if a.shape != (self.nrises, self.ncol_rise):
                a = np.reshape(a, (self.nrises, self.ncol_rise))
            self.rises = pd.DataFrame(a, columns=self.rise_headers)
            self.rises[['Year']] = self.rises[['Year']].astype(int)
            self.rises[['Rate']] = self.rises[['Rate']].astype(float)
            self.line_no += self.nrises
