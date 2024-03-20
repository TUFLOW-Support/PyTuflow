from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'GAUGE'


class Gauge(Handler):

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
        self.id = self.read_line(True)[0]
        return buf


AVAILABLE_CLASSES = [Gauge]