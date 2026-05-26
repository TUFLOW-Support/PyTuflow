import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Abstraction(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'component'
        self.rules = []
        self.headers = []
        self.ncol = 0
        self.abstraction = pd.DataFrame()
        self.ups_label = None
        self.dns_label = None
        self.swtype = ''
        self.clabel = ''
        self.ndat = 0
        self.tlag = 0.
        self.tm = 'SECONDS'
        self.rptflag = ''
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'ABSTRACTION'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label'], log_errors=[0])
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs_str(self.read_line(), ['swtype', 'clabel'], log_errors=[0])
        self._set_attrs(self.read_line(), ['ndat', 'tlag', 'tm', 'rptflag'], [int, float, str, str], log_errors=[0])
        if self.swtype.upper() == 'TIME':
            self.headers = ['time', 'abstraction']
        elif self.swtype.upper() == 'LOGICAL':
            self.headers = ['time', 'opmode', 'abstraction']
        self.ncol = len(self.headers)
        if self.ncol:
            a = np.genfromtxt(self.fo, delimiter=(10,10,10), max_rows=self.ndat)
            if a.shape != (self.ndat, len(self.headers)):
                a = np.reshape(a, (self.ndat, len(self.headers)))
            self.abstraction = pd.DataFrame(a, columns=self.headers)
            self.abstraction[['time', 'abstraction']] = self.abstraction[['time', 'abstraction']].astype(float)
            self.line_no += self.ndat

        if self.swtype.upper() == 'LOGICAL':
            self.read_rule_block()

    def read_rule_block(self) -> None:
        self.rules = []
        pass  # TODO capture rules from rule block
