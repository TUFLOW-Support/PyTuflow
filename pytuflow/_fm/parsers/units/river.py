import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler, SubHandler


class River(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._xs_point_count = 0
        self.TYPE = 'unit'
        self.headers = []
        self.ncol = 0
        self.spill_1 = None
        self.spill_2 = None
        self.lat_inflow_1 = None
        self.lat_inflow_2 = None
        self.lat_inflow_3 = None
        self.lat_inflow_4 = None
        self.dx = 0
        self.n = 0
        self.xs = pd.DataFrame()
        self.valid = True
        self.routing_section = False

    @staticmethod
    def unit_type_name() -> str:
        return 'RIVER'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)

        # load sub_type
        self._set_attrs_str(self.read_line(), ['sub_type'], log_errors=True)
        self.sub_type = self.sub_type.split(' ')[0]
        if self.sub_type == 'SECTION':
            self._sub_obj = RiverSection(self.parent)
        elif self.sub_type == 'CES':
            self._sub_obj = RiverCES(self.parent)
        elif self.sub_type == 'MUSKINGUM':
            self._sub_obj = RiverMuskingum(self.parent)
        elif self.sub_type == 'MUSK-VPMC':
            self._sub_obj = RiverMuskVPMC(self.parent)
        self._sync_obj(self._sub_obj)

        if self.routing_section:  # these sections are a bit more different
            self._sub_obj._sync_obj(self)
            self._sub_obj.load(line, fo, fixed_field_len, self.line_no)
            self._sync_obj(self._sub_obj)
            self.uid = self._get_uid()
            return

        # attributes
        self._set_attrs_str(self.read_line(True),
                            ['id', 'spill_1', 'spill_2', 'lat_inflow_1', 'lat_inflow_2', 'lat_inflow_3', 'lat_inflow_4'],
                            log_errors=[0])
        self.uid = self._get_uid()
        self._set_attrs_float(self.read_line(), ['dx'], log_errors=True)
        self._set_attrs_int(self.read_line(), ['n'], log_errors=True)

        # load cross-section DataFrame
        if self._sub_obj:
            self._sub_obj._sync_obj(self)
            self._sub_obj.load(line, fo, fixed_field_len, self.line_no)
            self._sync_obj(self._sub_obj)

        if self.n:
            a = np.genfromtxt(self.fo, delimiter=(10,10,10,10,10,10,10,10,10), max_rows=self.n, dtype='U')
            if len(a.shape) == 1:
                a = np.reshape(a, (self.n, a.size))
            a1 = a[:, :3].astype(float)
            self.xs = pd.DataFrame(a1, columns=self.headers[:a1.shape[1]])
            if a1.shape[1] >= 6:
                self.xs['easting'] = a[:,5]
            else:
                self.xs['easting'] = 0.
            if a1.shape[1] >= 7:
                self.xs['northing'] = a[:,6]
            else:
                self.xs['northing'] = 0.
            if a.shape[1] >= 7:
                self.xs['deactivation_marker'] = a[:,7]
            self.line_no += self.n

            # self.xs.rename(columns={i: self.headers[i] for i in range(self.xs.shape[1])}, inplace=True)
        self._sub_obj._sync_obj(self)

        # subtype specific post loading steps
        self._sub_obj.post_load()
        self._sync_obj(self._sub_obj)


