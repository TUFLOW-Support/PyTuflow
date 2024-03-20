from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'WEIR'


class Weir(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.ups_label = None
        self.dns_label = None
        self.cd = np.nan
        self.cv = np.nan
        self.b = np.nan
        self.zc = np.nan
        self.m = np.nan
        self.e = np.nan
        # TODO read other properties
        self.valid = True
        self.type = 'structure'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self._set_attrs(self.read_line(True), ['ups_label', 'dns_label'])
        self._set_attrs_floats(self.read_line(), ['e'])
        self._set_attrs_floats(self.read_line(), ['cd', 'cv', 'b', 'zc', 'm'])
        self.bed_level = self.zc
        self.ups_invert = self.bed_level
        self.dns_invert = self.bed_level
        self.id = self.ups_label
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        return buf


AVAILABLE_CLASSES = [Weir]
