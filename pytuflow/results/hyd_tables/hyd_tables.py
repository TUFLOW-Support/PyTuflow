import io
import re
from typing import TextIO
from pathlib import Path

from .hyd_table_cross_sections import HydTableCrossSection
from .hyd_tables_channels import HydTableChannels
from ..abc.time_series_result import TimeSeriesResult
from ..iterator_util import Iterator
from ..types import PathLike


class HydTables(TimeSeriesResult):
    """
    1d_ta_tables_check.csv

    Subclasses TimeSeriesResult so that it can be called using the same
    methods.
    """

    def __init__(self, fpath: PathLike):
        self.cross_sections = None
        self.tcf = None
        self._cross_sections_finished = False
        self._channels_finished = False
        super().__init__(fpath)

    def __repr__(self) -> str:
        if hasattr(self, 'fpath') and self.fpath is not None:
            return f'<HydTables: {self.fpath.stem}>'
        return '<HydTables>'

    def load(self):
        self.cross_sections = HydTableCrossSection()
        self.channels = HydTableChannels()
        self.sim_id = re.sub(r"_1d_ta_tables_check$", '', self.fpath.stem)
        with self.fpath.open() as f:
            self.tcf = Path(f.readline().split('"')[1].strip())
            while not self._cross_sections_finished:
                self._read_cross_section(f)
            while not self._channels_finished:
                self._read_channel(f)

    def init_iterator(self, *args) -> Iterator:
        """Initialise the class iterator."""
        if args:
            return Iterator(*args)
        return Iterator(self.cross_sections, self.channels)

    def _read_cross_section(self, fo: TextIO) -> None:
        buffer = io.StringIO()
        while True:  # must use while loop as using for loop disables tell() which means we can't rewind a line
            marker = fo.tell()
            line = fo.readline()
            if re.findall(r'^"Section\s', line):
                info = re.split('[\[\] ]', line)  # split by [ ] and space
                xs_id = info[1].strip()
                xs_source = Path(info[-2].strip())
                xs_type = info[3].strip().upper()
                if len(xs_type) > 2:
                    xs_type = xs_type[:2]
                xs_name = self._xs_name(xs_source, info[6])
                while True:  # must use while loop as using for loop disables tell() which means we can't rewind a line
                    line_ = fo.readline()
                    if line_ == '\n' or not line_:
                        break
                    buffer.write(line_)
                buffer.seek(0)
                self.cross_sections.append(buffer, xs_id, xs_name, xs_source, xs_type)
                return
            elif re.findall(r'^Channel', line):
                self._cross_sections_finished = True
                fo.seek(marker)  # rewind one line so that channel routine can read in this line properly
                return
            elif not line:
                self._cross_sections_finished = True
                return

    def _read_channel(self, fo: TextIO) -> None:
        buffer = io.StringIO()
        while True:
            marker = fo.tell()
            line = fo.readline()
            if re.findall(r'^Channel', line):
                info = re.split('[\[\] ]', line)
                channel_id = info[1].strip()
                cross_sections = re.findall(r'XS\d{5}', line)
                xs1 = cross_sections[0]
                xs2 = None
                if len(cross_sections) > 1:
                    xs2 = cross_sections[1]
                while True:
                    line_ = fo.readline()
                    if line_ == '\n' or not line_:
                        break
                    buffer.write(line_)
                buffer.seek(0)
                self.channels.append(buffer, channel_id, xs1, xs2)
                return
            elif not line:
                self._channels_finished = True
                return

    def _xs_name(self, fpath: Path, info: str) -> str:
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

    def _find_header_index(self, fpath: Path, ind: int) -> int:
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
