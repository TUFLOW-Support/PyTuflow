from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'LOSS'


class Loss(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.ups_label = ''
        self.dns_label = ''
        self.remote_label = ''
        self.kw = ''
        self.k = np.nan
        self.rfmode = ''
        # TODO read other properties
        self.valid = True
        self.type = 'component'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self._set_attrs(self.read_line(True), ['ups_label', 'dns_label', 'remote_label'])
        self.id = self.ups_label
        param = self.read_line()
        self._set_attrs_floats(param, ['k'])
        self._set_attrs(param[1:], ['rfmode'])
        return buf


AVAILABLE_CLASSES = [Loss]