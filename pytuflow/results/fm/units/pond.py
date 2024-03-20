from typing import TextIO

import pandas as pd

from ._unit import Handler


SUB_UNIT_NAME = 'POND'


class Pond(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = ['level', 'area']
        self.ncol = len(self.headers)
        self.ups_label = None
        self.dns_label = None
        # TODO read other properties
        self.valid = True
        self.type = 'unit'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        _ = self.read_line()  # ONLINE
        ids = self.read_line(True)
        self.id = ids[0]
        self.ups_label, self.dns_label = ids
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        n = int(self.read_line()[0])
        buf.write(''.join([fo.readline() for _ in range(n)]))
        buf.seek(0)
        return buf

    def post_load(self, df: pd.DataFrame) -> 'Handler':
        self.df = df
        self.bed_level = df['level'].values[0]
        self.ups_invert = self.bed_level
        self.dns_invert = self.bed_level
        return self


AVAILABLE_CLASSES = [Pond]