class RiverSection(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['x', 'y', 'n', 'rel_path_len', 'chan_marker', 'easting', 'northing', 'deactivation_marker',
                        'sp_marker']
        self.ncol = len(self.headers)
        self.routing_section = False
        self.dx = 0

    def post_load(self) -> None:
        if self.xs.empty:
            return
        if 'rel_path_len' in self.xs.columns and self.xs['rel_path_len'].dtype == np.float64:
            self.xs['path_marker'] = ['' for _ in range(self.n)]
        elif 'path_marker' in self.xs.columns and 'rel_path_len' in self.xs.columns:
            self.xs[['path_marker', 'rel_path_len']] = self.xs['rel_path_len'].str.split(' ', n=1, expand=True)
            self.xs['rel_path_len'] = np.where(self.xs['path_marker'] != '*', self.xs.path_marker, self.xs.rel_path_len)
            self.xs['path_marker'] = np.where(self.xs['path_marker'] == '*', self.xs.path_marker, '')
        if not self.xs.empty:
            self.bed_level = float(str(self.xs.y.min()))


class RiverCES(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['x', 'y', 'bank_marker', 'sinuosity', 'chan_marker', 'easting', 'northing']
        self.ncol = len(self.headers)
        self.nrz = 0
        self.roughness_zone = pd.DataFrame()
        self.roughness_zone_headers = ['x', 'rz']
        self.ncol_roughness_zone = len(self.roughness_zone_headers)
        self.routing_section = False
        self.dx = 0

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self.nrz = int(self.read_line()[0])
        if self.nrz:
            a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.nrz, dtype='f4')
            if a.shape != (self.nrz, self.ncol_roughness_zone):
                a = np.reshape(a, (self.nrz, self.ncol_roughness_zone))
            self.roughness_zone = pd.DataFrame(a, columns=self.roughness_zone_headers)
            self.line_no += self.nrz


class RiverMuskingum(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['Velocity', 'Flow']
        self.ncol = len(self.headers)
        self.ndat = 0
        self.routing_section = True
        self.z = np.nan
        self.k = np.nan
        self.x = np.nan
        self.specific_velocity = 'VQ POWER LAW'
        self.v0 = np.nan
        self.q0 = np.nan
        self.a = np.nan
        self.b = np.nan
        self.rating = pd.DataFrame()
        self.dx = 0.

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self._set_attrs_float(self.read_line(), ['dx', 'z'], log_errors=[0])
        self._set_attrs_float(self.read_line(), ['k', 'x'], log_errors=[0])
        self._set_attrs_str(self.read_line(True), ['specific_velocity'], log_errors=[0])
        if self.specific_velocity.upper() == 'VQ POWER LAW':
            self._set_attrs_float(self.read_line(), ['v0', 'q0', 'a', 'b'], log_errors=False)
        else:
            self._set_attrs_int(self.read_line(), ['ndat'], log_errors=True)
            if self.ndat:
                a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.ndat, dtype='f4')
                if a.shape != (self.ndat, self.ncol):
                    a = np.reshape(a, (self.ndat, self.ncol))
                self.rating = pd.DataFrame(a, columns=self.headers)


class RiverMuskVPMC(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['Velocity', 'Flow']
        self.ncol = len(self.headers)
        self.rating = pd.DataFrame()
        self.headers_wave = ['Discharge', 'Celerity', 'Attenuation', 'Level']
        self.ncol_wave = len(self.headers_wave)
        self.ndat = 0
        self.wave_attenuation = pd.DataFrame()
        self.routing_section = True
        self.z = np.nan
        self.slope = np.nan
        self.minsub = 0
        self.maxsub = 100
        self.keyword = 'WAVESPEED ATTENUATION'
        self.n = 0
        self.specific_velocity = 'VQ POWER LAW'
        self.v0 = np.nan
        self.q0 = np.nan
        self.a = np.nan
        self.b = np.nan
        self.lat_inflow_node_1 = None
        self.lat_inflow_node_2 = None
        self.lat_inflow_1 = None
        self.lat_inflow_2 = None
        self.lat_inflow_3 = None
        self.lat_inflow_4 = None
        self.dx = 0.

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs_str(self.read_line(True),
                            ['id', 'lat_inflow_node_1', 'lat_inflow_node_2', 'lat_inflow_1', 'lat_inflow_2',
                             'lat_inflow_3', 'lat_inflow_4'], log_errors=[0])
        self._set_attrs(self.read_line(), ['dx', 'z', 'slope', 'minsub', 'maxsub'],
                        [float, float, float, int, int], log_errors=[0])
        self._set_attrs_str(self.read_line(True), ['keyword'], log_errors=[0])
        self._set_attrs_int(self.read_line(), ['n'], log_errors=True)
        if self.n:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10, 10), max_rows=self.n, dtype='f4')
            if a.shape != (self.n, self.ncol_wave):
                a = np.reshape(a, (self.n, self.ncol_wave))
            self.wave_attenuation = pd.DataFrame(a, columns=self.headers_wave)
        self._set_attrs_str(self.read_line(True), ['specific_velocity'], log_errors=[0])
        if self.specific_velocity.upper() == 'VQ POWER LAW':
            self._set_attrs_float(self.read_line(), ['v0', 'q0', 'a', 'b'], log_errors=False)
        else:
            self._set_attrs_int(self.read_line(), ['ndat'], log_errors=True)
            if self.ndat:
                a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.ndat, dtype='f4')
                if a.shape != (self.ndat, self.ncol):
                    a = np.reshape(a, (self.ndat, self.ncol))
                self.rating = pd.DataFrame(a, columns=self.headers)


