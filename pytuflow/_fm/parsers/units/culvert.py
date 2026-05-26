import io
from typing import TextIO

import numpy as np

from .handler import Handler, SubHandler


class Culvert(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'component'
        self.ups_label = None
        self.dns_label = None
        self.ups_label_ref = None
        self.dns_label_ref = None
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'CULVERT'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['sub_type'], log_errors=True)
        if self.sub_type == 'INLET':
            self._sub_obj = CulvertInlet(self.parent)
        elif self.sub_type == 'OUTLET':
            self._sub_obj = CulvertOutlet(self.parent)
        elif self.sub_type == 'BEND':
            self._sub_obj = CulvertBend(self.parent)
        self._sync_obj(self._sub_obj)
        self._set_attrs_str(self.read_line(True),  ['ups_label', 'dns_label', 'ups_label_ref', 'dns_label_ref'],
                            log_errors=[0, 1])
        self.id = self.ups_label
        self.uid = self._get_uid()
        if self._sub_obj:
            self._sub_obj._sync_obj(self)
            self._sub_obj.load(line, fo, fixed_field_len, self.line_no)
            self._sync_obj(self._sub_obj)


class CulvertInlet(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.k = np.nan
        self.m = np.nan
        self.c = np.nan
        self.y = np.nan
        self.ki = np.nan
        self.ctype = ''
        self.ws = np.nan
        self.r = np.nan
        self.b = np.nan
        self.ks = np.nan
        self.rfmode = ''
        self.headwd = ''
        self.height = np.nan

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs(self.read_line(), ['k', 'm', 'c', 'y', 'ki', 'ctype'],
                       [float, float, float, float, float, str], log_errors=True)
        self._set_attrs(self.read_line(), ['ws', 'r', 'b', 'ks', 'rfmode', 'headwd', 'height'],
                        [float, float, float, float, str, str, float], log_errors=[0, 1, 2, 3, 4, 5])


class CulvertOutlet(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.ko = np.nan
        self.rfmode = ''
        self.headwd = ''

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs(self.read_line(), ['ko', 'rfmode', 'headwd'], [float, str, str], log_errors=True)


class CulvertBend(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = ''
        self.kb = np.nan
        self.rfmode = ''

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs_str(self.read_line(), ['keyword'], log_errors=True)
        self._set_attrs(self.read_line(), ['kb', 'rfmode'], [float, str], log_errors=True)
