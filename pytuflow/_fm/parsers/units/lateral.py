from typing import TextIO

from .handler import Handler


class Lateral(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'lateral'
        self.revision = 1
        self.dist_method = ''
        self.nunit = 0
        self.unit_labels = []
        self._labeltmp = ''
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'LATERAL'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self.revision = self._get_revision()
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self.uid = self._get_uid()
        self._set_attrs_str(self.read_line(), ['dist_method'], log_errors=True)
        self._set_attrs_int(self.read_line(), ['nunit'], log_errors=True)
        for i in range(self.nunit):
            self._set_attrs_str(self.read_line(True), ['_labeltmp'], log_errors=True)
            self.unit_labels.append(self._labeltmp)
