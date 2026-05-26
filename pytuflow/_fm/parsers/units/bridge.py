import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler, SubHandler


class Bridge(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'structure'
        self.ups_label = None
        self.dns_label = None
        self.ups_label_ref = None
        self.dns_label_ref = None
        self.keyword = ''
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'BRIDGE'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(), ['sub_type'], log_errors=True)
        if self.sub_type == 'ARCH':
            self._sub_obj = ArchBridge(self.parent)
        elif self.sub_type == 'PIERLOSS':
            self._sub_obj = PierLossBridge(self.parent)
        elif self.sub_type == 'USBPR1978':
            self._sub_obj = USBPRBridge(self.parent)
        self._sync_obj(self._sub_obj)
        self._set_attrs_str(self.read_line(True), ['ups_label', 'dns_label', 'ups_label_ref', 'dns_label_ref'],
                            log_errors=[0, 1])
        self.id = self.ups_label
        self.uid = self._get_uid()
        self._set_attrs_str(self.read_line(), ['keyword'], log_errors=True)
        if self._sub_obj:
            self._sub_obj._sync_obj(self)
            self._sub_obj.load(line, fo, fixed_field_len, self.line_no)
            self._sync_obj(self._sub_obj)



class ArchBridge(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.xs_headers = ['x', 'y', 'n', 'chan_marker']
        self.ncol_xs = len(self.xs_headers)
        self.xs = pd.DataFrame()
        self.arch_header = ['start', 'finish', 'springing level', 'soffit']
        self.ncol_arch = len(self.arch_header)
        self.arches = pd.DataFrame()
        self.skewb = np.nan
        self.cali = 1.
        self.rdlen = 0.
        self.duall = 0.
        self._blank = ''
        self.oflag = ''
        self.rlower = np.nan
        self.rupper = np.nan
        self.cdorifice = np.nan
        self.npts = 0
        self.narch = 0

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs(self.read_line(),
                        ['cali', 'skewb', 'rdlen', 'duall', '_blank', 'oflag', 'rlower', 'rupper', 'cdorifice'],
                        [float, float, float, float, str, str, float, float, float], log_errors=[0, 1])
        self._set_attrs_int(self.read_line(), ['npts'], log_errors=True)
        if self.npts:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10), max_rows=self.npts, dtype='f4')
            if a.shape != (self.npts, 3):
                a = np.reshape(a, (self.npts, 3))
            self.xs = pd.DataFrame(a, columns=self.xs_headers[:3])
            self.bed_level = float(str(self.xs.y.min()))
            self.line_no += self.npts

        self._set_attrs_int(self.read_line(), ['narch'], log_errors=True)
        if self.narch:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10, 10), max_rows=self.narch, dtype='f4')
            if a.shape != (self.narch, self.ncol_arch):
                a = np.reshape(a, (self.narch, self.ncol_arch))
            self.arches = pd.DataFrame(a, columns=self.arch_header)
            self.line_no += self.narch


class PierLossBridge(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.xs_headers = ['x', 'y', 'n', 'dummy', 'chan_marker', 'top_level']
        self.ncol_xs = len(self.xs_headers)
        self.xs_ups = pd.DataFrame()
        self.xs_dns = pd.DataFrame()
        self.pier_header = ['xleft', 'hleft', 'xright', 'hright']
        self.ncol_piers = len(self.pier_header)
        self.piers = pd.DataFrame()
        self.npts_us = 0
        self.npts_ds = 0
        self.npiers = 0
        self.cali = 1.
        self.altmethod = 'ORIFICE'
        self.cdorifice = 1.
        self.rlower = 0.
        self.rupper = 0.
        self.k = 1.
        self.rdlen = 0.

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs(self.read_line(), ['cali', 'altmethod', 'cdorifice', 'rlower', 'rupper'],
                        [float, str, float, float, float])
        self._set_attrs_float(self.read_line(), ['k', 'rdlen'], log_errors=True)
        self._set_attrs_int(self.read_line(), ['npts_us'], log_errors=True)
        if self.npts_us:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10, 10, 10, 10), max_rows=self.npts_us, dtype='U')
            if a.shape != (self.npts_us, self.ncol_xs):
                a = np.reshape(a, (self.npts_us, self.ncol_xs))
            self.xs_ups = pd.DataFrame(a, columns=self.xs_headers)
            self.xs_ups[['x', 'y', 'n', 'top_level']] = self.xs_ups[['x', 'y', 'n', 'top_level']].astype('float')
            self.xs_ups.drop(['dummy'], axis=1, inplace=True)
            self.line_no += self.npts_us
            if np.isnan(self.bed_level):
                self.bed_level = float(str(self.xs_ups.y.min()))

        self._set_attrs_int(self.read_line(), ['npts_ds'], log_errors=True)
        if self.npts_ds:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10, 10, 10, 10), max_rows=self.npts_ds)
            if a.shape != (self.npts_ds, self.ncol_xs):
                a = np.reshape(a, (self.npts_ds, self.ncol_xs))
            self.xs_dns = pd.DataFrame(a, columns=self.xs_headers)
            self.xs_dns[['x', 'y', 'n', 'top_level']] = self.xs_dns[['x', 'y', 'n', 'top_level']].astype('float')
            self.xs_dns.drop(['dummy'], axis=1, inplace=True)
            self.line_no += self.npts_ds
            bed_level = float(str(self.xs_ups.y.min()))
            if np.isnan(self.bed_level):
                self.bed_level = bed_level
            else:
                self.bed_level = min(self.bed_level, bed_level)

        self._set_attrs_int(self.read_line(), ['npiers'], log_errors=True)
        if self.npiers:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10, 10), max_rows=self.npiers, dtype='f4')
            if a.shape != (self.npiers, self.ncol_piers):
                a = np.reshape(a, (self.npiers, self.ncol_piers))
            self.piers = pd.DataFrame(a, columns=self.pier_header)
            self.line_no += self.npiers


