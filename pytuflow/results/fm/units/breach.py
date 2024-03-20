from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'BREACH'


class Breach(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = ['time', 'x', 'bottom_width', 'breach_level', 'base_depth', 'side_slope', 'breach_type']
        self.ncol = len(self.headers)
        self.ups_label = None
        self.dns_label = None
        self.method = ''
        self.cdw = np.nan
        self.cdo = np.nan
        self.mod_limit = np.nan
        self.interp = ''
        self.fcollapse = np.nan
        self.hb = np.nan
        self.elvmin = np.nan
        self.n = 0
        self.tlag = 0
        self.tm = 1
        self.repeat = ''
        self.trigger_flag = ''
        self.trigger_level = np.nan
        self.shape = ''
        # TODO read other properties
        self.valid = True
        self.type = 'component'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self._set_attrs(self.read_line(True), ['ups_label', 'dns_label'])
        self.id = self.ups_label
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        param = self.read_line()
        self._set_attrs(param, ['method', '', '', '', 'interp', '', '', '', 'shape'])
        self._set_attrs_floats(param, ['', 'cdw', 'cdo', 'mod_limit', '', 'fcollapse', 'hb', 'elvmin'])
        param = self.read_line()
        self._set_attrs(param, ['', '', '', 'repeat', 'trigger_flag'])
        self._set_attrs_floats(param, ['n', 'tlag', 'tm', '', 'trigger_level'])
        self.n = int(self.n)
        buf.write(''.join([fo.readline() for _ in range(self.n)]))
        buf.seek(0)
        return buf


AVAILABLE_CLASSES = [Breach]
