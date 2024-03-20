from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'QH CONTROL'


class QHControl(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = ['discharge', 'level']
        self.ncol = len(self.headers)
        self.ups_label = None
        self.dns_label = None
        self.n = 0
        self.zc = np.nan
        self.m = np.nan
        self.smooth = ''
        # TODO read other properties
        self.valid = True
        self.type = 'structure'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self._set_attrs(self.read_line(True), ['ups_label', 'dns_label'])
        self.id = self.ups_label
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        param = self.read_line()
        self._set_attrs_floats(param, ['zc', 'm'])
        self._set_attrs(param, ['smooth'], 2)
        self.n = int(self.read_line()[0])
        buf.write(''.join([fo.readline() for _ in range(self.n)]))
        buf.seek(0)
        return buf


AVAILABLE_CLASSES = [QHControl]
