from datetime import datetime
from pathlib import Path
from typing import Generator, Union

import numpy as np
import pandas as pd

from .zzn import ZZN


class FM_ResultDriver:

    def __new__(cls, fpath: Path):
        if fpath.suffix.lower() == '.csv':
            csv_version = FM_ResultDriver.fm_csv_version(fpath)
            if csv_version == 'gui':
                cls = FM_GuiCSVResult
            elif csv_version == 'python':
                cls = FM_PythonCSVResult
        elif fpath.suffix.lower() == '.zzn':
            cls = FM_ZZNResult
        return object.__new__(cls)

    @staticmethod
    def fm_csv_version(fpath: Path) -> str:
        with fpath.open() as f:
            line1, line2, line3 = None, None, None
            for line in f:
                data = line.split(',')
                if len(data) > 2 and not data[0].strip() and data[1].strip() and data[1].strip() == data[2].strip():
                    return 'python'
                if line1 == '\n' and line2 and 'time' in line.strip().lower():
                    return 'gui'
                else:
                    line2 = None
                if line1 == '\n':
                    line2 = line
                else:
                    line1 = None
                if line == '\n':
                    line1 = '\n'

    def __init__(self, fpath: Path) -> None:
        self.fpath = fpath
        self._reference_time = None
        self.df = None
        self.result_types = []
        self.timesteps = []
        self.load()

    def load(self) -> None:
        raise NotImplementedError

    @property
    def reference_time(self) -> Union[datetime, None]:
        return self._reference_time

    @reference_time.setter
    def reference_time(self, value: datetime) -> None:
        self._reference_time = value


class FM_GuiCSVResult(FM_ResultDriver):

    def __repr__(self) -> str:
        if isinstance(self.fpath, list):
            return f'<FM CSV GUI Export: {self.fpath[0].stem}>'
        return f'<FM CSV GUI Export>'

    @property
    def display_name(self) -> str:
        if self.header:
            _, fpath = [x.strip() for x in self.header.split('file', 1)]
            return Path(fpath).stem
        if self.fpath:
            return self.fpath.stem
        return ''

    def load(self) -> None:
        self.header = self.get_header()
        for res_type, ind, nrows in self.find_results():
            self.result_types.append(res_type)
            df = pd.read_csv(self.fpath, skiprows=ind, nrows=nrows)
            df.set_index('Time (hr)', inplace=True)
            df.columns = [f'{res_type}::{x}' for x in df.columns]
            if self.df is None:
                self.df = df
            else:
                self.df = pd.concat([self.df, df], axis=1)


    def get_header(self) -> Union[str, None]:
        with self.fpath.open() as f:
            line = f.readline()
            if 'Output data from file' in line:
                return line.strip()


    def find_results(self) -> Generator[tuple[str, int, int], None, None]:
        with self.fpath.open() as f:
            start, nrows, type_, next_  = None, None, None, False
            for i, line in enumerate(f):
                if not line.strip():
                    next_ = True
                elif next_:
                    type_ = line.strip()
                    next_ = False
                elif type_ and not start:
                    start = i

                if next_ and start:
                    yield type_, start, i - start - 1
                    start, type_ = None, None


class FM_PythonCSVResult(FM_ResultDriver):

    def __repr__(self) -> str:
        if isinstance(self.fpath, list):
            return f'<FM CSV Python Export: {self.fpath[0].stem}>'
        return f'<FM CSV Python Export>'

    def load(self) -> None:
        self.df = pd.read_csv(self.fpath, header=[0, 1, 2])
        self.df.columns = self.df.columns.map(lambda x: '::'.join([y for y in x if 'Unnamed' not in y]))
        self.df.set_index('Time (hr)', inplace=True)
        for col_name in self.df.columns:
            type_, _ = col_name.split('::', 1)
            if type_.strip() not in self.result_types:
                self.result_types.append(type_.strip())
        self.timesteps = self.df.index.tolist()
        self.display_name = self.fpath.stem


class FM_ZZNResult(FM_ResultDriver):

    def __repr__(self) -> str:
        if isinstance(self.fpath, list):
            return f'<FM ZZN: {self.fpath[0].stem}>'
        return f'<FM ZZN>'

    def load(self) -> None:
        self.zzn = ZZN(self.fpath)
        self.ids = self.zzn.labels()
        self._timesteps = np.array([[x + 1, (x * self.zzn.output_interval()) / 3600] for x in range(self.zzn.timestep_count())])
        self.result_types = ['Flow', 'Stage', 'Froude', 'Velocity', 'Mode',  'State']
        for res_type in self.result_types:
            df = pd.DataFrame(self.zzn.get_time_series_data(res_type))
            df.columns = [f'{res_type}::{x}' for x in self.ids]
            df['Time (hr)'] = self._timesteps[:,1]
            df.set_index('Time (hr)', inplace=True)
            if self.df is None:
                self.df = df
            else:
                self.df = pd.concat([self.df, df], axis=1)
        self.display_name = self.fpath.stem
        self._reference_time = self.zzn.reference_time()

    @property
    def reference_time(self) -> Union[datetime, None]:
        return self._reference_time

    @reference_time.setter
    def reference_time(self, value: datetime) -> None:
        pass