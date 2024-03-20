from typing import TextIO, TYPE_CHECKING
import io

import numpy as np
import pandas as pd

from ._unit import Handler
from ..unpack_fixed_field import unpack_fixed_field

if TYPE_CHECKING:
    from ..gxy import GXY
    from ..dat import Dat


SUB_UNIT_NAME = 'REPLICATE'


class Replicate(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.dz = np.nan
        self.easting = np.nan
        self.northing = np.nan
        self.spill_1 = None
        self.spill_2 = None
        self.valid = True
        self.type = 'unit'
        self.populated = False

    def __repr__(self) -> str:
        return f'<Replicate {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        ids = self.read_line(True)
        self.id = ids[0]
        self.uid = f'REPLICATE__{self.id}'
        self._assign_other_labels(ids)
        attrs = self.read_line()
        for i, attr in enumerate(['dx', 'dz', 'easting', 'northing']):
            try:
                setattr(self, attr, float(attrs[i].strip()))
            except (ValueError, IndexError):
                if i < 2:
                    self.errors.append(f'Error reading {attr} for {self.id}')
        return buf

    def _assign_other_labels(self, labels: list[str]) -> None:
        for i, attr in enumerate(['spill_1', 'spill_2']):
            j = i + 1  # first label is id
            if j < len(labels):
                setattr(self, attr, labels[j])


AVAILABLE_CLASSES = [Replicate]
