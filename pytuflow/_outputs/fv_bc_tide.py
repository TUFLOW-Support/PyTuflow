import re
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

try:
    from netCDF4 import Dataset
    has_netcdf4 = True
except ImportError:
    Dataset = 'Dataset'
    has_netcdf4 = False

from .time_series import TimeSeries
from .._pytuflow_types import PathLike, TuflowPath, TimeLike
from .helpers.fv_bc_tide_provider import FVBCTideProvider
from ..gis import has_gdal
from ..misc import AppendDict
from ..util import pytuflow_logging
from ..results import ResultTypeError


logger = pytuflow_logging.get_logger()


class FVBCTide(TimeSeries):
    """Class for FV BC Tide input time-series data. Point objects are generated along each nodestring based on the
    given chainage in the NetCDF file. Each point will be given the same name as the nodestring with `_pt_N`
    appended to the end (where N is the point number based on the order in the NetCDF file).

    e.g. A nodestring called :code:`Ocean` with 5 chainages along the line with water level data will have the following
    point names: :code:`Ocean_pt_0`, :code:`Ocean_pt_1`, :code:`Ocean_pt_2`, :code:`Ocean_pt_3`, :code:`Ocean_pt_4`.

    By default, locat time is used if it is available in the NetCDF file. This can be changed to use UTC time instead
    by setting :code:`use_local_time=True` within the constructor.

    Parameters
    ----------
    nc_fpath : PathLike
        Path to the FV tide netCDF file.
    node_string_gis_fpath : PathLike
        Path to the GIS node string file.
    use_local_time : bool, optional
        Uses local time, by default True.

    Raises
    ------
    ResultTypeError
        Raises :class:`pytuflow.results.ResultTypeError` if the file does not look like a ``FVBCTide`` file.

    Examples
    --------
    Load TUFLOW FV tide boundary data - this requires the NetCDF data that contains the tabular data and the GIS file
    that contains the spatial location.

    >>> from pytuflow import FVBCTide
    >>> bndry = FVBCTide('path/to/fv_bc_tide.nc', 'path/to/fv_bc_tide.shp')

    Plot a time-series of water level from a location along the boundary:

    >>> bndry.time_series('Ocean_pt1', 'water level')
    time       point/water level/Ocean_pt_1
    289258.00                     -0.228474
    289258.25                     -0.196456
    289258.50                     -0.160042
    289258.75                     -0.119967
    289259.00                     -0.076996
    ...                                 ...
    290025.00                      0.073840
    290025.25                      0.018794
    290025.50                     -0.034604
    290025.75                     -0.085668
    290026.00                     -0.133717

    Plot the long section along the nodestring at a specific datetime (relative time in hours can also be used):

    >>> from datetime import datetime
    >>> bndry.section('Ocean', 'water level', datetime(2023, 1, 1, 12, 0, 0))
        branch_id node_string        offset  water level
    0           0       Ocean      0.000000    -0.136288
    1           0       Ocean   2665.236328    -0.136288
    2           0       Ocean   5330.472656    -0.136658
    3           0       Ocean   7995.708984    -0.137053
    4           0       Ocean  10660.945312    -0.137360
    5           0       Ocean  13326.181641    -0.137726
    6           0       Ocean  15991.417969    -0.138077
    7           0       Ocean  18656.654297    -0.138393
    8           0       Ocean  21321.890625    -0.138562
    9           0       Ocean  23987.126953    -0.138638
    10          0       Ocean  26652.363281    -0.138558
    11          0       Ocean  29317.599609    -0.138558
    """

    DOMAIN_TYPES = {}
    GEOMETRY_TYPES = {'2d': ['2d'], 'point': ['node', 'timeseries', 'point'],
                      'line': ['section', 'nodestring', 'line']}
    ATTRIBUTE_TYPES = {}
    ID_COLUMNS = ['id']

    def __init__(self, nc_fpath: PathLike, node_string_gis_fpath: PathLike, use_local_time: bool = True) -> None:
        super().__init__(nc_fpath)

        if not has_netcdf4:
            raise ImportError('NetCDF4 is not installed, unable to initialise FVBCTide class.')

        #: Path: Path to the FV tide netCDF file.
        self.nc_fpath = Path(nc_fpath)
        #: Path: Path to the GIS node string file.
        self.node_string_gis_fpath = TuflowPath(node_string_gis_fpath)
        #: bool: Uses local time.
        self.use_local_time = use_local_time
        #: FVBCTideProvider: FV BC Tide provider object.
        self.provider = None
        #: pd.DataFrame: Result objects
        self.objs = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt', 'domain'])
        #: int: Number of nodes
        self.node_count = 0
        #: int: Number of node strings
        self.node_string_count = 0

        if not self.nc_fpath.exists():
            raise FileNotFoundError(f'File not found: {self.nc_fpath}')
        if not self.node_string_gis_fpath.exists():
            raise FileNotFoundError(f'File not found: {self.node_string_gis_fpath}')
        if not has_gdal:
            raise ImportError('GDAL is required for FVBCTideProvider')

        # call before tpc_reader is initialised to give a clear error message if it isn't actually a .info time series file
        if not self._looks_like_this(self.nc_fpath):
            raise ResultTypeError(f'File does not look like a time series {self.__class__.__name__} file: {nc_fpath}')

        try:
            with self.node_string_gis_fpath.open_gis('r') as f:
                pass
        except Exception as e:
            raise Exception(e)

        # call after tpc_reader has been initialised so that we know the file can be loaded by the reader
        if self._looks_empty(nc_fpath):
            raise EOFError(f'File is empty or incomplete: {nc_fpath}')

        # private
        self._time_series_data = AppendDict()
        self._maximum_data = AppendDict()

        self._load()

    @staticmethod
    def _looks_like_this(fpath: Path) -> bool:
        # docstring inherited
        try:
            with Dataset(fpath) as nc:
                hastime = 'time' in nc.dimensions and len(nc.dimensions) > 1
                if not hastime:
                    return False
                vars = [x for x in nc.variables.keys() if re.findall(r'^ns.*_wl$', x)]
                has_res = len(vars) > 0
                return has_res
        except Exception:
            return False

    @staticmethod
    def _looks_empty(fpath: Path) -> bool:
        # docstring inherited
        with Dataset(fpath) as nc:
            return len(nc.dimensions['time']) == 0

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns all the available times for the given filter.

        The ``filter_by`` is an optional input that can be used to filter the return further. Valid filters
        for the ``FVBCTide`` class are:

        * :code:`None`: default - returns all available times
        * :code:`2d`: same as :code:`None` as class only contains 2D data
        * :code:`node` / code:`point`: returns only node times
        * :code:`nodestring` / code:`line`: returns only nodestring times
        * :code:`[id]`: returns only data types for the given ID.
        * :code:`[data_type]`: returns only times for the given data type.

        Parameters
        ----------
        filter_by : str, optional
            The string to filter the times by.
        fmt : str, optional
            The format for the times. Options are :code:`relative` or :code:`absolute`.

        Returns
        -------
        list[TimeLike]
            The available times in the requested format.

        Examples
        --------
        >>> bndry.times()
        [0.0, 0.016666666666666666, ..., 3.0]
        >>> bndry.times(fmt='absolute')
        [Timestamp('2021-01-01 00:00:00'), Timestamp('2021-01-01 00:01:00'), ..., Timestamp('2021-01-01 03:00:00')]
        """
        return super().times(filter_by, fmt)

    def ids(self, filter_by: str = None) -> list[str]:
        """Returns all the available IDs for the given filter.

        The ``filter_by`` argument can be used to add a filter to the returned IDs. Available filters objects for the
        ``FVBCTide`` class are:

        * :code:`None`: default - returns all IDs
        * :code:`2d`: same as :code:`None` as class only contains 2D data
        * :code:`node` / code:`point`: returns only node IDs
        * :code:`nodestring` / code:`line`: returns only nodestring IDs
        * :code:`timeseries`: returns only IDs that have time series data.
        * :code:`section`: returns only IDs that have section data (i.e. long plot data).
        * :code:`[data_type]`: returns only IDs for the given data type. Shorthand data type names can be used.

        Parameters
        ----------
        filter_by : str, optional
            The string to filter the IDs by.

        Returns
        -------
        list[str]
            The available IDs.

        Examples
        --------
        The below examples demonstrate how to use the filter argument to filter the returned IDs. The first example
        returns all IDs:

        >>> bndry.ids()
        ['Ocean_pt_0', 'Ocean_pt_1', 'Ocean_pt_2', 'Ocean_pt_3', 'Ocean_pt_4', 'Ocean']
        """
        return super().ids(filter_by)

    def data_types(self, filter_by: str = None) -> list[str]:
        """Returns all the available data types (result types) for the given filter.

        The ``filter_by`` is an optional input that can be used to filter the return further. Available
        filters for the ``FVBCTide`` class are:

        * :code:`None`: default - returns all available data types
        * :code:`2d`: same as :code:`None` as class only contains 2D data
        * :code:`node` / code:`point`: returns only node data types
        * :code:`nodestring` / code:`line`: returns only nodestring data types
        * :code:`[id]`: returns only data types for the given ID.

        Parameters
        ----------
        filter_by : str, optional
            The string to filter the data types by.

        Returns
        -------
        list[str]
            The available data types.

        Examples
        --------
        >>> bndry.data_types()
        ['water level']
        """
        return super().data_types(filter_by)

    def maximum(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a DataFrame containing the maximum values for the given data types. The returned DataFrame
        will include time of maximum results as well.

        It's possible to pass in a well known shorthand for the data type e.g. :code:`h` for :code:`water level`.

        The returned DataFrame will have an index column corresponding to the location IDs, and the columns
        will be in the format :code:`obj/data_type/[max|tmax]`,
        e.g. :code:`point/water level/max`, :code:`point/water level/tmax`

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the maximum values for. :code:`None` will return all locations for the
            given data_types.
        data_types : str | list[str]
            The data types to extract the maximum values for. :code:`None` will return all data types for the
            given locations.
        time_fmt : str, optional
            The format for the time of max result. Options are :code:`relative` or :code:`absolute`

        Returns
        -------
        pd.DataFrame
            The maximum, and time of maximum values

        Examples
        --------
        Extracting the maximum flow for a given channel:

        >>> bndry.maximum('Ocean_pt_0', 'level')
                    point/level/max  point/level/tmax
        Ocean_pt_0         1.191989         289784.25
        """
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        filter_by = '/'.join(locations + data_types)
        ctx = self._filter(filter_by)
        if ctx.empty:
            return pd.DataFrame()

        df = self._maximum_extractor(ctx[ctx['geometry'] == 'point'].data_type.unique(), data_types,
                                     self._maximum_data, ctx, time_fmt, self.reference_time)
        df.columns = [f'point/{x}' for x in df.columns]

        return df

    def time_series(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                    time_fmt: str = 'relative', *args, **kwargs) -> pd.DataFrame:
        """Returns a time-series DataFrame for the given location(s) and data type(s).

        It's possible to pass in a well known shorthand for the data type e.g. :code:`h` for :code:`water level`.

        The returned column names will be in the format :code:`obj/data_type/location`
        e.g. :code:`point/level/Ocean_pt_0`. The :code:`data_type` name in the column heading will be identical to the
        data type  name passed into the function e.g. if :code:`h` is used instead of :code:`water level`, then the
        return will be :code:`point/h/Ocean_pt_0`.

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the time series data for. If :code:`None` is passed in, all locations will be
            returned for the given data_types.
        data_types : str | list[str]
            The data type to extract the time series data for. If :code:`None` is passed in, all data types
            will be returned for the given locations.
        time_fmt : str, optional
            The format for the time column. Options are :code:`relative` or :code:`absolute`.

        Returns
        -------
        pd.DataFrame
            The time series data.

        Examples
        --------
        Extracting flow for a given channel.

        >>> bndry = FVBCTide('/path/to/fv_bc_tide.nc', '/path/to/fv_bc_tide.shp')
        >>> bndry.time_series('ds1', 'q')
        time       point/level/Ocean_pt_0
        289258.00               -0.228474
        289258.25               -0.196456
        289258.50               -0.160042
        289258.75               -0.119967
        289259.00               -0.076996
        ...                           ...
        290025.00                0.073840
        290025.25                0.018794
        290025.50               -0.034604
        290025.75               -0.085668
        290026.00               -0.133717
        """
        ctx, locations, data_types = self._time_series_filter_by(locations, data_types)
        if ctx.empty:
            return pd.DataFrame()

        share_idx = ctx[['start', 'end', 'dt']].drop_duplicates().shape[0] < 2
        df = self._time_series_extractor(ctx[ctx['geometry'] == 'point'].data_type.unique(), data_types,
                                         self._time_series_data, ctx, time_fmt, share_idx, self.reference_time)
        df.columns = [f'point/{x}' for x in df.columns]

        return df

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike, *args, **kwargs) -> pd.DataFrame:
        """Returns a DataFrame containing the long plot data for the given location(s) and data type(s).

        Multiple locations can be passed in as a list. To be consistent with section data extraction, the data is
        stored vertically with the :code:`branch_id` and :code:`node_string` columns denoting the locations
        of the different plotted nodestrings.

        The returned DataFrame will have the following columns:

        * :code:`branch_id`: The ID of the branch (nodestring) that the data is from (starts at zero and increments).
        * :code:`node_string`: The name of the nodestring.
        * :code:`offset`: The offset along the nodestring.
        * :code:`data_type`: The data type (e.g. water level).

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the long plot data for (i.e. the nodestring names).
        data_types : str | list[str]
            The data types to extract the long plot data for. Only water level is supported.
        time : TimeLike
            The time to extract the long plot data for.

        Returns
        -------
        pd.DataFrame
            The long plot data.

        Examples
        --------

        >>> from datetime import datetime
        >>> bndry = FVBCTide('/path/to/fv_bc_tide.nc', '/path/to/fv_bc_tide.shp')
        >>> bndry.section('Ocean', 'water level', datetime(2023, 1, 1, 12, 0, 0))
            branch_id node_string        offset  water level
        0           0       Ocean      0.000000    -0.136288
        1           0       Ocean   2665.236328    -0.136288
        2           0       Ocean   5330.472656    -0.136658
        3           0       Ocean   7995.708984    -0.137053
        4           0       Ocean  10660.945312    -0.137360
        5           0       Ocean  13326.181641    -0.137726
        6           0       Ocean  15991.417969    -0.138077
        7           0       Ocean  18656.654297    -0.138393
        8           0       Ocean  21321.890625    -0.138562
        9           0       Ocean  23987.126953    -0.138638
        10          0       Ocean  26652.363281    -0.138558
        11          0       Ocean  29317.599609    -0.138558
        """
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        locations, data_types = self._figure_out_loc_and_data_types_lp(locations, data_types, 'section')

        df = pd.DataFrame()
        for i, loc in enumerate(locations):
            for dtype in data_types:  # assume only water level is possible
                a = self.provider.get_section(loc, time, False)
                df1 = pd.DataFrame(a, columns=['offset', dtype])
                df1['branch_id'] = i
                df1['node_string'] = loc
                df1 = df1[['branch_id', 'node_string', 'offset', dtype]]
                df = df1 if df.empty else pd.concat([df, df1], axis=0)

        return df

    def curtain(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``FVBCTide`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support curtain plotting.')

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike, **kwargs) -> pd.DataFrame:
        """Not supported for ``FVBCTide`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support vertical profile plotting.')

    def _load(self):
        if self._loaded:
            return
        self.provider = FVBCTideProvider(self.nc_fpath, self.node_string_gis_fpath, self.use_local_time)
        self.name = self.provider.name
        self.name_tz = self.provider.display_name
        self.reference_time = self.provider.reference_time
        self.gis_layer_l_fpath = self.node_string_gis_fpath
        self._load_time_series()
        self._load_maximums()
        self._load_obj_df()
        self.node_count = int(self.objs['geometry'].value_counts().get('point', 0))
        self.node_string_count = int(self.objs['geometry'].value_counts().get('line', 0))
        self._loaded = True

    def _overview_dataframe(self) -> pd.DataFrame:
        return self.objs.copy()

    def _load_time_series(self):
        df = pd.DataFrame()
        for label in self.provider.get_labels():
            df1 = pd.DataFrame(
                self.provider.get_time_series_data_raw(label),
                index=self.provider.get_timesteps('relative'),
                columns=[f'{label}_pt_{x}' for x in range(self.provider.number_of_points(label))]
            )
            df = df1 if df.empty else pd.concat([df, df1], axis=1)

        if not df.empty:
            df.index.name = 'time'

        self._time_series_data['water level'] = df

    def _load_maximums(self) -> None:
        """Load the result maximums."""
        # info class does not have actual maximums, so need to be post-processed.
        for data_type, results in self._time_series_data.items():
            for res in results:
                max_ = res.max()
                tmax = res.idxmax()
                self._maximum_data[data_type] = pd.DataFrame({'max': max_, 'tmax': tmax})

    def _load_obj_df(self):
        info = {'id': [], 'data_type': [], 'geometry': [], 'start': [], 'end': [], 'dt': []}
        dt, start, end = np.nan, np.nan, np.nan
        for dtype, vals in self._time_series_data.items():
            for df1 in vals:
                dt = np.round((df1.index[1] - df1.index[0]) * 3600., decimals=2)
                start = df1.index[0]
                end = df1.index[-1]
                for col in df1.columns:
                    info['id'].append(col)
                    info['data_type'].append(dtype)
                    info['geometry'].append('point')
                    info['start'].append(start)
                    info['end'].append(end)
                    info['dt'].append(dt)

        for label in self.provider.get_labels():
            info['id'].append(label)
            info['data_type'].append('water level')
            info['geometry'].append('line')
            info['start'].append(start)
            info['end'].append(end)
            info['dt'].append(dt)

        self.objs = pd.DataFrame(info)
