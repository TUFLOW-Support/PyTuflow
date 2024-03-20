from typing import TextIO

from ._unit import Handler


SUB_UNIT_NAME = 'BLOCKAGE'


class Blockage(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.ups_label = None
        self.dns_label = None
        # TODO read other properties
        self.valid = True
        self.type = 'component'

    def __repr__(self) -> str:
        return f'<Blockage {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        ids = self.read_line(True)
        self.id = ids[0]
        self.ups_label, self.dns_label = ids[:2]
        self.uid = f'BLOCKAGE__{self.id}'
        return buf


AVAILABLE_CLASSES = [Blockage]
