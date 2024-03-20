from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'GATED WEIR'


class GatedWeir(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.ups_label = None
        self.dns_label = None
        self.controller_label = None
        self.ctc = np.nan
        self.cgt = np.nan
        self.crev = np.nan
        self.m = np.nan
        self.gtdir = ''
        self.b = np.nan
        self.zc = np.nan
        self.hg = np.nan
        self.bias = ''
        self.omode = ''
        self.opemax = np.nan
        self.opemin = np.nan
        self.clabel = ''
        self.n = 0
        self.rptflag = ''
        self.tm = np.nan
        # TODO read other properties
        self.valid = True
        self.type = 'structure'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self._set_attrs(self.read_line(True), ['ups_label', 'dns_label', 'controller_label'])
        param = self.read_line()
        self._set_attrs_floats(param, ['ctc', 'cgt', 'crev', 'm'])
        self._set_attrs(param, ['gtdir'], 4)
        param = self.read_line()
        self._set_attrs_floats(param, ['b', 'zc', 'hg'])
        self._set_attrs(param, ['bia'], 3)
        param = self.read_line()
        self._set_attrs_floats(param, ['tm'], 1)
        self._set_attrs(param, ['rptflag'], 2)
        param = self.read_line()
        self._set_attrs(param, ['omode', '', '', '', 'clabel'])
        self._set_attrs_floats(param, ['', 'opemax', 'opemin'])
        _ = self.read_line()  # GATE
        self.n = int(self.read_line()[0])
        if self.omode.upper() == 'TIME':
            self.headers = ['time', 'gate_opening']
        elif self.omode.upper().startswith('WATER'):
            self.headers = ['water_level', 'gate_opening']
        elif self.omode.upper() in ['CONTROLLER', 'LOGICAL']:
            self.headers = ['time', 'open_mode', 'gate_opening']
        self.ncol = len(self.headers)
        buf.write(''.join([fo.readline() for _ in range(self.n)]))
        buf.seek(0)
        self.bed_level = self.zc
        self.ups_invert = self.bed_level
        self.dns_invert = self.bed_level
        self.id = self.ups_label
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        return buf


AVAILABLE_CLASSES = [GatedWeir]
