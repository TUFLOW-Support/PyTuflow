from typing import TextIO

import numpy as np
import pandas as pd
from uuid import uuid4

from ._unit import Unit
from ..unpack_fixed_field import unpack_fixed_field


class River(Unit):

    def __init__(self, fo: TextIO, fixed_field_len: int) -> None:
        self.headers = ['x', 'y', 'n', 'rel_path_len', 'chan_marker', 'easting', 'northing', 'deactivation_marker', 'sp_marker']
        super().__init__(fo, fixed_field_len)

    def __repr__(self) -> str:
        return f'<River {self._id}>'

    @property
    def id(self) -> str:
        if self._id:
            return f'RIVER_SECTION_{self._id}'
        return f'RIVER_SECTION_UNKOWN_{uuid4()}'

    def _load(self, fo: TextIO, fixed_field_len: int) -> None:
        _ = fo.readline()  # SECTION
        self._id = unpack_fixed_field(fo.readline(), [fixed_field_len]*7)[0].strip()
        self.dx = float(unpack_fixed_field(fo.readline(), [fixed_field_len]*7)[0].strip())
        try:
            n = int(fo.readline())
        except ValueError:
            return
        self.df = pd.read_fwf(fo, widths=[10]*9, names=self.headers, nrows=n)
        if self.df['rel_path_len'].dtype == np.float64:
            self.df['path_marker'] = ['' for _ in range(n)]
        else:
            self.df[['path_marker', 'rel_path_len']] = self.df['rel_path_len'].str.split(' ', n=1, expand=True)
            self.df['rel_path_len'] = np.where(self.df['path_marker'] != '*', self.df.path_marker, self.df.rel_path_len)
            self.df['path_marker'] = np.where(self.df['path_marker'] == '*', self.df.path_marker, '')
