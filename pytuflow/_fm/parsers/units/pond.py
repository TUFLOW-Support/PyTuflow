import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler, SubHandler


class Pond(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'component'
        self.headers = ['level', 'area']
        self.ncol = len(self.headers)
        self.storage = pd.DataFrame()
        self.title = ''
        self.ups_label = None
        self.dns_label = None
        self.n = 0
        self.nstruct = 0
        self.noutflow = 0
        self._outflow_type = ''
        self.outflows = []
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'POND'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self.title = line.split('POND')[1].strip()
        self._set_attrs_str(self.read_line(), ['sub_type'], log_errors=False)
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label'], log_errors=True)
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs_int(self.read_line(), ['n'], log_errors=True)
        if self.n:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.n, dtype='f4')
            if a.shape != (self.n, self.ncol):
                a = np.reshape(a, (self.n, self.ncol))
            self.storage = pd.DataFrame(a, columns=self.headers)
            self.bed_level = float(str(self.storage.level.min()))
            self.line_no += self.n

        self._set_attrs_int(self.read_line(), ['nstruct'], log_errors=True)
        _ = self.read_line()
        self._set_attrs_int(self.read_line(), ['noutflow'], log_errors=True)
        for i in range(self.noutflow):
            self._set_attrs_str(self.read_line(True), ['_outflow_type'], log_errors=True)
            if self._outflow_type == 'OUTFLOW WEIR':
                self._outflow = OutflowWeir()
            elif self._outflow_type == 'OUTFLOW SLUICE':
                self._outflow = OutflowSluice()
            elif self._outflow_type == 'OUTFLOW RATING':
                self._outflow = OutflowRating()
            else:
                _ = self.read_line()
                self._outflow = None
            if self._outflow:
                self._outflow.load(line, fo, fixed_field_len, line_no)
                self.outflows.append(self._outflow)
                self.line_no = self._outflow.line_no


class OutflowWeir(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cdw = np.nan
        self.bw = np.nan
        self.zcw = np.nan

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_float(self.read_line(), ['cdw', 'bw', 'zcw'], log_errors=True)


class OutflowSluice(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cds = np.nan
        self.as_ = np.nan
        self.zcs = np.nan
        self.ds = np.nan

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_float(self.read_line(), ['cds', 'as_', 'zcs', 'ds'], log_errors=True)


class OutflowRating(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['flow', 'stage']
        self.ncol = len(self.headers)
        self.rating = pd.DataFrame()
        self.n = 0

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_int(self.read_line(), ['n'], log_errors=True)
        if self.n:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.n, dtype='f4')
            if a.shape != (self.n, self.ncol):
                a = np.reshape(a, (self.n, self.ncol))
            self.rating = pd.DataFrame(a, columns=self.headers)
            self.line_no += self.n
