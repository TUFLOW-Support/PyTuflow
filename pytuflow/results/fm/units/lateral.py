from typing import TextIO

from ._unit import Handler


SUB_UNIT_NAME = 'LATERAL'


class Lateral(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.labels = []
        # TODO read other properties
        self.valid = True
        self.type = 'junction'

    def __repr__(self) -> str:
        return f'<LATERAL {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        ids = self.read_line(True)
        self.id = ids[0]
        _ = self.read_line()
        nlabel = int(self.read_line()[0])
        for _ in range(nlabel):
            self.labels.append(self.read_line(True)[0])
        self.uid = f'LATERAL__{self.id}'
        return buf


AVAILABLE_CLASSES = [Lateral]
