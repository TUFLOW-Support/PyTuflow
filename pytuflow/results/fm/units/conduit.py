import io
from typing import TextIO

import numpy as np

from ._unit import Handler


SUB_UNIT_NAME = 'CONDUIT'


class Conduit(Handler):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.keyword = SUB_UNIT_NAME
        self.headers = []
        self.ncol = 0
        # TODO read other properties
        self.valid = True
        self.type = 'unit'

    def __repr__(self) -> str:
        return f'<{self.keyword} {self.sub_name} {self.id}>'

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = super().load(line, fo, fixed_field_len)
        self.sub_name = self.read_line(True)[0]
        self.id = self.read_line(True)[0]
        self.uid = f'{self.keyword}_{self.sub_name}_{self.id}'
        if self.sub_name == 'ASYMMETRIC':
            self._sub_obj = AsymmetricConduit()
        elif self.sub_name == 'CIRCULAR':
            self._sub_obj = CircularConduit()
        elif self.sub_name == 'FULLARCH':
            self._sub_obj = FullArchConduit()
        elif self.sub_name == 'RECTANGULAR':
            self._sub_obj = RectangularConduit()
        elif self.sub_name == 'SPRUNGARCH':
            self._sub_obj = SprungArchConduit()
        elif self.sub_name == 'SECTION':
            self._sub_obj = SymmetricalConduit()
        if self._sub_obj:
            return self._load_sub_class(self._sub_obj, line, fo, fixed_field_len)
        return buf


class AsymmetricConduit(Conduit):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.method = ''
        self.headers = ['x', 'y', 'ks']
        self.ncol = len(self.headers)

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO()
        param = self.read_line()
        self.dx = float(param[0])
        self.method = param[1]
        self.ndat = int(self.read_line()[0])
        buf.write(''.join([fo.readline() for _ in range(self.ndat)]))
        buf.seek(0)
        return buf


class CircularConduit(Conduit):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.friform = ''
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

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO()
        self.dx = float(self.read_line()[0])
        self.friform = self.read_line()[0]
        param = self.read_line()
        self.inv = float(param[0])
        self.bed_level = self.inv
        self.ups_invert = self.bed_level
        self.dns_invert = self.bed_level
        self.dia = float(param[1])
        self.bslot = param[2]
        try:
            self.dh = float(param[3])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.dslot = float(param[4])
        except (ValueError, TypeError, IndexError):
            pass
        self.tslot = param[5]
        try:
            self.dh_top = float(param[6])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.hslot = float(param[7])
        except (ValueError, TypeError, IndexError):
            pass
        param = self.read_line()
        try:
            self.fribot = float(param[0])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.fritop = float(param[1])
        except (ValueError, TypeError, IndexError):
            pass
        return buf


class FullArchConduit(Conduit):

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

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO()
        self.dx = float(self.read_line()[0])
        self.frform = self.read_line()[1]
        param = self.read_line()
        self.inv = float(param[0])
        self.bed_level = self.inv
        self.ups_invert = self.bed_level
        self.dns_invert = self.bed_level
        self.width = float(param[1])
        self.archyt = float(param[2])
        self.bslot = param[3]
        try:
            self.dh = float(param[4])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.dslot = float(param[5])
        except (ValueError, TypeError, IndexError):
            pass
        self.tslot = param[6]
        try:
            self.dh_top = float(param[7])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.hslot = float(param[8])
        except (ValueError, TypeError, IndexError):
            pass
        return buf


class RectangularConduit(Conduit):

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

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO()
        self.dx = float(self.read_line()[0])
        self.friform = self.read_line()[0]
        param = self.read_line()
        self.inv = float(param[0])
        self.bed_level = self.inv
        self.ups_invert = self.bed_level
        self.dns_invert = self.bed_level
        self.width = float(param[1])
        self.height = float(param[2])
        self.bslot = param[3]
        try:
            self.dh = float(param[4])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.dslot = float(param[5])
        except (ValueError, TypeError, IndexError):
            pass
        self.tslot = param[6]
        try:
            self.dh_top = float(param[7])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.hslot = float(param[8])
        except (ValueError, TypeError, IndexError):
            pass
        param = self.read_line()
        try:
            self.fribot = float(param[0])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.frisid = float(param[1])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.fritop = float(param[2])
        except (ValueError, TypeError, IndexError):
            pass
        return buf


class SprungArchConduit(Conduit):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.frform = ''
        self.inv = np.nan
        self.width = np.nan
        self.sprhyt = np.nan
        self.archyt = np.nan
        self.fribot = np.nan
        self.fritop = np.nan
        self.frisid = np.nan
        self.bslot = 'GLOBAL'
        self.dh = np.nan
        self.dslot = np.nan
        self.tslot = 'GLOBAL'
        self.dh_top = np.nan
        self.hslot = np.nan

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO()
        self.dx = float(self.read_line()[0])
        self.frform = self.read_line()[1]
        param = self.read_line()
        self.inv = float(param[0])
        self.bed_level = self.inv
        self.ups_invert = self.bed_level
        self.dns_invert = self.bed_level
        self.width = float(param[1])
        self.sprhyt = float(param[2])
        self.archyt = float(param[3])
        self.bslot = param[4]
        try:
            self.dh = float(param[5])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.dslot = float(param[6])
        except (ValueError, TypeError, IndexError):
            pass
        self.tslot = param[7]
        try:
            self.dh_top = float(param[8])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.hslot = float(param[9])
        except (ValueError, TypeError, IndexError):
            pass
        param = self.read_line()
        try:
            self.fribot = float(param[0])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.frisid = float(param[1])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            self.fritop = float(param[2])
        except (ValueError, TypeError, IndexError):
            pass
        return buf


class SymmetricalConduit(Conduit):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.headers = ['x', 'y', 'ks']
        self.ncol = len(self.headers)

    def load(self, line: str, fo: TextIO, fixed_field_len: int) -> TextIO:
        buf = io.StringIO()
        param = self.read_line()
        self.dx = float(param[0])
        self.ndat = int(self.read_line()[0])
        buf.write(''.join([fo.readline() for _ in range(self.ndat)]))
        buf.seek(0)
        return buf


AVAILABLE_CLASSES = [Conduit]
