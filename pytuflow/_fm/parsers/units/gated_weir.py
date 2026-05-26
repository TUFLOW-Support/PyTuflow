import logging
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler
from .sluice import SluiceGateWater, SluiceGateLogical, SluiceGateTime


logger = logging.getLogger('pytuflow')


class GatedWeir(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'structure'
        self.gate = None
        self.ups_label = None
        self.dns_label = None
        self.remote_label = None
        self.ctc = np.nan
        self.cgt = np.nan
        self.crev = np.nan
        self.m = np.nan
        self.gtdir = ''
        self.b = np.nan
        self.zc = np.nan
        self.hg = np.nan
        self.bias = 0
        self.omode = ''
        self.oprate = np.nan
        self.opemax = np.nan
        self.opemin = np.nan
        self.clabel = ''
        self.n1 = 0
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'GATED WEIR'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label', 'remote_label'], log_errors=[0, 1])
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs(self.read_line(), ['ctc', 'cgt', 'crev', 'm', 'gtdir'],
                        [float, float, float, float, str])
        self._set_attrs_float(self.read_line(), ['b', 'zc', 'hg', 'bias'], log_errors=[0, 1])
        try:
            self.bias = int(self.bias)
        except (ValueError, TypeError):
            logger.error(f'Line No: {self.line_no}: Error reading "bias" as int from parameters')
        self._set_attrs_str(self.read_line(), ['tm', 'rptflag'], ind=1)
        self._set_attrs(self.read_line(), ['omode', 'oprate', 'opemax', 'opemin', 'clabel'],
                        [str, float, float, float, str], log_errors=[0])
        _ = self.read_line()
        if self.omode.upper() in ['WATER1', 'WATER2', 'WATER3']:
            self.gate = WeirGateWater(self)
        elif self.omode.upper() == 'TIME':
            self.gate = WeirdGateTime(self)
        elif self.omode.upper() in ['CONTROLLER', 'LOGICAL']:
            self.gate = WeirGateLogical(self)
        if self.gate:
            self.gate.load(line, fo, fixed_field_len, self.line_no)
            self.line_no = self.gate.line_no
        self.bed_level = self.zc


class WeirGateWater(SluiceGateWater):
    pass


class WeirdGateTime(SluiceGateTime):
    pass


class WeirGateLogical(SluiceGateLogical):
    pass
