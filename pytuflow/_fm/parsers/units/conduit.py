import io
from typing import TextIO

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .handler import Handler, SubHandler


class Conduit(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.TYPE = 'unit'
        self.valid = True

    @staticmethod
    def unit_type_name() -> str:
        return 'CONDUIT'

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        super().load(line, fo, fixed_field_len, line_no)
        self._set_attrs_str(self.read_line(True), ['sub_type'], log_errors=True)
        if self.sub_type == 'ASYMMETRIC':
            self._sub_obj = AsymmetricConduit(self.parent)
        elif self.sub_type == 'CIRCULAR':
            self._sub_obj = CircularConduit(self.parent)
        elif self.sub_type in ['FULL', 'FULLARCH']:
            self._sub_obj = FullArchConduit(self.parent)
        elif self.sub_type == 'RECTANGULAR':
            self._sub_obj = RectangularConduit(self.parent)
        elif self.sub_type in ['SPRUNG', 'SPRUNGARCH']:
            self._sub_obj = SprungArchConduit(self.parent)
        elif self.sub_type == 'SECTION':
            self._sub_obj = SymmetricalConduit(self.parent)
        self._sync_obj(self._sub_obj)
        self._set_attrs_str(self.read_line(True), ['id'], log_errors=True)
        self.uid = self._get_uid()
        if self._sub_obj:
            self._sub_obj._sync_obj(self)
            self._sub_obj.load(line, fo, fixed_field_len, self.line_no)
            self._sync_obj(self._sub_obj)


class AsymmetricConduit(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.method = ''
        self.headers = ['x', 'y', 'ks']
        self.ncol = len(self.headers)
        self.section = pd.DataFrame()
        self.ndat = 0

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs(self.read_line(), ['dx', 'method'], [float, str], log_errors=True)
        self._set_attrs_int(self.read_line(), ['ndat'], log_errors=True)
        if self.ndat:
            a = np.genfromtxt(self.fo, delimiter=(10, 10, 10), max_rows=self.ndat, dtype='f4')
            if a.shape != (self.ndat, self.ncol):
                a = np.reshape(a, (self.ndat, self.ncol))
            self.line_no += self.ndat
            self.section = pd.DataFrame(a, columns=self.headers)
            self.bed_level = float(str(self.section.y.min()))


class CircularConduit(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.frform = ''
        self.inv = np.nan
        self.dia = np.nan
        self.fribot = np.nan
        self.fritop = np.nan
        self.bslot = 'GLOBAL'
        self.dh = np.nan
        self.dslot = np.nan
        self.tslot = 'GLOBAL'
        self.dh_top = np.nan
        self.hslot = np.nan

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs_float(self.read_line(), ['dx'], log_errors=True)
        self._set_attrs(self.read_line(), ['frform'], [str], log_errors=True)
        self._set_attrs(self.read_line(),
                        ['inv', 'dia','bslot', 'dh', 'dslot', 'tslot', 'dh_top', 'hslot'],
                        [float, float, str, float, float, str, float, float], log_errors=[0, 1])
        self._set_attrs_float(self.read_line(), ['fribot', 'fritop'], log_errors=True)
        self.bed_level = self.inv


class FullArchConduit(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.frform = ''
        self.inv = np.nan
        self.width = np.nan
        self.archyt = np.nan
        self.bslot = 'GLOBAL'
        self.dh = np.nan
        self.dslot = np.nan
        self.tslot = 'GLOBAL'
        self.dh_top = np.nan
        self.hslot = np.nan
        self.fribot = np.nan
        self.friarc = np.nan

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs_float(self.read_line(), ['dx'], log_errors=True)
        self._set_attrs_str(self.read_line(), ['frform'], log_errors=True)
        self._set_attrs(self.read_line(),
                        ['inv', 'width', 'archyt', 'bslot', 'dh', 'dslot', 'tslot', 'dh_top', 'hslot'],
                        [float, float, float, str, float, float, str, float, float], log_errors=[0, 1, 2])
        self._set_attrs_float(self.read_line(), ['fribot', 'friarc'], log_errors=True)
        self.bed_level = self.inv


class RectangularConduit(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.friform = ''
        self.inv = np.nan
        self.width = np.nan
        self.height = np.nan
        self.fribot = np.nan
        self.fritop = np.nan
        self.frisid = np.nan
        self.bslot = 'GLOBAL'
        self.dh = np.nan
        self.dslot = np.nan
        self.tslot = 'GLOBAL'
        self.dh_top = np.nan
        self.hslot = np.nan

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs_float(self.read_line(), ['dx'], log_errors=True)
        self._set_attrs_str(self.read_line(), ['friform'], log_errors=True)
        self._set_attrs(self.read_line(),
                        ['inv', 'width', 'height', 'bslot', 'dh', 'dslot', 'tslot', 'dh_top', 'hslost'],
                        [float, float, float, str, float, float, str, float, float], log_errors=[0, 1, 2])
        self._set_attrs_float(self.read_line(), ['fribot', 'fritop', 'frisid'], log_errors=True)
        self.bed_level = self.inv


class SprungArchConduit(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.frform = ''
        self.inv = np.nan
        self.width = np.nan
        self.sprhyt = np.nan
        self.archyt = np.nan
        self.bslot = 'GLOBAL'
        self.dh = np.nan
        self.dslot = np.nan
        self.tslot = 'GLOBAL'
        self.dh_top = np.nan
        self.hslot = np.nan
        self.fribot = np.nan
        self.frisid = np.nan
        self.friarc = np.nan

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs_float(self.read_line(), ['dx'], log_errors=True)
        self._set_attrs_str(self.read_line(), ['frform'], log_errors=True)
        self._set_attrs(self.read_line(),
                        ['inv', 'width', 'sprhyt', 'archyt', 'bslot', 'dh', 'dslot', 'tslot', 'dh_top', 'hslot'],
                        [float, float, float, float, str, float, float, str, float, float],
                        log_errors=[0, 1, 2, 3])
        self._set_attrs_float(self.read_line(), ['fribot', 'frisid', 'friarc'], log_errors=True)
        self.bed_level = self.inv


class SymmetricalConduit(SubHandler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['x', 'y', 'ks']
        self.ncol = len(self.headers)
        self.section = pd.DataFrame()
        self.ndat = 0

    def load(self, line: str, fo: TextIO, fixed_field_len: int, line_no: int) -> None:
        self._set_attrs_float(self.read_line(), ['dx'], log_errors=True)
        self._set_attrs_int(self.read_line(), ['ndat'], log_errors=True)
        if self.ndat:
            a = np.genfromtxt(fo, delimiter=(10, 10, 10), max_rows=self.ndat, dtype='f4')
            if a.shape != (self.ndat, self.ncol):
                a = np.reshape(a, (self.ndat, self.ncol))
            self.section = pd.DataFrame(a, columns=self.headers)
            self.line_no += self.ndat
            self.bed_level = float(str(self.section.y.min()))
