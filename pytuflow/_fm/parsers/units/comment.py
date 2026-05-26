from typing import TextIO

from .handler import Handler


class Comment(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'comment'
        self.n = 0
        self.comments = []
        self.valid = True
    @staticmethod
    def unit_type_name() -> str:
        return 'COMMENT'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_int(self.read_line(), ['n'])
        self.comments = [self.read_line_raw() for _ in range(self.n)]
