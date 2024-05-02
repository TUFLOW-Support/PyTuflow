from typing import TextIO

from ._unit import Handler


SUB_UNIT_NAME = 'FSSR16BDY'


class Fssr16bdy(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        # TODO read other properties
        self.valid = True
        self.type = 'boundary'

    def __repr__(self) -> str:
        return f'<FSSR16BDY {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        ids = self.read_line(True)
        self.id = ids[0]
        self.uid = f'FSSR16BDY__{self.id}'
        return buf


AVAILABLE_CLASSES = [Fssr16bdy]