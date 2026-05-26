from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Interpolate(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'unit'
        self.xs = pd.DataFrame()
        self.headers = []
        self.ncol = 0
        self.dx = 0
        self.easting = np.nan
        self.northing = np.nan
        self.spill_1 = None
        self.spill_2 = None
        self.valid = True
        self.populated = False

    @staticmethod
    def unit_type_name() -> str:
        return 'INTERPOLATE'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['id', 'spill_1', 'spill_2'], log_errors=[0])
        self.uid = self._get_uid()
        self._set_attrs_float(self.read_line(), ['dx', 'easting', 'northing'], log_errors=[0])
