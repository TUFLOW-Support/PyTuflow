import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .fm_unit_handler import Handler


class RiverUnit(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._xs_point_count = 0
        self.keyword = 'RIVER'
        self.headers = []
        self.ncol = 0
        self.spill_1 = None
        self.spill_2 = None
        self.lat_inflow_1 = None
        self.lat_inflow_2 = None
        self.lat_inflow_3 = None
        self.lat_inflow_4 = None
        self.valid = True
        self.type = 'unit'

    def __repr__(self) -> str:
        return f'<River {self.sub_name} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self.sub_name = self.read_line(True)[0]  # SECTION / CES
        ids = self.read_line(True)  # ID, spill 1, spill 2, lat inflow 1, lat inflow 2, lat inflow 3, lat inflow 4
        self.id = ids[0]
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        self._assign_other_labels(ids)
        try:
            self.dx = float(self.read_line()[0])
        except ValueError:
            self.errors.append(f'Error reading dx for {self.id}')
        try:
            self._xs_point_count = int(self.read_line()[0])
        except ValueError:
            self.errors.append(f'Error reading number of lines for {self.id}')
            self._xs_point_count = 0

        if self.sub_name == 'SECTION':
            self._sub_obj = RiverSection()
        elif self.sub_name == 'CES':
            self._sub_obj = RiverCES()
        if self._sub_obj is not None:
            return self._load_sub_class(self._sub_obj, line, fo, fixed_field_len)
        return buf

    def post_load(self, df: pd.DataFrame) -> 'Handler':
        self.df = df
        if self._sub_obj is not None:
            self._sub_obj = self._sub_obj.post_load(df)
            self.__dict__.update(self._sub_obj.__dict__)
        return self

    def _assign_other_labels(self, labels: list[str]) -> None:
        for i, attr in enumerate(['spill_1', 'spill_2', 'lat_inflow_1', 'lat_inflow_2', 'lat_inflow_3', 'lat_inflow_4']):
            j = i + 1  # first label is id
            if j < len(labels):
                setattr(self, attr, labels[j])


# noinspection DuplicatedCode
class RiverSection(RiverUnit):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['x', 'y', 'n', 'rel_path_len', 'chan_marker', 'easting', 'northing', 'deactivation_marker',
                        'sp_marker']
        self.ncol = len(self.headers)

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO(''.join([fo.readline() for _ in range(self._xs_point_count)]))
        return buf

    def post_load(self, df: pd.DataFrame) -> 'Handler':
        self.df = df
        if self.df['rel_path_len'].dtype == np.float64:
            self.df['path_marker'] = ['' for _ in range(self._xs_point_count)]
        else:
            self.df[['path_marker', 'rel_path_len']] = self.df['rel_path_len'].str.split(' ', n=1, expand=True)
            self.df['rel_path_len'] = np.where(self.df['path_marker'] != '*', self.df.path_marker, self.df.rel_path_len)
            self.df['path_marker'] = np.where(self.df['path_marker'] == '*', self.df.path_marker, '')
        self.bed_level = np.nanmin(self.df['y'])
        self.ups_invert = self.bed_level
        self.dns_invert = self.bed_level
        return self


class RiverCES(RiverUnit):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.nrz = 0
        self.headers = ['x', 'y', 'bank_marker', 'sinuosity', 'chan_marker', 'easting', 'northing']
        self.ncol = len(self.headers)
        self.df_roughness_zone = pd.DataFrame()
        self.roughness_zone_headers = ['x', 'rz']

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf1 = io.StringIO(''.join([fo.readline() for _ in range(self._xs_point_count)]))
        self.nrz = int(self.read_line()[0])
        buf2 = io.StringIO(''.join([fo.readline() for _ in range(self.nrz)]))
        self.df_roughness_zone = pd.read_fwf(buf2, widths=[10] * len(self.roughness_zone_headers), names=self.roughness_zone_headers, header=None)
        return buf1

    def post_load(self, df: pd.DataFrame) -> 'Handler':
        self.df = df
        return self
