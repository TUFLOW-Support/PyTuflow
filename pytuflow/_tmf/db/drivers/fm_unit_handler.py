import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from ...utils.unpack_fixed_field import unpack_fixed_field


class Handler:
    """Abstract base class for all unit handlers."""

    def __init__(self, *args, **kwargs) -> None:
        """keyword should be overridden by subclass. No arguments should be passed to this method."""
        super().__init__()
        self.fo = None
        self.fixed_field_len = 0
        self.keyword = ''
        self.sub_name = ''
        self.ncol = 0
        self.headers = []
        self.df = None  # populated in post_load method
        self.id = None  # id of the unit (populated in load method)
        self.uid = None  # id of the unit but includes the type which then creates a unique id (e.g. RIVER_SECTION_{id})
        self.dx = np.nan  # populated in load method
        self.bed_level = np.nan
        self.ups_invert = np.nan
        self.dns_invert = np.nan
        self.errors = []
        self.ups_units = []
        self.dns_units = []
        self.ups_link_ids = []
        self.dns_link_ids = []
        self.ups_junc = None
        self.dns_junc = None
        self.valid = False
        self.type = 'unknown'
        self.connections = []
        self.dz = np.nan
        self._sub_obj = None

    def __repr__(self) -> str:
        return f'<Unit {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        """
        Set the id, uuid, ncol, and headers and any other attributes.
        Return a string buffer object containing the data to be read by pandas.
        """
        self.fo = fo
        self.fixed_field_len = fixed_field_len
        return io.StringIO()

    def post_load(self, df: pd.DataFrame) -> 'Handler':
        """Can be overridden by subclass to perform any post-load operations on the dataframe. Must return self."""
        self.df = df
        return self

    def read_line(self, labels: bool = False, data_length: int = 20) -> list[str]:
        if not self.fo or not self.fixed_field_len:
            return []
        if labels:
            return [x.strip() for x in unpack_fixed_field(self.fo.readline(), [self.fixed_field_len] * data_length)]
        return [x.strip() for x in unpack_fixed_field(self.fo.readline(), [10] * data_length)]

    def _load_sub_class(self, obj: 'Handler', line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        self.headers = obj.headers
        self.ncol = obj.ncol
        obj.__dict__.update(self.__dict__)
        ret = obj.load(line, fo, fixed_field_len)
        self.__dict__.update(obj.__dict__)
        return ret

    def _set_attrs_floats(self, param: list[str], attrs: list[str], ind: int = -1) -> None:
        for attr in attrs:
            if not attr:
                continue
            ind += 1
            try:
                setattr(self, attr, float(param[ind]))
            except (ValueError, TypeError, IndexError):
                pass

    def _set_attrs(self, param: list[str], attrs: list[str], ind: int = -1) -> None:
        for attr in attrs:
            if not attr:
                continue
            ind += 1
            try:
                setattr(self, attr, param[ind])
            except IndexError:
                pass
