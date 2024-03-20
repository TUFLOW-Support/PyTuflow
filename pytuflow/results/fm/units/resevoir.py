from typing import TextIO

import pandas as pd

from ._unit import Handler


SUB_UNIT_NAME = 'RESEVOIR'


class Resevoir(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.labels = []
        self.lateral_inflows = []
        # TODO read other properties
        self.valid = True
        self.type = 'component'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self.labels = self.read_line(True, 100)
        self.id = self.labels[0]
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        if '#revision1#1' in line:
            self.lateral_inflows = self.read_line(True)
        n = int(self.read_line()[0])
        buf.write(''.join([fo.readline() for _ in range(n)]))
        buf.seek(0)
        return buf

    def post_load(self, df: pd.DataFrame) -> 'Handler':
        self.df = df
        self.bed_level = df.iloc[0, 0]
        self.ups_invert = df.iloc[0, 1]
        self.dns_invert = df.iloc[0, 2]
        return self


AVAILABLE_CLASSES = [Resevoir]
