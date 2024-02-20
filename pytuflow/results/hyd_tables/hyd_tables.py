import io
import re
from typing import TextIO, Union
from pathlib import Path

import pandas as pd

from .hyd_tables_cross_sections import HydTableCrossSection
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
            self.cross_sections.load_time_series()
            while not self._channels_finished:
                self._read_channel(f)
            self.channels.load_time_series()

    def init_iterator(self, *args) -> Iterator:
        """Initialise the class iterator."""
        if args:
            return Iterator(*args)
        return Iterator(self.cross_sections, self.channels)

    def result_types(self, id: Union[str, list[str]] = '', domain: str = '') -> list[str]:
        id = self._correct_id(id)  # need to convert cross-section names to their ids
        result_types = super().result_types(id, domain)

        # don't pass back a bunch of different 'K' types, simply pass back one 'K' type (e.g. K (n=1.000))
        for i, res_type in enumerate(result_types.copy()):
            if res_type.startswith('K'):
                if 'K' in result_types[:i]:
                    result_types.remove(res_type)
                else:
                    result_types[i] = 'K'
        return result_types

    def time_series(self,
                    id: Union[str, list[str]],
                    result_type: Union[str, list[str]],
                    domain: str = None,
                    use_common_index: bool = True
                    ) -> pd.DataFrame:
        if not isinstance(id, list):
            id = [id] if id else []
        id_ = id.copy()
        id = self._correct_id(id)
        correct_df_header = id_ != id
        df = super().time_series(id, result_type, domain, use_common_index)
        if correct_df_header:  # convert cross-section ids (e.g. 'XS00001') back to name (e.g. '1d_xs_C109')
            ids = [list(x) for x in df.columns.values.tolist()]
            for xsid in ids:
                name = self.cross_sections.xsid2name(xsid[2])
                if name in id_:
                    xsid[2] = name
            df.columns = pd.MultiIndex.from_tuples(ids, names=df.columns.names)

        return df

    def _correct_id(self, id: Union[str, list[str]] = '') -> list[str]:
        """Convert cross-section names to their ids as they are stored in the 1d_ta_tables_check.csv file."""
        if not id:
            return []
        if not isinstance(id, list):
            id = [id]
        for i, id_ in enumerate(id):
            if id_.lower() in [x.lower() for x in self.cross_sections.ids(None)]:
                if self.cross_sections.has_unique_names:
                    id[i] = self.cross_sections.name2xsid(id_)
                else:
                    raise Exception('Cross section names are not unique. Use the id instead: e.g. XS00001.')
        return id

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
                    a = line_.split(',')
                    try:
                        float(a[0])
                    except ValueError:
                        if a[0] != '"Bed"' and a[0] != '' and a[0] != '""' and a[0] != '"Inactive"':
                            a[-1] = a[-1].strip()
                            a.append('"Message"\n')
                            line_ = ','.join(a)
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
                    a = line_.split(',')
                    try:
                        float(a[0])
                    except ValueError:
                        if a[0] != '"Bed"' and a[0] != '' and a[0] != '""' and a[0] != '"Inactive"':
                            a[-1] = a[-1].strip()
                            a.append('"Message"\n')
                            line_ = ','.join(a)
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
