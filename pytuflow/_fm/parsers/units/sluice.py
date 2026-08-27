import logging
import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler, SubHandler


logger = logging.getLogger('pytuflow')


class Sluice(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'structure'
        self.ups_label = None
        self.dns_label = None
        self.remote_label = None
        self.cvw = np.nan
        self.cvg = np.nan
        self.b = np.nan
        self.zc = np.nan
        self.hg = np.nan
        self.l = np.nan
        self.degflg = ''
        self.p1 = np.nan
        self.p2 = np.nan
        self.bias = 0
        self.cvs = np.nan
        self.hp = np.nan
        self.r = np.nan
        self.ngates = 0
        self.wdrown = np.nan
        self.sdrown = np.nan
        self.tdrown = np.nan
        self.tm = 'SECONDS'
        self.rptflg = ''
        self.omode = ''
        self.oprate = np.nan
        self.opemax = np.nan
        self.opemin = np.nan
        self.clabel = ''
        self.gates = []
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'SLUICE'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(), ['sub_type'], log_errors=True)
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label', 'remote_label'], log_errors=[0, 1])
        self.id = self.ups_label
        self.uid = self._get_uid()
        if self.sub_type == 'RADIAL':
            self._sub_obj = RadialSluice(self.parent)
        elif self.sub_type == 'VERTICAL':
            self._sub_obj = VerticalSluice(self.parent)
        self._sub_obj._sync_obj(self)
        if self._sub_obj:
            self._sub_obj.load(line, fo, fixed_field_len, self.line_no)
            self._sync_obj(self._sub_obj)


class RadialSluice(SubHandler):

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs(self.read_line(), ['cvw', 'cvg', 'b', 'zc', 'hg', 'l', 'degflg'],
                        [float, float, float, float, float, float, str], log_errors=True)
        self._set_attrs_float(self.read_line(), ['p1', 'p2', 'bias', 'cvs', 'hp', 'r'], log_errors=True)
        try:
            self.bias = int(self.bias)
        except (ValueError, TypeError):
            logger.error(f'Line No: {self.line_no}: Error reading "bias" as int from parameters')
        self._set_attrs(self.read_line(), ['ngates', 'wdrown', 'sdrown', 'tdrown', 'tm', 'rptflg'],
                        [int, float, float, float, str, str], log_errors=[0])
        self._set_attrs(self.read_line(), ['omode', 'oprate', 'opemax', 'opemin', 'clabel'],
                        [str, float, float, float, str], log_errors=[0])
        for i in range(self.ngates):
            _ = self.read_line()
            gate = None
            if self.omode.upper() in ['WATER1', 'WATER2', 'WATER']:
                gate = SluiceGateWater()
            elif self.omode.upper() == 'TIME':
                gate = SluiceGateTime()
            elif self.omode.upper() in ['CONTROLLER', 'LOGICAL']:
                gate = SluiceGateLogical()
            if gate:
                gate.load(line, fo, fixed_field_len, self.line_no)
                self.line_no = gate.line_no
                self.gates.append(gate)


class VerticalSluice(SubHandler):

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs_float(self.read_line(), ['cvw', 'cvg', 'b', 'zc', 'hg', 'l'], log_errors=True)
        self._set_attrs_float(self.read_line(), ['p1', 'p2', 'bias', 'cvs', 'wdrown', 'sdrown', 'tdrown'],
                              log_errors=[0, 1, 2, 3])
        try:
            self.bias = int(self.bias)
        except (ValueError, TypeError):
            logger.error(f'Line No: {self.line_no}: Error reading "bias" as int from parameters')
        self._set_attrs(self.read_line(), ['ngates', 'tm', 'rptflg'],
                        [int, str, str], log_errors=[0])
        self._set_attrs(self.read_line(), ['omode', 'oprate', 'opemax', 'opemin', 'clabel'],
                        [str, float, float, float, str], log_errors=[0])
        for i in range(self.ngates):
            _ = self.read_line()
            gate = None
            if self.omode.upper() in ['WATER1', 'WATER2', 'WATER']:
                gate = SluiceGateWater(self)
            elif self.omode.upper() == 'TIME':
                gate = SluiceGateTime(self)
            elif self.omode.upper() in ['CONTROLLER', 'LOGICAL']:
                gate = SluiceGateLogical(self)
            if gate:
                gate.load(line, fo, fixed_field_len, self.line_no)
                self.line_no = gate.line_no
                self.gates.append(gate)


class SluiceGate(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.n = 0
        self.headers = []
        self.ncol = 0
        self.gate_operation = pd.DataFrame()

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_int(self.read_line(), ['n'], log_errors=True)
        if self.n:
            a = np.genfromtxt(self.fo, delimiter=[10]*self.ncol, max_rows=self.n)
            if a.shape != (self.n, self.ncol):
                a = np.reshape(a, (self.n, self.ncol))
            self.gate_operation = pd.DataFrame(a, columns=self.headers)
            float_headers = ['Time', 'Opening'] if 'Time' in self.headers else ['Water Level', 'Opening']
            self.gate_operation[float_headers] = self.gate_operation[float_headers].astype(float)
            self.line_no += self.n


class SluiceGateWater(SluiceGate):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['Water Level', 'Opening']
        self.ncol = len(self.headers)


class SluiceGateTime(SluiceGate):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['Time', 'Opening']
        self.ncol = len(self.headers)


class SluiceGateLogical(SluiceGate):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['Time', 'Mode', 'Opening']
        self.ncol = len(self.headers)
