import re
from pathlib import Path
from typing import io

import numpy as np


class BoundaryType:
    """Base class for handling Boundary Type data."""

    def __new__(cls, line: str):
        line = line.strip('\n\t "')
        if re.findall(r'^BC\d{6}:', line):
            line_ = re.sub(r'^BC\d{6}:\s*', '', line)
            if line_.startswith('QT'):
                cls = BoundaryTypeQT
            elif line_.startswith('HT'):
                cls = BoundaryTypeHT
            elif line_.startswith('HQ'):
                cls = BoundaryTypeHQ
            elif line_.startswith('ST') and 'based on SA region' in line_:
                cls = BoundaryTypeSA
            elif line_.startswith('RF') and 'based on SA region' in line_:
                cls = BoundaryTypeRF
        self = super().__new__(cls)
        return self

    def __init__(self, line: str) -> None:
        """
        Parameters
        ----------
        line : str
            Line from file.
        """
        self.line = line
        self.id = ''
        self.name = ''
        self.type = ''
        self.units = ''
        self.index_name = 'Time'
        self.gis_file = ''
        self.bc_dbase = ''
        self.bc_file = ''
        self.type = ''
        self.col1_header = None
        self.col2_header = None
        self.header_line_count = 2
        self.values = np.array([])
        self.valid = False

    def __repr__(self):
        if self.valid:
            return '<{0} {1}>'.format(self.__class__.__name__, self.name)
        return '<{0} Invalid>'.format(self.__class__.__name__)

    def read(self, fo: io.TextIO) -> None:
        """Read the boundary data from file.

        Parameters
        ----------
        fo : io.TextIO
            File object.
        """
        pass


class BoundaryTypeBC(BoundaryType):
    """Base class for handling Boundary Type data coming from BC files."""

    def __init__(self, line: str) -> None:
        # docstring inherited
        super().__init__(line)
        self.id = re.findall(r'^"?BC\d{6}', line)[0]
        self.id = self.id.strip('"')
        line_ = re.sub(r'^"/BC\d{6}:\s*', '', line)
        if re.findall(r'[A-Za-z]{2} BC in ', line_):
            line_ = re.sub(r'[A-Za-z]{2} BC in ', '', line_)
            if 'Tabular data' in line_:
                i = line_.index('Tabular data')
                self.gis_file = Path(line_[:i].strip(' .'))
                line_ = line_[i:]
        if 'Tabular data' in line_:
            line_ = line_.replace('Tabular Data from file ', '')
            if ' and name ' in line_:
                i = line_.index(' and name ')
                self.bc_file = Path(line_[:i].strip(' ."'))
                line_ = line_[i:]
        if 'and name ' in line_:
            line_ = line_.replace('and name ', '')
            if re.findall(r'( (?:and|in) database )', line_):
                text = re.findall(r'(?: (?:and|in) database )', line_)[0]
                i = line_.index(text)
                self.name = line_[:i].strip(' "')
                line_ = line_[i:]
        if re.findall(r'( (?:and|in) database )', line_):
            line_ = re.sub(r'( (?:and|in) database )', '', line_)
            self.bc_dbase = Path(line_.strip(' ."'))
        if self.name:
            self.valid = True

    def read(self, fo: io.TextIO) -> None:
        # docstring inherited
        _, self.col1_header, self.col2_header = [x.strip('\n\t "') for x in fo.readline().split(',')]
        if 'm' in self.col2_header:
            self.units = 'metric'
        elif 'ft' in self.col2_header:
            self.units = 'us customary'

        for _ in range(self.header_line_count - 1):
            next(fo)
        data = []
        for line in fo:
            if not line.strip():
                break
            elif '"' in line:
                continue
            data.append(line.strip().split(',')[1:])
        self.values = np.array(data, dtype=float)
        if not self.values.size:
            self.valid = False


class BoundaryTypeQT(BoundaryTypeBC):
    """Class for handling QT type boundary data."""

    def __init__(self, line: str) -> None:
        super().__init__(line)
        self.type = 'QT'


class BoundaryTypeHT(BoundaryTypeBC):
    """Class for handling HT type boundary data."""

    def __init__(self, line: str) -> None:
        super().__init__(line)
        self.type = 'HT'


class BoundaryTypeHQ(BoundaryTypeBC):
    """Base class for handling HQ type boundary data."""

    def __init__(self, line: str) -> None:
        super().__init__(line)
        self.header_line_count = 1
        self.type = 'HQ'
        self.index_name = 'Flow'
        if not self.name:
            self.name = self.id
            self.valid = True


class BoundaryTypeSA(BoundaryTypeBC):
    """Base class for handling SA type boundary data."""

    def __init__(self, line: str) -> None:
        super().__init__(line)
        self.type = 'SA'


class BoundaryTypeRF(BoundaryTypeBC):
    """Base class for handling RF type boundary data."""

    def __init__(self, line: str) -> None:
        super().__init__(line)
        self.type = 'RF'

    def read(self, fo: io.TextIO) -> None:
        super().read(fo)
        if not self.valid:
            return
        a1 = sum([[x, x] for x in self.values[:, 0]], [])
        a1 = a1[1:-1]
        a2 = sum([[x, x] for x in self.values[:, 1]], [])
        a2 = a2[2:]
        self.values = np.array([a1, a2]).T
