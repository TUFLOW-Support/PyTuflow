import io
from typing import TextIO

import numpy as np
import pandas as pd

from ._unit import Handler


SUB_UNIT_NAME = 'BRIDGE'


class Bridge(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        self.ups_label = None
        self.dns_label = None
        self.ups_ref = None
        self.dns_ref = None
        self.valid = True
        self.type = 'structure'
        self._labels = []
        # TODO there are still other properties that need to be added to the class

    def __repr__(self) -> str:
        return f'<Bridge {self.sub_name} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self.sub_name = self.read_line()[0]
        self._labels = self.read_line(True)
        self.id = self._labels[0]
        self.ups_label, self.dns_label = self._labels[:2]
        self._assign_other_labels(self._labels)
        self.uid = f'BRIDGE_{self.sub_name}_{self.id}'
        if self.sub_name == 'ARCH':
            self._sub_obj = ArchBridge()
        elif self.sub_name == 'PIERLOSS':
            self._sub_obj = PierLossBridge()
        elif self.sub_name == 'USBPR1978':
            self._sub_obj = USBPRBridge()
        if self._sub_obj is not None:
            return self._load_sub_class(self._sub_obj, line, fo, fixed_field_len)
        return buf

    def post_load(self, df: pd.DataFrame) -> 'Handler':
        self.df = df
        if np.isnan(self.bed_level):
            self.bed_level = df.min().y
        if np.isnan(self.ups_invert):
            self.ups_invert = self.bed_level
        if np.isnan(self.dns_invert):
            self.dns_invert = self.bed_level
        return self

    def _assign_other_labels(self, labels: list[str]) -> None:
        for i, attr in enumerate(['ups_ref', 'dns_ref']):
            j = i + 2
            if j < len(labels):
                setattr(self, attr, labels[j])


class ArchBridge(Bridge):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['x', 'y', 'n', 'chan_marker']
        self.arch_header = ['start', 'finish', 'springing level', 'soffit']
        self.ncol = len(self.headers)
        self.df_arch = pd.DataFrame(columns=self.arch_header)

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        _ = self.read_line()  # MANNING
        params = self.read_line()
        self.nxspts = int(self.read_line()[0])
        buf = io.StringIO(''.join([fo.readline() for _ in range(self.nxspts)]))
        self.narch = int(self.read_line()[0])
        buf2 = io.StringIO(''.join([fo.readline() for _ in range(self.narch)]))
        self.df_arch = pd.read_fwf(buf2, widths=[10]*len(self.arch_header), names=self.arch_header, header=None)
        return buf


class PierLossBridge(Bridge):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['x', 'y', 'n', 'chan_marker', 'top_level']
        self.pier_header = ['xleft', 'xright', 'hleft', 'hright']
        self.ncol = len(self.headers)
        self.nupsxspts = 0
        self.ndnsxspts = 0
        self.npier = 0
        self.df_ups_xs = pd.DataFrame(columns=self.headers)
        self.df_dns_xs = pd.DataFrame(columns=self.headers)
        self.df_piers = pd.DataFrame(columns=self.pier_header)

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        _ = self.read_line()  # YARNELL
        params = self.read_line()
        params = self.read_line()
        self.nupsxspts = int(self.read_line()[0])
        buf1 = io.StringIO(''.join([fo.readline() for _ in range(self.nupsxspts)]))
        self.ndnsxspts = int(self.read_line()[0])
        buf2 = io.StringIO(''.join([fo.readline() for _ in range(self.ndnsxspts)]))
        self.npiers = int(self.read_line()[0])
        buf3 = io.StringIO(''.join([fo.readline() for _ in range(self.npiers)]))
        self.df_ups_xs = pd.read_fwf(buf1, widths=[10]*len(self.headers), names=self.headers, header=None)
        self.df_dns_xs = pd.read_fwf(buf2, widths=[10]*len(self.headers), names=self.headers, header=None)
        self.df_piers = pd.read_fwf(buf3, widths=[10]*len(self.pier_header), names=self.pier_header, header=None)
        self.ups_invert = self.df_ups_xs.min().y
        self.dns_invert = self.df_dns_xs.min().y
        if self.ups_invert < self.dns_invert:
            self.bed_level = self.ups_invert
            buf1.seek(0)
            return buf1
        else:
            self.bed_level = self.dns_invert
            buf2.seek(0)
            return buf2


class USBPRBridge(Bridge):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['x', 'y', 'n', 'chan_marker']
        self.arch_header = ['start', 'finish', 'springing level', 'soffit']
        self.culv_header = ['invert', 'soffit', 'area', 'cd part full', 'cd full', 'drowning coeff']
        self.ncol = len(self.headers)
        self.npiers = 0
        self.nxspts = 0
        self.narch = 0
        self.nculv = 0
        self.df_arch = pd.DataFrame()
        self.df_culv = pd.DataFrame()

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        _ = self.read_line()  # MANNING
        params = self.read_line()
        params = self.read_line()
        self.npiers = int(self.read_line()[0])
        type_ = self.read_line()[0]
        self.nxspts = int(self.read_line()[0])
        buf1 = io.StringIO(''.join([fo.readline() for _ in range(self.nxspts)]))
        self.narch = int(self.read_line()[0])
        buf2 = io.StringIO(''.join([fo.readline() for _ in range(self.narch)]))
        self.df_arch = df = pd.read_fwf(buf2, widths=[10]*len(self.arch_header), names=self.arch_header, header=None)
        self.nculv = int(self.read_line()[0])
        buf3 = io.StringIO(''.join([fo.readline() for _ in range(self.nculv)]))
        self.df_culv = pd.read_fwf(buf3, widths=[10]*len(self.culv_header), names=self.culv_header, header=None)
        return buf1


AVAILABLE_CLASSES = [Bridge]