class MuskXsec(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.routing_section = True
        self.headers = ['Velocity', 'Flow']
        self.ncol = len(self.headers)
        self.rating = pd.DataFrame()
        self.xs = pd.DataFrame()
        self.xs_headers = ['x', 'y', 'n', 'rel_path_len', 'chan_marker', 'easting', 'northing']
        self.xs_ncol = len(self.xs_headers)
        self.lat_inflow_node_1 = None
        self.lat_inflow_node_2 = None
        self.lat_inflow_1 = None
        self.lat_inflow_2 = None
        self.lat_inflow_3 = None
        self.lat_inflow_4 = None
        self.z = np.nan
        self.slope = np.nan
        self.minsub = 0
        self.maxsub = 100
        self.qmax = np.nan
        self.c0fact = 1.
        self.keyword = 'CROSS SECTION'
        self.specific_velocity = 'VQ POWER LAW'
        self.n = 0
        self.ndat = 0
        self.v0 = np.nan
        self.q0 = np.nan
        self.a = np.nan
        self.b = np.nan
        self.dx = 0.

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs_str(self.read_line(True),
                            ['id', 'lat_inflow_node_1', 'lat_inflow_node_2', 'lat_inflow_1', 'lat_inflow_2',
                             'lat_inflow_3', 'lat_inflow_4'], log_errors=[0])
        self._set_attrs(self.read_line(), ['dx', 'z', 'slope', 'minsub', 'maxsub', 'qmax', 'c0fact'],
                        [float, float, float, int, int, float, float], log_errors=[0])
        self._set_attrs_str(self.read_line(True), ['keyword'], log_errors=True)
        self._set_attrs_int(self.read_line(), ['n'], log_errors=True)
        if self.n:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10, 10, 10, 10, 10), max_rows=self.n, dtype='U')
            if len(a.shape) == 1:
                a = np.reshape(a, (self.n, a.size))
            a1 = a[:, :3].astype(float)
            a1 = a1[:,4:].astype(float)
            self.xs = pd.DataFrame(a1, columns=self.headers[:3])
        self._set_attrs_str(self.read_line(True), ['specific_velocity'], log_errors=[0])
        if self.specific_velocity.upper() == 'VQ POWER LAW':
            self._set_attrs_float(self.read_line(), ['v0', 'q0', 'a', 'b'], log_errors=False)
        else:
            self._set_attrs_int(self.read_line(), ['ndat'], log_errors=True)
            if self.ndat:
                a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.ndat, dtype='f4')
                if a.shape != (self.ndat, self.ncol):
                    a = np.reshape(a, (self.ndat, self.ncol))
                self.rating = pd.DataFrame(a, columns=self.headers)


class MuskRsec(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.routing_section = True
        self.headers = ['Velocity', 'Flow']
        self.ncol = len(self.headers)
        self.rating = pd.DataFrame()
        self.lat_inflow_node_1 = None
        self.lat_inflow_node_2 = None
        self.lat_inflow_1 = None
        self.lat_inflow_2 = None
        self.lat_inflow_3 = None
        self.lat_inflow_4 = None
        self.dx = 0.
        self.zval = 0.
        self.keyword = 'RIBAMAN'
        self.rtype = 'MANNING'
        self.crough = np.nan
        self.frough = np.nan
        self.cslope = np.nan
        self.fslope = np.nan
        self.b1 = np.nan
        self.b2 = np.nan
        self.b3 = np.nan
        self.b4 = np.nan
        self.d1 = np.nan
        self.d2 = np.nan
        self.d3 = np.nan
        self.d4 = np.nan
        self.vs = np.nan
        self.maxq = np.nan
        self.bfprop = 1.0
        self.specific_velocity = 'VQ POWER LAW'
        self.ndat = 0
        self.v0 = np.nan
        self.q0 = np.nan
        self.a = np.nan
        self.b = np.nan
        self.dx = 0.

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs_str(self.read_line(True),
                            ['id', 'lat_inflow_node_1', 'lat_inflow_node_2', 'lat_inflow_1', 'lat_inflow_2',
                             'lat_inflow_3', 'lat_inflow_4'], log_errors=[0])
        self._set_attrs_float(self.read_line(), ['dx', 'zval'], log_errors=[0])
        self._set_attrs_str(self.read_line(True), ['keyword'], log_errors=[0])
        self._set_attrs_str(self.read_line(True), ['rtype'], log_errors=False)
        self._set_attrs_float(self.read_line(), ['crough', 'frough'], log_errors=False)
        self._set_attrs_float(self.read_line(), ['cslope', 'fslope'], log_errors=False)
        self._set_attrs_float(self.read_line(), ['b1', 'b2', 'b3', 'b4'], log_errors=False)
        self._set_attrs_float(self.read_line(), ['d1', 'd2', 'd3', 'd4'], log_errors=False)
        self._set_attrs_float(self.read_line(), ['vs'], log_errors=False)
        self._set_attrs_float(self.read_line(), ['maxq', 'bfprop'], log_errors=False)
        self._set_attrs_str(self.read_line(True), ['specific_velocity'], log_errors=[0])
        if self.specific_velocity.upper() == 'VQ POWER LAW':
            self._set_attrs_float(self.read_line(), ['v0', 'q0', 'a', 'b'], log_errors=False)
        else:
            self._set_attrs_int(self.read_line(), ['ndat'], log_errors=True)
            if self.ndat:
                a = np.genfromtxt(self.fo, delimiter=(10, 10), max_rows=self.ndat, dtype='f4')
                if a.shape != (self.ndat, self.ncol):
                    a = np.reshape(a, (self.ndat, self.ncol))
                self.rating = pd.DataFrame(a, columns=self.headers)
