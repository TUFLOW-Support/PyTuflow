from datetime import datetime, timedelta
from pathlib import Path
import re

import numpy as np

try:
    from netCDF4 import Dataset
    has_netcdf4 = True
except ImportError:
    Dataset = 'Dataset'
    has_netcdf4 = False

from ..._pytuflow_types import TimeLike
from ...util import pytuflow_logging


class FVBCTideNCProvider:
    """Class for providing data from the netCDF file to the FVBCTideProvider class."""

    def __init__(self, path: Path, use_local_time: bool) -> None:
        """
        Parameters
        ----------
        path : Path
            Path to the netCDF file.
        use_local_time : bool
            Use local time.
        """
        if not has_netcdf4:
            raise ImportError('NetCDF4 is not installed, unable to initialise FVBCTideNCProvider class.')
        #: Path: Path to the netCDF file.
        self.path = path
        #: list: List of result labels.
        self.labels = []
        #: bool: Use local time.
        self.use_local_time = use_local_time
        #: datetime: Reference time.
        self.reference_time = datetime(1990, 1, 1)
        #: str: Time units.
        self.units = 'd'
        #: str: Timezone.
        self.tz = 'UTC'
        self._timevar = 'time'
        self._nc = None
        self._units = ''  # full units string from nc file
        self._timesteps = None  # cache this data so we don't have to read it every time it's requested

    def __repr__(self):
        return f'FVBCTideNCProvider({self.path.name})'

    def open(self) -> None:
        """Open the netCDF file.

        Returns
        -------
        None
        """
        self._nc = Dataset(self.path)
        self.load()

    def close(self) -> None:
        """Cloase the netCDF file.

        Returns
        -------
        None
        """
        if self._nc:
            self._nc.close()
            self._nc = None

    def load(self) -> None:
        """Loads the netCDF file. Must be opened first.

        Returns
        -------
        None
        """
        if self.use_local_time and 'local_time' not in self._nc.variables:
            pytuflow_logging.get_logger().warning('Local time not available in netCDF file. Using UTC time instead.')
        self.use_local_time = 'local_time' in self._nc.variables and self.use_local_time
        self._timevar = 'local_time' if self.use_local_time else 'time'
        self._get_units()
        self.labels = [self._strip_label(k) for k, v in self._nc.variables.items() if v.ndim == 2 and v.dimensions[0] == 'time']

    def is_empty(self) -> bool:
        """Returns True if the NC file is empty.

        Returns
        -------
        bool
        """
        return bool(self.labels)

    def is_fv_tide_bc(self) -> bool:
        """Returns True if the netCDF file looks like a FV tide boundary condition file.

        Returns
        -------
        bool
        """
        return 'time' in self._nc.dimensions and len(self._nc.dimensions) > 1

    def get_timesteps(self, fmt: str) -> np.ndarray:
        """Get the timesteps from the netCDF file.

        Parameters
        ----------
        fmt : str
            Format of the timesteps. Options are 'relative', 'absolute' (or 'datetime' can also be used as an alias).

        Returns
        -------
        np.ndarray
            Array of timesteps.
        """
        if fmt == 'relative':
            return self._get_relative_timesteps()
        else:  # absolute or datetime
            return self._get_absolute_timesteps()

    def number_of_points(self, label: str) -> int:
        """Returns the number of points along the node string for a given label.

        Parameters
        ----------
        label : str
            Node string ID.

        Returns
        -------
        int
            Number of points.
        """
        ch_label = self._chainage_dim_label(label)
        return self._nc.dimensions[ch_label].size

    def get_chainages(self, label: str) -> np.ndarray:
        """Returns the chainages for a given label (label is the node string ID).

        Parameters
        ----------
        label : str
            Node string ID.

        Returns
        -------
        np.ndarray
            Array of chainages.
        """
        chlabel = self._chainage_label(label)
        chainages = self._nc.variables[chlabel][:]
        return self._convert_from_masked_array(chainages)

    def get_section(self, label: str, time: TimeLike) -> np.ndarray:
        """Get the long section data along a node string at a given timestep.

        Parameters
        ----------
        label : str
            Node string ID.
        time : TimeLike
            Time of the timestep. Can be a float value (hours), or a datetime object

        Returns
        -------
        np.ndarray
            Array of chainages and water levels.
        """
        sect_label = self._section_label(label)
        time_ind = self._get_closest_timestep_index(time)
        y = self._nc.variables[sect_label][time_ind, :]
        x = np.ma.masked_where(y.mask, self.get_chainages(label))
        x = x.reshape((x.shape[0], 1))
        y = y.reshape((y.shape[0], 1))
        return np.ma.append(x, y, axis=1)

    def get_time_series(self, label: str, point_ind: int, time_fmt: str) -> np.ndarray:
        """Returns the time series water level data for a given node string ID and point index.

        Parameters
        ----------
        label : str
            Node string ID.
        point_ind : int
            Point index.
        time_fmt : str
            Format of the returned timesteps.
            Options are 'relative', 'absolute' (or 'datetime' can also be used as an alias).

        Returns
        -------
        np.ndarray
            Array of timesteps and water levels.
        """
        sect_label = self._section_label(label)
        if time_fmt == 'relative':
            timesteps = self._get_relative_timesteps()
        else:
            timesteps = self._get_absolute_timesteps()
        y = self._nc.variables[sect_label][:, point_ind]
        x = timesteps.reshape((timesteps.shape[0], 1))
        y = y.reshape((y.shape[0], 1))
        return np.ma.append(x, y, axis=1)

    def get_time_series_data_raw(self, label: str) -> np.ndarray:
        """Returns the time series data for the given label as the raw numpy array extracted
        from the netCDF file.

        Parameters
        ----------
        label : str
            The boundary label / name within the netCDF file.

        Returns
        -------
        np.ndarray
        """
        sect_label = self._section_label(label)
        data = self._nc.variables[sect_label][:]
        if isinstance(data, np.ma.MaskedArray):
            data = data.filled(np.nan)
        return data

    @staticmethod
    def _strip_label(label: str) -> str:
        x = re.sub(r'^ns', '', label)
        x = re.sub(r'_wl$', '', x)
        return x

    @staticmethod
    def _section_label(label: str) -> str:
        return f'ns{label}_wl'

    @staticmethod
    def _chainage_label(label: str) -> str:
        return f'ns{label}_chainage'

    @staticmethod
    def _chainage_dim_label(label: str) -> str:
        return f'ns{label}_chain'

    def _get_closest_timestep_index(self, time: TimeLike, tol: float = 0.01) -> int:
        if isinstance(time, datetime):
            time = (time - self.reference_time).total_seconds() / 3600
        timesteps = self._get_relative_timesteps()
        a = np.isclose(time, timesteps, atol=tol, rtol=0.)
        if a[a].any():
            # noinspection PyTypeChecker
            return np.where(a)[0][0]
        else:
            if time < timesteps.min():
                return 0
            elif time > timesteps.max():
                return timesteps.size - 1
            i = np.argmin(np.absolute(timesteps - time))
            if timesteps[i] < time:
                return i
            return max(i - 1, 0)

    def _get_relative_timesteps(self) -> np.ndarray:
        # return in hours
        if self.units == 'd':
            return self._get_timesteps() * 24
        elif self.units == 's':
            return self._get_timesteps() / 3600
        return self._get_timesteps()

    def _get_absolute_timesteps(self) -> np.ndarray:
        return np.array([self.reference_time + timedelta(hours=float(ts)) for ts in self._get_relative_timesteps()])

    def _get_timesteps(self) -> np.ndarray:
        if self._timesteps is None:
            self._timesteps = self._nc.variables[self._timevar][:]
            self._timesteps = self._convert_from_masked_array(self._timesteps)
        return self._timesteps

    def _get_units(self) -> None:
        self._units = self._nc.variables[self._timevar].units
        rt = re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', self._units)
        if rt:
            self.reference_time = datetime.strptime(rt[0], '%Y-%m-%d %H:%M:%S')  # keep timezone naive for now (TUFLOW Viewer assumes UTC)
        if 'day' in self._units:
            self.units = 'd'
        elif 'hour' in self._units:
            self.units = 'h'
        elif 'sec' in self._units:
            self.units = 's'
        self.tz = self._nc.variables[self._timevar].timezone

    def _convert_from_masked_array(self, a: np.ma.MaskedArray) -> np.ndarray:
        # noinspection PyUnreachableCode
        if not isinstance(a, np.ma.MaskedArray):
            return a
        if not a.mask.any():
            return a.filled(0)
        if len(a.shape) == 1 or a.shape[1] == 1:
            return self._convert_from_masked_array_1d(a)
        return a

    @staticmethod
    def _convert_from_masked_array_1d(a: np.ma.MaskedArray) -> np.ndarray:
        x = np.arange(0, a.shape[0])
        xp = x[~a.mask]
        fp = a[~a.mask].filled(0)
        return np.interp(x, xp, fp)
