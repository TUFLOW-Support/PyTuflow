import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler


class Reservoir(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'junction'
        self.headers = ['Elevation', 'Plan Area']
        self.ncol = len(self.headers)
        self.rating = pd.DataFrame()
        self.connections = []
        self.lateral_inflows = []
        self.revision = -1
        self.n = 0
        self.easting = np.nan
        self.northing = np.nan
        self.runoff = np.nan
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'RESERVOIR'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self.revision = self._get_revision()
        self.connections = self.read_line(True, 100)
        self.id = self.connections[0]
        self.uid = self._get_uid()
        if self.revision == 1:
            self.lateral_inflows = self.read_line(True)
        self._set_attrs_int(self.read_line(), ['n'], log_errors=True)
        if self.n:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.n, dtype='f4')
            if a.shape != (self.n, self.ncol):
                a = np.reshape(a, (self.n, self.ncol))
            self.rating = pd.DataFrame(a, columns=self.headers)
            self.line_no += self.n

        if self.revision == 1:
            self._set_attrs_float(self.read_line(), ['easting', 'northing', 'runoff'])
