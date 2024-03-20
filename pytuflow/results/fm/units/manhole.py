from typing import TextIO

from ._unit import Handler


SUB_UNIT_NAME = 'MANHOLE'


class Manhole(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.labels = []
        # TODO read other properties
        self.valid = True
        self.type = 'component'

    def __repr__(self) -> str:
        return f'<Manhole {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self.labels = self.read_line(True)
        self.id = self.labels[0]
        self.uid = f'MANHOLE__{self.id}'
        return buf


AVAILABLE_CLASSES = [Manhole]
