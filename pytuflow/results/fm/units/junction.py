from typing import TextIO

from ._unit import Handler


SUB_UNIT_NAME = 'JUNCTION'


class Junction(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = 'JUNCTION'
        self.headers = []
        self.ncol = 0
        self.connections = []
        self.valid = True
        self.type = 'junction'

    def __repr__(self) -> str:
        return f'<Junction {self.sub_name} {", ".join(self.connections)}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self.sub_name = self.read_line()[0]  # OPEN
        self.connections = self.read_line(True)
        self.id = self.connections[0]
        self.uid = f'JUNCTION_{self.sub_name}_{self.id}'
        return buf


AVAILABLE_CLASSES = [Junction]
