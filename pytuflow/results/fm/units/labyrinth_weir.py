from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'LABYRINTH WEIR'


class LabyrinthWeir(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.ups_label = None
        self.dns_label = None
        self.ups_remote_label = None
        self.dns_remote_label = None
        self.p1 = np.nan
        self.alpha = np.nan
        self.w = np.nan
        self.n = 0
        self.b = np.nan
        self.a = np.nan
        self.t = np.nan
        self.zc = np.nan
        self.l = np.nan
        self.cfc = 1
        self.m = np.nan
        self.cdlim = np.nan
        self.l1 = np.nan
        self.d = np.nan
        self.shflag = ''
        # TODO read other properties
        self.valid = True
        self.type = 'structure'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self._set_attrs(self.read_line(True), ['ups_label', 'dns_label', 'ups_remote_label', 'dns_remote_label'])
        self._set_attrs_floats(self.read_line(), ['p1', 'alpha', 'w', 'n', 'b', 'b', 't', 'zc', 'l'])
        param = self.read_line()
        self._set_attrs_floats(param, ['ccf', 'm', 'cdlim', 'l1', 'd'])
        self._set_attrs(param, ['shflag'], 5)
        self.bed_level = self.zc
        self.ups_invert = self.bed_level
        self.dns_invert = self.bed_level
        self.id = self.ups_label
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        return buf


AVAILABLE_CLASSES = [LabyrinthWeir]
