import io
import os
import re
from pathlib import Path
from typing import TextIO

import pandas as pd


class HydTablesCrossSectionProvider:

    def __init__(self):
        #: bool: Whether the provider is finished reading
        self.finished = False
        #: dict: The database of cross-sections
        self.database = {}

    def name2id(self, name: str) -> str:
        for xs_id, xs in self.database.items():
            if xs.name == name:
                return xs_id
        return ''

    def read_next(self, fo: TextIO):
        buffer = io.StringIO()
        while True:  # must use while loop as using for loop disables tell() which means we can't rewind a line
            marker = fo.tell()
            line = fo.readline()
            if re.findall(r'^"Section\s', line):
                info = re.split(r'[\[\] ]', line)  # split by [ ] and space
                xs_id = info[1].strip()
                xs_source = info[-2].strip()
                if os.name != 'nt' and '\\' in xs_source:
                    xs_source = xs_source.replace('\\', '/')
                xs_source = Path(xs_source)
                xs_type = info[3].strip().upper()
                if len(xs_type) > 2:
                    xs_type = xs_type[:2]
                xs_name = self._cross_section_name(xs_source, info[6])
                while True:  # must use while loop as using for loop disables tell() which means we can't rewind a line
                    line_ = fo.readline()
                    if line_ == '\n' or not line_ or [x for x in line_.split(',') if x][0] == '\n':
                        break
                    a = line_.split(',')
                    try:
                        float(a[0])
                    except ValueError:
                        if a[0] != '"Bed"' and a[0] != '' and a[0] != '""' and a[0] != '"Inactive"':
                            a[-1] = a[-1].strip()
                            a = [x for i, x in enumerate(a) if x or i == 4]  # i == 4 is meant to be blank
                            a.append('"Message"\n')
                            line_ = ','.join(a)
                    buffer.write(line_)
                buffer.seek(0)
                self.add_cross_section_entry(buffer, xs_id, xs_name, xs_type)
                return
            elif re.findall(r'^Channel', line):
                self.finished = True
                fo.seek(marker)  # rewind one line so that channel routine can read in this line properly
                return
            elif not line:
                self.finished = True
                return

    def add_cross_section_entry(self, fo: TextIO, xs_id: str, xs_name: str, xs_type: str):
        df = pd.read_csv(fo)
        df.columns = df.columns.str.lower()
        if xs_type == 'XZ':
            df_xs = df[df.columns[:4]].dropna()
            df_proc = df[df.columns[5:-1]].dropna(how='all').copy()
            df_proc.rename(columns={'elevation.1': 'elevation'}, inplace=True)
        else:
            df_xs = pd.DataFrame(columns=['points', 'distance', 'elevation', 'manning n'])
            df_proc = df[df.columns[:-1]].dropna(how='all')
        df_xs.set_index('distance', inplace=True)
        df_xs.columns = df_xs.columns.str.split('(', n=1).str[0]
        df_proc.set_index('elevation', inplace=True)
        df_proc.columns = df_proc.columns.str.split('(', n=1).str[0]
        db_entry = CrossSectionEntry(xs_id, xs_name, xs_type, df_xs, df_proc)
        self.database[xs_id] = db_entry

    def _cross_section_name(self, fpath: Path, info: str) -> str:
        if not info.strip():
            return fpath.stem
        inds = info.split(',')
        for i, ind in enumerate(inds[:]):
            try:
                inds[i] = int(ind) - 1  # will be 1 based fortran indexing
            except (ValueError, TypeError):
                return fpath.stem
        header_ind = self._find_header_index(fpath, max(inds))
        if header_ind == -1:
            return fpath.stem
        with fpath.open() as f:
            for i, line in enumerate(f):
                if i == header_ind:
                    return line.split(',')[inds[1]].strip()
        return ''

    def _find_header_index(self, fpath: Path, ind: int) -> int:
        if fpath.exists():
            with fpath.open() as f:
                for i, line in enumerate(f):
                    data = line.split(',')
                    if len(data) < ind + 1:
                        continue
                    try:
                        float(data[ind])
                        return i - 1  # -1 because the header line will be the line before the data
                    except ValueError:
                        continue
        return -1


class CrossSectionEntry:
    """Class for handling individual cross-section entries in HydTableCrossSection.

    Parameters
    ----------
    xs_id : str
        Cross-section ID (typically XS00001, XS00002, etc.).
    xs_name : str
        Name of the cross-section - usually the source file name.
    xs_type : str
        Type attribute of the cross-section (XZ, HW, etc).
    df_xs : pd.DataFrame
        Cross-section data.
    df_proc : pd.DataFrame
        Processed cross-section data.
    """

    def __init__(self, xs_id: str, xs_name: str, xs_type: str, df_xs: pd.DataFrame, df_proc: pd.DataFrame) -> None:
        self.id = xs_id
        self.name = xs_name
        self.type = xs_type
        self.df_xs = df_xs
        self.has_xs = not self.df_xs.empty
        self.df_proc = df_proc

    def __repr__(self) -> str:
        return f'<CrossSectionEntry: {self.id}>'
