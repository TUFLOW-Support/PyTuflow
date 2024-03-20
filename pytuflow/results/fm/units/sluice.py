import io
from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'SLUICE'


class Sluice(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.ups_label = None
        self.dns_label = None
        self.remote_label = None
        self.cvw = np.nan
        self.cvg = np.nan
        self.b = np.nan
        self.zc = np.nan
        self.hg = np.nan
        self.length = np.nan
        self.degflg = ''
        self.allow_free_flow = False
        self.p1 = np.nan
        self.p2 = np.nan
        self.bias_factor = np.nan
        self.cvs = np.nan
        self.hp = np.nan
        self.r = np.nan
        self.ngates = 0
        self.calc_method = ''
        self.wdrown = np.nan
        self.sdrown = np.nan
        self.tdrown = np.nan
        self.control_method = ''
        self.oprate = np.nan
        self.opemax = np.nan
        self.opemin = np.nan
        self.clabel = ''
        self.dum = np.nan
        self.time = np.nan
        self.yo = np.nan
        self.rptflag = ''
        self.opmode = ''
        # TODO read other properties
        self.valid = True
        self.type = 'structure'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.sub_name} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self.sub_name = self.read_line(True)[0]
        self._set_attrs(self.read_line(True), ['ups_label', 'dns_label', 'remote_label'])
        self.id = self.ups_label
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        if self.sub_name == 'RADIAL':
            self._sub_obj = RadialSluice()
        elif self.sub_name == 'VERTICAL':
            self._sub_obj = VerticalSluice()
        if self._sub_obj:
           return self._load_sub_class(self._sub_obj, line, fo, fixed_field_len)
        return buf


class RadialSluice(Sluice):

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO()
        param = self.read_line()
        self._set_attrs_floats(param, ['cvw', 'cvg', 'b', 'zc', 'hg', 'length'])
        self.bed_level = self.zc
        self.ups_invert = self.zc
        self.dns_invert = self.zc
        self._set_attrs(param, ['degflg'], 6)
        self._set_attrs_floats(self.read_line(), ['p1', 'p2', 'bias_factor', 'cvs', 'hp', 'r'])
        param = self.read_line()
        self.ngates = int(param[0])
        self._set_attrs_floats(param, ['wdrown', 'sdrown', 'tdrown', 'time'], 1)
        self.rptflag = self._set_attrs(param, ['rptflag'], 5)
        param = self.read_line()
        self._set_attrs(param, ['control_method', '', '', '',  'clabel'])
        self._set_attrs_floats(param, ['oprate', 'opemax', 'opemin'], 1)
        return buf


class VerticalSluice(Sluice):

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO()
        param = self.read_line()
        self._set_attrs_floats(param, ['cvw', 'cvg', 'b', 'zc', 'hg', 'length'])
        self.bed_level = self.zc
        self.ups_invert = self.zc
        self.dns_invert = self.zc
        self._set_attrs_floats(self.read_line(), ['p1', 'p2', 'bias_factor', 'wdrown', 'sdrown', 'tdrown'])
        param = self.read_line()
        self.ngates = int(param[0])
        self._set_attrs_floats(param, ['time'], 1)
        self._set_attrs(param, ['rptflag'], 5)
        param = self.read_line()
        self._set_attrs(param, ['control_method', '', '', '',  'clabel'])
        self._set_attrs_floats(param, ['oprate', 'opemax', 'opemin'], 1)
        return buf


AVAILABLE_CLASSES = [Sluice]
