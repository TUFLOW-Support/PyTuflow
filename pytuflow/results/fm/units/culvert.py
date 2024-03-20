import io
from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'CULVERT'


class Culvert(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.ups_label = None
        self.dns_label = None
        self.ups_ref = None
        self.dns_ref = None
        # TODO read other properties
        self.valid = True
        self.type = 'component'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.sub_name} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self.sub_name = self.read_line(True)[0]
        self._set_attrs(self.read_line(True), ['ups_label', 'dns_label', 'ups_ref', 'dns_ref'])
        self.id = self.ups_label
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        if self.sub_name == 'INLET':
            self._sub_obj = CulvertInlet()
        elif self.sub_name == 'OUTLET':
            self._sub_obj = CulvertOutlet()
        elif self.sub_name == 'BEND':
            self._sub_obj = CulvertBend()
        if self._sub_obj:
            return self._load_sub_class(self._sub_obj, line, fo, fixed_field_len)
        return buf


class CulvertInlet(Culvert):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.k = np.nan
        self.m = np.nan
        self.c = np.nan
        self.y = np.nan
        self.ki = np.nan
        self.e = np.nan
        self.ws = np.nan
        self.r = np.nan
        self.fb = np.nan
        self.ks = np.nan
        self.height = np.nan
        self.rfmode = ''
        self.headwd = ''

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.sub_name} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO()
        self._set_attrs_floats(self.read_line(), ['k', 'm', 'c', 'y', 'ki', 'e'])
        param = self.read_line()
        self._set_attrs_floats(param, ['ws', 'r', 'fb', 'ks'])
        self.rfmode = param[3]
        self.headwd = param[4]
        self._set_attrs_floats(param[5:], ['height'])
        return buf


class CulvertOutlet(Culvert):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.ko = np.nan
        self.rfmode = ''
        self.headwd = ''

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.sub_name} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO()
        param = self.read_line()
        self._set_attrs_floats(param[:1], ['ko'])
        self.rfmode = param[1]
        self.headwd = param[2]
        return buf


class CulvertBend(Culvert):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.kb = np.nan
        self.rfmode = ''

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.sub_name} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO()
        param = self.read_line()
        self._set_attrs_floats(param[:1], ['kb'])
        self.rfmode = param[1]
        return buf


AVAILABLE_CLASSES = [Culvert]
