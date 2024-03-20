from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'SPILL'


class Spill(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = ['x', 'y']
        self.ncol = len(self.headers)
        self.ups_label = None
        self.dns_label = None
        self.cd = np.nan
        self.mod_limit = np.nan
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
        self._set_attrs_floats(self.read_line(), ['cd', 'mod_limit'])
        self.n = int(self.read_line()[0])
        buf.write(''.join([fo.readline() for _ in range(self.n)]))
        buf.seek(0)
        return buf

    def post_load(self, df):
        self.df = df
        self.bed_level = df.min().y
        self.ups_invert = self.bed_level
        self.dns_invert = self.bed_level
        return self


AVAILABLE_CLASSES = [Spill]
