from typing import TextIO

from .handler import Handler


class Junction(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'junction'
        self.connections = []
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'JUNCTION'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['sub_type'], log_errors=True)
        self.connections = self.read_line(True)
        for i, conn_id in enumerate(self.connections.copy()):
            conn_id = conn_id.replace('\\', '').replace('/', '')
            self.connections[i] = conn_id
        self.id = self.connections[0]
        self.uid = self._get_uid()
