from typing import TextIO

from ._unit import Handler


SUB_UNIT_NAME = 'ORIFICE'


class Orifice(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.ups_label = None
        self.dns_label = None
        # TODO read other properties
        self.valid = True
        self.type = 'structure'

    def __repr__(self) -> str:
        return f'<{SUB_UNIT_NAME} {self.sub_name} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self.sub_name = self.read_line(True)[0]
        self.ups_label, self.dns_label = self.read_line(True)
        self.id = self.ups_label
        self.bed_level = float(self.read_line()[0])
        self.ups_invert = self.bed_level
        self.dns_invert = self.bed_level
        self.uid = f'{self.__class__.__name__}_{self.sub_name}_{self.id}'
        return buf


AVAILABLE_CLASSES = [Orifice]
