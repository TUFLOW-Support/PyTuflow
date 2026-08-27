from typing import TextIO

import numpy as np

from .handler import Handler


class LabyrinthWeir(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'structure'
        self.ups_label = None
        self.dns_label = None
        self.ups_remote_label = None
        self.dns_remote_label = None
        self.p1 = 0.
        self.alpha = np.nan
        self.w = np.nan
        self.n = 0
        self.b = 0.
        self.a = 0.
        self.t = 0.
        self.zc = np.nan
        self.l = np.nan
        self.ccf = 1.
        self.m = 0.
        self.cdlim = 0.
        self.l1 = np.nan
        self.d = 0.
        self.shflag = ''
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'LABYRINTH'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True),
                            ['ups_label', 'dns_label', 'ups_remote_label', 'dns_remote_label'], log_errors=[0, 1])
        self.id = self.ups_label
        self.uid = f'LABYRINTH WEIR__{self.id}'
        self._set_attrs_float(self.read_line(), ['p1', 'alpha', 'w', 'n', 'b', 'a', 't', 'zc', 'l'],
                              log_errors=[1, 2, 7, 8])
        self._set_attrs(self.read_line(), ['ccf', 'm', 'cdlim', 'l1', 'd', 'shflag'],
                        [float, float, float, float, float, str], log_errors=[3])
        self.bed_level = self.zc
