import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Union

import pandas as pd

try:
    from netCDF4 import Dataset
except ImportError:
    Dataset = None

from ..abc.time_series import TimeSeries
from ..time_util import nc_time_series_reference_time


ID = {'flows_1d': 'flow_1d'}


class TPCTimeSeriesNC(TimeSeries):

    def __init__(self, fpath: Union[str, Path], id: str) -> None:
        super().__init__()
        self._df = None
        self._id = ID.get(id, id)
        self.time_units = ''
        self.fpath = Path(fpath)
        self.load()

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Time Series (NC): {self.fpath.stem}>'
        return '<TPC Time Series (NC)>'

    @property
    def df(self):
        if self._df is None:
            if Dataset is None:
                raise ModuleNotFoundError('netCDF4 is not installed')
            self._df = pd.DataFrame(self.timesteps('relative'), columns=['Time (h)'])
            self._df.set_index('Time (h)', inplace=True)
            with Dataset(self.fpath) as nc:
                df = pd.DataFrame(nc.variables[self._id][:].transpose(), columns=self._names())
                df['Time (h)'] = self.timesteps('relative')
                df.set_index('Time (h)', inplace=True)
            self._df = pd.concat([self._df, df], axis=1)
        return self._df

    def load(self):
        if Dataset is None:
            raise ModuleNotFoundError('netCDF4 is not installed')
        self.reference_time, self.time_units = nc_time_series_reference_time(self.fpath)

    def timesteps(self, dtype: str) -> list[Union[float, datetime]]:
        if dtype == 'absolute':
            if self.time_units == 'h':
                return [self.reference_time + timedelta(hours=x) for x in self._timesteps()]
            elif self.time_units == 'm':
                return [self.reference_time + timedelta(minutes=x) for x in self._timesteps()]
            elif self.time_units == 's':
                return [self.reference_time + timedelta(seconds=x) for x in self._timesteps()]
            else:
                raise ValueError(f'Unknown time unit: {self.time_units}')
        elif dtype == 'relative':  # relative
            if self.time_units == 'h':
                return self._timesteps()
            elif self.time_units == 'm':
                return [x * 60 for x in self._timesteps()]
            elif self.time_units == 's':
                return [x * 3600 for x in self._timesteps()]
            else:
                raise ValueError(f'Unknown time unit: {self.time_units}')
        else:
            raise ValueError(f'Unknown time type: {dtype}')

    def _timesteps(self) -> list[float]:
        if Dataset is None:
            raise ModuleNotFoundError('netCDF4 is not installed')
        with Dataset(self.fpath) as nc:
            return nc.variables['time'][:]

    def _names(self) -> list[str]:
        NODE_RES = ['water_levels_1d', 'energy_levels_1d']
        if re.findall(r'_1d$', self._id):
            if self._id.lower() in NODE_RES:
                return self._extract_nc_names('node_names')
            else:
                return self._extract_nc_names('channel_names')
        elif re.findall(r'_2d$', self._id):
            return self._extract_nc_names(f'name_{self._id}')
        elif re.findall(r'_rl$', self._id):
            return self._extract_nc_names(f'name_{self._id}')
        else:
            raise ValueError(f'Unknown result type: {self._id}')

    def _extract_nc_names(self, id: str) -> list[str]:
        if Dataset is None:
            raise ModuleNotFoundError('netCDF4 is not installed')
        with Dataset(self.fpath) as nc:
            return [''.join([y.decode('utf-8') for y in x]).strip() for x in nc.variables[id][:]]
