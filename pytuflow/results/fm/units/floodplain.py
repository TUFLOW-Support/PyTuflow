from typing import TextIO

from ._unit import Handler


SUB_UNIT_NAME = 'FLOODPLAIN'


class Floodplain(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = ['x', 'y', 'n']
        self.ncol = len(self.headers)
        self.ups_label = None
        self.dns_label = None
        # TODO read other properties
        self.valid = True
        self.type = 'component'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self.sub_name = self.read_line(True)[0]
        self.ups_label, self.dns_label = self.read_line(True)
        self.id = self.ups_label
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        param = self.read_line()
        n = int(self.read_line()[0])
        buf.write(''.join([fo.readline() for _ in range(n)]))
        buf.seek(0)
        return buf


AVAILABLE_CLASSES = [Floodplain]