class USBPRBridge(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.xs_headers = ['x', 'y', 'n', 'chan_marker']
        self.ncol_xs = len(self.xs_headers)
        self.xs = pd.DataFrame()
        self.arch_headers = ['start', 'finish', 'springing level', 'soffit']
        self.ncol_arch = len(self.arch_headers)
        self.arches = pd.DataFrame()
        self.culv_headers = ['invert', 'soffit', 'area', 'part full cd', 'full cd', 'drowning coeff']
        self.ncol_culv = len(self.culv_headers)
        self.culvs = pd.DataFrame()
        self.cali = 1.
        self.skewb = 0.
        self.rdlen = 0.
        self.duall = 0.
        self.pierw = 0.
        self.oflag = ''
        self.rlower = 0.
        self.rupper = 0.
        self.cdorifice = 1.
        self.iabut = 0
        self.npier = 0
        self.shape = ''
        self.diaph = ''
        self.prcoef = 1.
        self.altype = ''
        self.npts = 0
        self.narch = 0
        self.nculv = 0

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs(self.read_line(),
                        ['cali', 'skewb', 'rdlen', 'duall', 'pierw', 'oflag', 'rlower', 'rupper', 'cdorifice'],
                        [float, float, float, float, float, str, float, float, float])
        self._set_attrs_int(self.read_line(), ['iabut'], log_errors=True)
        self._set_attrs(self.read_line(), ['npier', 'shape', 'diaph', 'prcoef'], [int, str, str, float],
                        log_errors=[0])
        self._set_attrs_str(self.read_line(), ['altype'], log_errors=True)

        # cross-section
        self._set_attrs_int(self.read_line(), ['npts'], log_errors=True)
        if self.npts:
            a = np.genfromtxt(self.fo, delimiter=(10,10,10,10), max_rows=self.npts, dtype='U')
            if a.shape != (self.npts, self.ncol_xs):
                a = np.reshape(a, (self.npts, self.ncol_xs))
            self.xs = pd.DataFrame(a, columns=self.xs_headers)
            self.xs[['x', 'y', 'n']] = self.xs[['x', 'y', 'n']].astype('float')
            self.bed_level = self.xs.y.min()
            self.line_no += self.npts

        # arches
        self._set_attrs_int(self.read_line(), ['narch'], log_errors=True)
        if self.narch:
            a = np.genfromtxt(self.fo, delimiter=(10,10,10,10), max_rows=self.narch, dtype='f4')
            if a.shape != (self.narch, self.ncol_arch):
                a = np.reshape(a, (self.narch, self.ncol_arch))
            self.arches = pd.DataFrame(a, columns=self.arch_headers)
            self.line_no += self.narch

        # culverts
        self._set_attrs_int(self.read_line(), ['nculv'], log_errors=True)
        if self.nculv:
            a = np.genfromtxt(self.fo, delimiter=(10,10,10,10,10,10), max_rows=self.nculv, dtype='f4')
            if a.shape != (self.nculv, self.ncol_culv):
                a = np.reshape(a, (self.nculv, self.ncol_culv))
            self.culvs = pd.DataFrame(a, columns=self.culv_headers)
            self.line_no += self.nculv
