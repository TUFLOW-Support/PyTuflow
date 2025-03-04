from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Union, Generator

import numpy as np
import pandas as pd

from ..results import ResultTypeError
from .map_output import PointLocation, LineStringLocation
from .grid import Grid
from .helpers.nc_grid_var import NCGridVar
from .._pytuflow_types import PathLike, TimeLike

try:
    from netCDF4 import Dataset
    has_nc = True
except ImportError:
    Dataset = 'Dataset'
    has_nc = False


class NCGrid(Grid):
    """Class for reading netCDF grid outputs (NC) from TUFLOW, though any CF-compliant netCDF file should work.

    The ``NCGrid`` class will only load header information from the NC file on initialisation, this makes the class
    cheap to initialise.

    The netCDF4 library is required to use this class.

    Parameters
    ----------
    fpath : PathLike
        Path to the netCDF file.

    Raises
    ------
    ResultTypeError
        Raises :class:`pytuflow.results.ResultTypeError` if the file does not look like a ``NCGrid`` file, or
        if the file is empty or locked by another program.

    Examples
    --------
    >>> from pytuflow import NCGrid
    >>> nc = NCGrid('./path/to/nc')

    Get all the data types available in the netCDF file:

    >>> nc.data_types()
    ['water level', 'depth', 'velocity', 'z0', 'max water level', 'max depth', 'max velocity', 'max z0', 'tmax water level']

    Get only the temporal data types:

    >>> nc.data_types('temporal')
    ['water level', 'depth', 'velocity', 'z0']

    Get only the vector data types:

    >>> nc.data_types('vector')
    ['velocity', 'max velocity']

    Get all the available times in the netCDF file:

    >>> nc.times()
    [0.0, 0.08333, 0.1667, 0.25, 0.3333, 0.4167, 0.5]

    Get the water level time-series data for a given point defined in a shapefile:

    >>> nc.time_series('/path/to/point.shp', 'water level')
    time     water level/pnt1
    0.00000               NaN
    0.08333               NaN
    0.16670               NaN
    0.25000               NaN
    0.33330         44.125675
    0.41670         44.642513
    0.50000         45.672554
    0.58330         46.877666

    Get a water level section from a line defined in a shapefile at time 0.5 hrs:

    >>> nc.section('/path/to/line.shp', 'water level', 0.5)
           offset  water level/Line 1
    0    0.000000           45.994362
    1    1.495967           45.994362
    2    1.495967           45.636654
    3    4.159921           45.636654
    4    4.159921           45.592628
    5    6.804385           45.592628
    6    6.804385           45.624744
    7    6.823876           45.624744
    8    6.823876           45.583813
    9    9.487831           45.583813
    10   9.487831           45.560959
    """

    def __init__(self, fpath: PathLike):
        super().__init__(fpath)
        self.fpath = Path(fpath)
        self._loaded = False
        self._stnd2var = {}
        self._nc = None

        #: str: The units of time in the netCDF file.
        self.time_units = 'h'

        if not has_nc:
            raise ImportError('netCDF4 is not installed.')

        if not self.fpath.exists():
            raise FileNotFoundError(self.fpath)

        if not self._looks_like_this(self.fpath):
            raise ResultTypeError(f'{self.fpath} does not look like a netCDF grid file or could be empty or locked by another program.')

        self._initial_load()

    @staticmethod
    def _looks_like_this(fpath: PathLike) -> bool:
        try:
            for _ in NCGrid._nc_grid_layers(fpath):
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _looks_empty(fpath: PathLike) -> bool:
        return False

    @staticmethod
    def _nc_grid_layers(fpath: PathLike) -> Generator[NCGridVar, None, None]:
        with Dataset(fpath, 'r') as nc:
            for varname in nc.variables:
                nc_var = NCGridVar(nc, varname)
                if nc_var.valid:
                    yield nc_var

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns a list of times for the given filter.

        The ``filter_by`` argument can be used to filter the times by a given data type. In most cases (out of TUFLOW)
        all the times are the same for all data types, so ``filter_by`` is not necessary.

        Parameters
        ----------
        filter_by : str, optional
            Filter the times by a given string.
        fmt : str, optional
            The format for the time values. Options are 'relative' or 'absolute'.

        Returns
        -------
        list[TimeLike]
            The list of times.

        Examples
        --------
        >>> nc.times()
        [0.0, 0.016666666666666666, ..., 3.0]
        """
        return super().times(filter_by, fmt)

    def data_types(self, filter_by: str = None) -> list[str]:
        """Return the available data types for the given filter.

        The available filters are:

        * ``None`` - no filter, return all available data types
        * ``scalar/vector`` - filter by scalar or vector data types
        * ``max/min`` - filter by data types that have maximum or minimum values
        * ``static/temporal`` - filter by static or temporal data types

        Filters can be combined by delimiting with a forward slash, e.g. ``'scalar/max'``.

        Parameters
        ----------
        filter_by : str, optional
            The filter to apply to the data types.

        Returns
        -------
        list[str]
            The list of data types available.

        Examples
        --------
        >>> nc.data_types()
        ['water level', 'depth', 'velocity', 'z0', 'max water level', 'max depth', 'max velocity', 'max z0', 'tmax water level']

        Get only the temporal data types:

        >>> nc.data_types('temporal')
        ['water level', 'depth', 'velocity', 'z0']

        Get only the vector data types:

        >>> nc.data_types('vector')
        ['velocity', 'max velocity']
        """
        return super().data_types(filter_by)

    def time_series(self, locations: PointLocation, data_types: Union[str, list[str]],
                    time_fmt: str = 'relative') -> pd.DataFrame:
        self._load()
        with self._open() as self._nc:
            return super().time_series(locations, data_types, time_fmt)

    def section(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        self._load()
        with self._open() as self._nc:
            return super().section(locations, data_types, time)

    def curtain(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``NCGrid`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support curtain plotting.')

    def profile(self, locations: PointLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``NCGrid`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support vertical profile plotting.')

    @contextmanager
    def _open(self):
        with Dataset(self.fpath) as nc:
            yield nc

    def _initial_load(self):
        self.name = self.fpath.stem
        with self._open() as nc:
            self.reference_time = self._reference_time(nc)
            self._load_info(nc)

    def _reference_time(self, nc: Dataset) -> datetime:
        if 'time' not in nc.variables:
            return
        units = nc.variables['time'].units
        if 'hour' in units:
            self.time_units = 'h'
        elif 'second' in units:
            self.time_units = 's'
        else:
            self.time_units = units.split(' ')[0]

        return self._parse_time_units_string(units, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', '%Y-%m-%d %H:%M:%S')[0]

    def _load_info(self, nc: Dataset):
        d = {'data_type': [], 'type': [], 'is_max': [], 'is_min': [], 'static': [], 'start': [], 'end': [], 'dt': [],
             'dx': [], 'dy': [], 'ox': [], 'oy': [], 'ncol': [], 'nrow': []}
        for varname in nc.variables:
            var = NCGridVar(nc, varname)
            if not var.valid:
                continue
            if var.is_vec_dir:  # skip direction variables, recording the magnitude in the info dataframe is enough
                continue
            stnd = self._get_standard_data_type_name(var.name)
            self._stnd2var[stnd] = varname
            d['data_type'].append(stnd)
            d['type'].append(var.type)
            d['is_max'].append(var.is_max)
            d['is_min'].append(var.is_min)
            d['static'].append(var.static)
            if var.static:
                d['start'].append(0)
                d['end'].append(0)
                d['dt'].append(0)
            else:
                dif = np.diff(var.times) * 3600.
                if np.isclose(dif[:-1], dif[0], atol=0.01, rtol=0).all():
                    dt = float(np.round(dif[0], decimals=2))
                else:
                    dt = tuple(var.times)
                start = float(var.times[0])
                end = float(var.times[-1])
                d['start'].append(start)
                d['end'].append(end)
                d['dt'].append(dt)
            d['dx'].append(var.dx)
            d['dy'].append(var.dy)
            d['ox'].append(var.ox)
            d['oy'].append(var.oy)
            d['ncol'].append(var.ncol)
            d['nrow'].append(var.nrow)

        self._info = pd.DataFrame(d)

    def _load(self):
        if self._loaded:
            return
        self._loaded = True

    def _value(self, n: int, m: int, timeidx: int, dtype: str) -> float:
        if n < 0 or m < 0:
            return np.nan
        varname = self._stnd2var[dtype]
        val = self._nc.variables[varname][timeidx, m, n]
        if np.ma.is_masked(val):
            return np.nan
        return float(val)
