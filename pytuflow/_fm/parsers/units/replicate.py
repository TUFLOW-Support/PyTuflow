from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Replicate(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'unit'
        self.xs = pd.DataFrame()
        self.headers = []
        self.ncol = 0
        self.dz = 0
        self.easting = np.nan
        self.northing = np.nan
        self.spill_1 = None
        self.spill_2 = None
        self.valid = True
        self.populated = False  # has properties been calculated yet?

    @staticmethod
    def unit_type_name() -> str:
        return 'REPLICATE'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['id', 'spill_1', 'spill_2'], log_errors=[0])
        self.uid = self._get_uid()
        self._set_attrs_float(self.read_line(), ['dx', 'dz', 'easting', 'northing'], log_errors=[0, 1])
