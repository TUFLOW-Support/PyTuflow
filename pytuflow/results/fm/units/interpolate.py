from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'INTERPOLATE'


class Interpolate(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.easting = np.nan
        self.northing = np.nan
        self.spill_1 = None
        self.spill_2 = None
        self.valid = True
        self.type = 'unit'
        self.populated = False

    def __repr__(self) -> str:
        return f'<Interpolate {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        ids = self.read_line(True)
        self.id = ids[0]
        self.uid = f'INTERPOLATE__{self.id}'
        self._assign_other_labels(ids)
        attrs = self.read_line()
        for i, attr in enumerate(['dx', 'easting', 'northing']):
            try:
                setattr(self, attr, float(attrs[i].strip()))
            except (ValueError, IndexError):
                if i == 0:
                    self.errors.append(f'Error reading {attr} for {self.id}')
        return buf

    def _assign_other_labels(self, labels: list[str]) -> None:
        for i, attr in enumerate(['spill_1', 'spill_2']):
            j = i + 1  # first label is id
            if j < len(labels):
                setattr(self, attr, labels[j])


AVAILABLE_CLASSES = [Interpolate]
