from pathlib import Path
import re
from typing import Union

import numpy as np
import pandas as pd
try:
    from netCDF4 import Dataset
    has_netcdf4 = True
except ImportError:
    has_netcdf4 = False

from .gpkg_1d import GPKG1D
from .gpkg_2d import GPKG2D
from .gpkg_rl import GPKGRL
from .helpers.nc_ts import NCTS
from .info import INFO
from .itime_series_2d import ITimeSeries2D
from .helpers.tpc_reader import TPCReader
from .._pytuflow_types import PathLike, AppendDict, TimeLike
from ..util import pytuflow_logging
from .._outputs.helpers.nc_dataset_wrapper import DatasetWrapper


logger = pytuflow_logging.get_logger()


class TPC(INFO, ITimeSeries2D):
    """Class to handle the standard TUFLOW Time Series result file (:code:`.tpc`).

    Supports:

    * 1D, 2D, and  Reporting Location (RL) results.
    * Supports varying time indexes between results e.g. 1D results can have a different output interval than 2D
      results. It also supports varying time indexes within a single domain e.g. :code:`2d_po` results where one
      location has a different temporal resolution than another location. This is not something that TUFLOW Classic/HPC
      supports, however it is something that can occur in TUFLOW FV.
    * Supports duplicate IDs across domains e.g. a 1D node called :code:`test`, a PO point called :code:`test`,
      and an RL point called :code:`test` - these can all have the same ID with a :code:`Water Level` result attached.

    The ``TPC`` class will only load basic properties on initialisation. These are typically properties
    that are easy to obtain from the file without having to load any of the time-series results. Once a method
    requiring more detailed information is called, the full results will be loaded. This makes the ``TPC`` class
    very cheap to initialise.

    Parameters
    ----------
    fpath : PathLike
        The path to the output (.tpc) file.

    Raises
    ------
    ResultTypeError
        Raises :class:`pytuflow.results.ResultTypeError` if the file does not look like a ``TPC`` file.

    Examples
    --------
    Loading a .tpc file:

    >>> from pytuflow import TPC
    >>> res = TPC('path/to/file.tpc')

    Querying all the available :code:`2d_po` data types:

    >>> res.data_types('po')
    ['flow into region', 'volume', 'average water level', 'water level', 'velocity']

    Querying all the available 1D channel IDs

    >>> res.ids('channel')
    ['FC01.1_R', 'FC01.2_R', 'FC04.1_C']

    Extracting the time-series information for a given channel and data type:

    >>> res.time_series('FC01.1_R', 'flow')
    time      channel/flow/FC01.1_R
    0.000000                  0.000
    0.016667                  0.000
    0.033333                  0.000
    0.050000                  0.000
    0.066667                  0.000
    ...                         ...
    2.933333                  3.806
    2.950000                  3.600
    2.966667                  3.400
    2.983334                  3.214
    3.000000                  3.038

    For more examples, see the documentation for the individual methods.
    """

    DOMAIN_TYPES = {'1d': ['1d'], '2d': ['2d', 'po'], 'rl': ['rl', '0d']}
    GEOMETRY_TYPES = {'point': ['point'], 'line': ['line'], 'polygon': ['polygon', 'region']}
    ATTRIBUTE_TYPES = {}
    ID_COLUMNS = ['id']

    def __init__(self, fpath: PathLike):
        # private
        self._time_series_data_2d = AppendDict()
        self._time_series_data_rl = AppendDict()
        self._maximum_data_2d = AppendDict()
        self._maximum_data_rl = AppendDict()
        self._nc_file = None
        self._ncid = None
        self._gis_layers_initialised = False
        self._gpkgswmm = None
        self._gpkg1d = None
        self._gpkg2d = None
        self._gpkgrl = None

        # PO counts are only known after loading the time-series
        self._po_point_count = 0
        self._po_line_count = 0
        self._po_poly_count = 0

        #: str: format of the results - options are 'CSV' or 'NC'. If both are specified, the NC will be preferred.
        self.format = 'CSV'

        super().__init__(fpath)

    @property
    def po_point_count(self) -> int:
        if self.format != 'GPKG':
            self._load()
        return self._po_point_count

    @po_point_count.setter
    def po_point_count(self, count: int):
        self._po_point_count = count

    @property
    def po_line_count(self) -> int:
        if self.format != 'GPKG':
            self._load()
        return self._po_line_count

    @po_line_count.setter
    def po_line_count(self, count: int):
        self._po_line_count = count

    @property
    def po_poly_count(self) -> int:
        if self.format != 'GPKG':
            self._load()
        return self._po_poly_count

    @po_poly_count.setter
    def po_poly_count(self, count: int):
        self._po_poly_count = count

    @staticmethod
    def _looks_like_this(fpath: PathLike) -> bool:
        # docstring inherited
        fpath = Path(fpath)
        if fpath.suffix.upper() != '.TPC':
            return False
        # noinspection PyBroadException
        try:
            with fpath.open() as f:
                line = f.readline()
                if not line.startswith('Format Version == 2'):
                    return False
        except Exception:
            return False
        return True

    @staticmethod
    def _looks_empty(fpath: PathLike) -> bool:
        # docstring inherited
        target_line_count = 7  # fairly arbitrary
        # noinspection PyBroadException
        try:
            tpc_reader = TPCReader(fpath)
            gpkgs = list(tpc_reader.iter_properties('GPKG Time Series'))
            if gpkgs:
                return False
            if tpc_reader.property_count() < target_line_count:
                return True
            node_count = tpc_reader.get_property('Number 1D Nodes')
            channel_count = tpc_reader.get_property('Number 1D Channels')
            rlp_count = tpc_reader.get_property('Number Reporting Location Points')
            rll_count = tpc_reader.get_property('Number Reporting Location Lines')
            rlr_count = tpc_reader.get_property('Number Reporting Location Regions')
            po_count = 0
            for _, _ in tpc_reader.iter_properties(r'^2D', regex=True):
                po_count += 1
            if node_count + channel_count + rlp_count + rll_count + rlr_count + po_count == 0:
                return True
            return False
        except Exception:
            return True

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns all the available times for the output.

        The ``filter_by`` is an optional input that can be used to filter the return further. Valid filters
        for the ``TPC`` results are:

        Domain filters:

        * ``1d``: 1D result times - nodes and channels will always have the same times
        * ``node`` - times for node types (note, there will be no difference between nodes and channels)
        * ``channel`` - times for channel types (note, there will be no difference between nodes and channels)
        * ``2d (or ``po``): 2D result times - 2D results can have varying times between result types and locations. This
          will return all unique times
        * ``rl`` (or ``0d``): Reporting locations result times. RL results will have the same times for all RL types

        Data type filters:

        * ``[data type]``: The data type to filter the times by. This will return all times for the given data type.

        Location filters:

        * ``[location]``: The location to filter the times by. This will return all times for the given location.

        Combine filters:

        * ``[filter1]/[filter2]/...``: (use ``/`` to delim).

        Parameters
        ----------
        filter_by : str, optional
            The string to filter the times by.
        fmt : str, optional
            The format for the times. Options are 'relative' or 'absolute'.

        Returns
        -------
        list[TimeLike]
            The available times in the requested format.

        Examples
        --------
        >>> res = TPC('/path/to/result.tpc')
        >>> res.times()
        [0.0, 0.016666666666666666, ..., 3.0]
        >>> res.times(fmt='absolute')
        [Timestamp('2021-01-01 00:00:00'), Timestamp('2021-01-01 00:01:00'), ..., Timestamp('2021-01-01 03:00:00')]
        """
        return super().times(filter_by, fmt)

    def ids(self, filter_by: str = None) -> list[str]:
        """Returns all the available IDs for the output.

        The ``filter_by`` is an optional input that can be used to filter the return further. Valid
        filters for the ``TPC`` class are:

        Domain filters:

        * :code:`1d`
        * :code:`2d` (or :code:`po`)
        * :code:`rl` (or :code:`0d`)

        Geometry filters:

        * :code:`node`
        * :code:`channel`
        * :code:`point` - (for 2d and rl domains only - use :code:`node` for 1d domain)
        * :code:`line` - (for 2d and rl domains only - use :code:`channel` for 1d domain)
        * :code:`polygon` (or :code:`region`)

        Data type filters:

        * :code:`[data_type]`: The data_type to filter the ids by.

        Combine filters:

        * ``[filter1]/[filter2]/...``: (use ``/`` to delim).

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
        Get the IDs for all :code:`po` results:

        >>> res = TPC('/path/to/result.tpc')
        >>> res.ids('po')
        ['po_poly', 'po_point', 'po_line']

        Get the IDs for all :code:`rl line` results:

        >>> res.ids('rl/line')
        ['rl_line']
        """
        return super().ids(filter_by)

    def data_types(self, filter_by: str = None) -> list[str]:
        """Returns all the available data types (result types) for the output given the filter.

        The ``filter_by`` is an optional input that can be used to filter the return further. Available
        filters for the ``TPC`` are:

        Domain filters:

        * :code:`1d`
        * :code:`2d` (or :code:`po`)
        * :code:`rl` (or :code:`0d`)

        Geometry filters:

        * :code:`node`
        * :code:`channel`
        * :code:`point` - (for 2d and rl domains only - use :code:`node` for 1d domain)
        * :code:`line` - (for 2d and rl domains only - use :code:`channel` for 1d domain)
        * :code:`polygon` (or :code:`region`)

        Location filters:

        * :code:`[location]`: The location to filter the data_types by.

        Combine filters:

        * ``[filter1]/[filter2]/...``: (use ``/`` to delim).

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
        Get the available data types for 1D :code:`channel` results:

        >>> res = TPC('/path/to/result.tpc')
        >>> res.data_types('channel')
        ['flow', 'velocity', 'channel entry losses', 'channel additional losses', 'channel exit losses', 'channel flow regime']

        Get the available data types for 2D :code:`po` and specicially for :code:`po line`.

        >>> res.data_types('po/line')
        ['depth', 'flow area', 'flow integral', 'flow']

        Get the available data types for 2D :code:`po` and RL (:code:`rl`) :code:`region` results.

        >>> res.data_types('po/rl/region')
        ['flow into region', 'flow out of region', 'volume', 'average water level', 'max water level']

        The above could also be accomplished with just :code:`region` (or :code:`polygon`) since it's only
        applicable for :code:`po` and :code:`rl` domains.
        """
        return super().data_types(filter_by)

    def maximum(self, locations: str | list[str] | None, data_types: str | list[str] | None,
                time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a dataframe containing the maximum values for the given data types. The returned dataframe
        will include time of maximum results as well.

        It's possible to pass in a well known shorthand for the data type e.g. 'q' for flow.

        The location can be an ID or filter string, e.g. ``channel`` to extract the maximum values
        for all channels. An ID can be used alongside a filter string since there can be duplicate IDs across
        domains e.g. 'test/channel' - where 'test' is the name and 'channel' is an additional filter. Note, the order
        does not matter, but it doesn't work very well if your ID has a '/' or has the same name as a filter string
        (e.g. calling a po line 'line').
        For the ``TPC`` result class, the following filters are available:

        Domain filters:

        * :code:`1d`
        * :code:`2d` (or :code:`po`)
        * :code:`rl` (or :code:`0d`)

        Geometry filters:

        * :code:`node`
        * :code:`channel`
        * :code:`point` - (for 2d and rl domains only - use :code:`node` for 1d domain)
        * :code:`line` - (for 2d and rl domains only - use :code:`channel` for 1d domain)
        * :code:`polygon` (or :code:`region`)

        Combine filters:

        * ``[filter1]/[filter2]/...``: (use ``/`` to delim).

        The returned DataFrame will have an index column corresponding to the location ids, and the columns
        will be in the format :code:`obj/data_type/[max|tmax]`,
        e.g. :code:`channel/flow/max`, :code:`channel/flow/tmax`.

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the maximum values for.
        data_types : str | list[str]
            The data types to extract the maximum values for.
        time_fmt : str, optional
            The format for the time of max result. Options are :code:`relative` or :code:`absolute`

        Returns
        -------
        pd.DataFrame
            The maximum, and time of maximum values

        Examples
        --------
        Extracting the maximum flow for a given channel:

        >>> res = TPC('/path/to/result.tpc')
        >>> res.maximum('ds1', 'flow')
             channel/flow/max  channel/flow/tmax
        ds1            59.423           1.383333

        Extracting all the maximum results for a given channel:

        >>> res.maximum(['ds1'], None)
             channel/Flow/max  ...  channel/Velocity/tmax
        ds1            59.423  ...               0.716667

        Extracting the maximum flow for all channels:

        >>> res.maximum(None, 'flow')
                 channel/flow/max  channel/flow/tmax
        ds1                 59.423           1.383333
        ds2                 88.177           1.400000
        ...                  ...              ...
        FC04.1_C             9.530           1.316667
        FC_weir1            67.995           0.966667
        """
        ctx, locations, data_types = self._time_series_filter_by(locations, data_types)
        if ctx.empty:
            return pd.DataFrame()

        # 1D
        df = super().maximum(locations, data_types, time_fmt)

        # 2D
        df = self._append_maximum_2d('2d', self._maximum_data_2d, df, ctx, data_types,
                                     time_fmt, self.reference_time)

        # rl
        df = self._append_maximum_2d('rl', self._maximum_data_rl, df, ctx, data_types,
                                     time_fmt, self.reference_time)

        return df

    def time_series(self, locations: str | list[str] | None, data_types: str | list[str] | None,
                    time_fmt: str = 'relative', *args, **kwargs) -> pd.DataFrame:
        """Returns a time series dataframe for the given location(s) and data type(s).

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can be an ID or filter string, e.g. :code:`channel` to extract the maximum values
        for all channels. An ID can be used alongside a filter string since there can be duplicate IDs across
        domains e.g. :code:`test/channel` - where :code:`test` is the name and :code:`channel` is an additional filter.
        Note, the order does not matter, but it doesn't work very well if your ID has a '/' or has the same name as a
        filter string (e.g. calling a po line 'line').

        The following filters are available for the ``TPC`` class:

        Domain filters:

        * ``1d``
        * ``2d`` (or :code:`po`)
        * ``rl`` (or :code:`0d`)

        Geometry filters:

        * ``node``
        * ``channel``
        * ``point`` - (for 2d and rl domains only - use :code:`node` for 1d domain)
        * ``line`` - (for 2d and rl domains only - use :code:`channel` for 1d domain)
        * ``polygon`` (or :code:`region`)

        Combine filters:

        * ``[filter1]/[filter2]/...``: (use ``/`` to delim).

        The returned column names will be in the format :code:`obj/data_type/location`
        e.g. :code:`channel/flow/FC01.1_R`. The data_type name in the column heading will be identical to the data type
        name passed into the function e.g. if :code:`h` is used instead of :code:`water level`,
        then the return will be :code:`node/h/FC01.1_R.1`.

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the time series data for. If None is passed in, all locations will be returned for
            the given data_types.
        data_types : str | list[str]
            The data type to extract the time series data for. If None is passed in, all data types will be returned
            for the given locations.
        time_fmt : str, optional
            The format for the time column. Options are 'relative' or 'absolute'.

        Returns
        -------
        pd.DataFrame
            The time series data.

        Examples
        --------
        Extracting flow for a given channel.

        >>> res = TPC('path/to/file.tpc')
        >>> res.time_series('ds1', 'q')
        Time (h)   channel/q/ds1
        0.000000           0.000
        0.016667           0.000
        ...                  ...
        2.983334           8.670
        3.000000           8.391

        Extracting all data types for a given location

        >>> res.time_series('ds1', None)
        Time (h)  channel/Flow/ds1  channel/Velocity/ds1
        0.000000             0.000                 0.000
        0.016667             0.000                 0.000
        ...                    ...                   ...
        2.983334             8.670                 1.348
        3.000000             8.391                 1.333

        Extracting all :code:`flow` results

        >>> res.time_series(None, 'flow')
        Time (h)  channel/flow/ds1  ...  channel/flow/FC_weir1
        0.000000             0.000  ...                    0.0
        0.016667             0.000  ...                    0.0
        ...                    ...  ...                    ...
        2.983334             8.670  ...                    0.0
        3.000000             8.391  ...                    0.0
        """
        ctx, locations, data_types = self._time_series_filter_by(locations, data_types)
        if ctx.empty:
            return pd.DataFrame()

        share_idx = ctx[['start', 'end', 'dt']].drop_duplicates().shape[0] < 2

        # 1D
        df = super().time_series(locations, data_types, time_fmt, *args, **kwargs)

        # 2d/po
        df = self._append_time_series_2d('2d', self._time_series_data_2d, df, ctx, data_types, time_fmt,
                                         share_idx, self.reference_time)

        # rl
        df = self._append_time_series_2d('rl', self._time_series_data_rl, df, ctx, data_types, time_fmt,
                                         share_idx, self.reference_time)

        return df

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike, *args, **kwargs) -> pd.DataFrame:
        if self._gpkgswmm is not None:
            try:
                return self._gpkgswmm.section(locations, data_types, time, *args, **kwargs)
            except NameError:
                pass
        return super().section(locations, data_types, time, *args, **kwargs)

    def curtain(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``TPC`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support curtain plotting.')

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike, **kwargs) -> pd.DataFrame:
        """Not supported for ``TPC`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support vertical profile plotting.')

    def _initial_load(self) -> None:
        """Load the TPC file into memory. Called by the __init__ method."""
        self.format = self._tpc_reader.get_property('Time Series Output Format', 'CSV')
        if 'CSV' in self.format:
            self.format = 'CSV'  # it is possible to have both CSV and NC and CSV is a more complete format

        if self.format == 'GPKG':
            self.name = self._tpc_reader.get_property('Simulation ID')
            self.units = 'si' if self._tpc_reader.get_property('Units') == 'METRIC' else 'us customary'
            self._initial_gpkg_load()
            return

        self.reference_time = self._tpc_reader.get_property('Reference Time', self.reference_time)

        # rl counts - up here since it's easy to get and useful when loading time series and maximum data
        self.rl_point_count = self._tpc_reader.get_property('Number Reporting Location Points', 0)
        self.rl_line_count = self._tpc_reader.get_property('Number Reporting Location Lines', 0)
        self.rl_poly_count = self._tpc_reader.get_property('Number Reporting Location Regions', 0)

        # gis layers
        self._gis_layer_p_fpath = self._expand_property_path('GIS Plot Layer Points')
        self._gis_layer_l_fpath = self._expand_property_path('GIS Plot Layer Lines')
        self._gis_layer_r_fpath = self._expand_property_path('GIS Plot Layer Regions')

        # 1d
        super()._initial_load()

    def _load(self):
        if self._loaded:
            return

        self._nc_file = self._expand_property_path('NetCDF Time Series')  # returns None if there is no property
        if self.format == 'NC':
            if not has_netcdf4:
                raise ImportError('NetCDF4 is required to read NetCDF files.')

        with DatasetWrapper(self._nc_file) as self._ncid:
            super()._load()

            # po
            self.po_objs = self._load_po_info()
            if not self.po_objs.empty:
                self._po_point_count = self.po_objs[self.po_objs['geometry'] == 'point']['id'].unique().size
                self._po_line_count = self.po_objs[self.po_objs['geometry'] == 'line']['id'].unique().size
                self._po_poly_count = self.po_objs[self.po_objs['geometry'] == 'polygon']['id'].unique().size

            # rl
            self.rl_objs = self._load_rl_info()

        self._ncid = None
        self._loaded = True

    def _overview_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(columns=self.oned_objs.columns)
        for domain, df1 in {'1d': self.oned_objs, '2d': self.po_objs, 'rl': self.rl_objs}.items():
            if not df1.empty:
                df2 = df1.copy()
                df2['domain'] = domain
                df = pd.concat([df, df2], axis=0, ignore_index=True) if not df.empty else df2
        return df

    def _filter(self, filter_by: str, filtered_something: bool = False, df: pd.DataFrame = None,
                ignore_excess_filters: bool = False) -> pd.DataFrame:
        # docstring inherited
        filter_by = self._replace_1d_aliases(filter_by)
        return super()._filter(filter_by, ignore_excess_filters=True)

    def _info_name_correction(self, name: str) -> str:
        # override this as it isn't needed for TPC
        return name

    def _load_time_series(self) -> None:
        """Load time-series data into memory."""
        if self.format == 'GPKG':  # special approach
            self._load_time_series_gpkg()
            return

        # load node time series
        for prop, _ in self._tpc_reader.iter_properties(start_after='1D Node Maximums', end_before='1D Channel Maximums'):
            data_type = prop.replace('1D', '').strip()
            df = self._load_time_series_from_property(prop, data_type, '1D')
            if df is not None:
                data_type = self._get_standard_data_type_name(data_type)
                self._time_series_data[data_type] = df
                if df.columns.isin(self._node_info.index).all():
                    self._nd_res_types.append(data_type)

        # load channel time series
        for prop, _ in self._tpc_reader.iter_properties(start_after='1D Channel Maximums', end_before='Number Reporting Location Points'):
            data_type = prop.replace('1D', '').strip()
            df = self._load_time_series_from_property(prop, data_type, '1D')
            if df is not None:
                if 'Channel Losses' in data_type:
                    for dtype in ['Channel Entry Losses', 'Channel Additional Losses', 'Channel Exit Losses']:
                        df1 = self._post_process_channel_losses(df, dtype)
                        if df1 is not None:
                            dtype = self._get_standard_data_type_name(dtype)
                            self._time_series_data[dtype] = df1
                    df1 = self._post_process_channel_losses_2(df)
                    if df1 is not None:
                        dtype = self._get_standard_data_type_name('Channel Losses')
                        self._time_series_data[dtype] = df1
                else:
                    data_type = self._get_standard_data_type_name(data_type)
                    self._time_series_data[data_type] = df

        # reporting locations
        if self.rl_point_count:
            df = self._load_time_series_from_property('Reporting Location Points Water Levels', 'Water Levels', 'RL')
            if df is not None:
                self._time_series_data_rl['water level'] = df
        if self.rl_line_count:
            df = self._load_time_series_from_property('Reporting Location Lines Flows', 'Flows', 'RL')
            if df is not None:
                self._time_series_data_rl['flow'] = df
        if self.rl_poly_count:
            df = self._load_time_series_from_property('Reporting Location Regions Volumes', 'Volumes', 'RL')
            if df is not None:
                self._time_series_data_rl['volume'] = df

        # 2d data
        for prop, value in self._tpc_reader.iter_properties('^2D', regex=True):
            data_type = re.sub(r'^2D (Point|Line|Region)', '', prop).split('[', 1)[0].strip()
            df = self._load_time_series_from_property(prop, data_type, '2D', value)
            if df is not None:
                if not prop.startswith('2D Region Max Water Level'):
                    data_type = self._get_standard_data_type_name(data_type)
                self._time_series_data_2d[data_type.lower()] = df

    def _load_time_series_from_property(self, prop: str, data_type: str, domain: str, value: str = None) -> None | pd.DataFrame:
        p = self._expand_property_path(prop, value=value)
        if p or self.format == 'NC':
            try:
                # noinspection PyUnreachableCode
                if self.format == 'CSV':
                    return self._load_time_series_csv(p)
                elif self.format == 'NC':
                    return self._load_time_series_nc(data_type, domain)
                else:  # GPKG
                    self._load_time_series_gpkg()
                    return None
            except Exception as e:
                logger.warning(f'TPC._load_time_series_from_property(): Error loading from {prop}: {e}')
        return None

    def _load_time_series_nc(self, dtype: str, domain: str) -> pd.DataFrame:
        df = NCTS.extract_result(self._ncid, dtype, domain)
        if df is None or df.empty:
            logger.warning(f'TPC._load_time_series_nc(): No data found in NetCDF file for {dtype} for domain {domain}.')
        return df

    def _initial_gpkg_load(self):
        reference_time_set = False
        for prop, value in self._tpc_reader.iter_properties('GPKG Time Series'):
            if str(value).lower().endswith('_1d.gpkg'):
                self._gpkg1d = GPKG1D(self._expand_property_path(prop, value=value))
                self.node_count += self._gpkg1d.node_count
                self.channel_count += self._gpkg1d.channel_count
                self.reference_time = self._gpkg1d.reference_time if not reference_time_set else self.reference_time
            elif str(value).lower().endswith('_swmm_ts.gpkg'):
                self._gpkgswmm = GPKG1D(self._expand_property_path(prop, value=value))
                self.node_count += self._gpkgswmm.node_count
                self.channel_count += self._gpkgswmm.channel_count
                self.reference_time = self._gpkgswmm.reference_time if not reference_time_set else self.reference_time
            elif str(value).lower().endswith('_2d.gpkg'):
                self._gpkg2d = GPKG2D(self._expand_property_path(prop, value=value))
                self.po_point_count += self._gpkg2d.po_point_count
                self.po_line_count += self._gpkg2d.po_line_count
                self.po_poly_count += self._gpkg2d.po_poly_count
                self.reference_time = self._gpkg2d.reference_time if not reference_time_set else self.reference_time
            elif str(value).lower().endswith('_rl.gpkg'):
                self._gpkgrl = GPKGRL(self._expand_property_path(prop, value=value))
                self.rl_point_count += self._gpkgrl.rl_point_count
                self.rl_line_count += self._gpkgrl.rl_line_count
                self.rl_poly_count += self._gpkgrl.rl_poly_count
                self.reference_time = self._gpkgrl.reference_time if not reference_time_set else self.reference_time

    # noinspection PyProtectedMember
    def _load_time_series_gpkg(self):
        if self._gpkg1d is not None:
            self._gpkg1d._load()
            self._time_series_data = self._gpkg1d._time_series_data
            self._nd_res_types = self._gpkg1d._nd_res_types

        if self._gpkgswmm is not None:
            self._gpkgswmm._load()
            self._time_series_data.update(self._gpkgswmm._time_series_data)
            self._nd_res_types.extend(self._gpkgswmm._nd_res_types)

        if self._gpkg2d is not None:
            self._gpkg2d._load()
            self._time_series_data_2d = self._gpkg2d._time_series_data_2d

        if self._gpkgrl is not None:
            self._gpkgrl._load()
            self._time_series_data_rl = self._gpkgrl._time_series_data_rl

    @staticmethod
    def _post_process_channel_losses(df: pd.DataFrame, dtype: str) -> None | pd.DataFrame:
        d = {'Channel Entry Losses': 'Entry', 'Channel Additional Losses': 'Additional', 'Channel Exit Losses': 'Exit'}
        cols = df.columns.str.contains(d[dtype])
        if cols.any():
            df1 = df.loc[:,cols].copy()
            df1.columns = [' '.join(x.split(' ')[2:]) for x in df1.columns]
            return df1
        return None

    @staticmethod
    def _post_process_channel_losses_2(df: pd.DataFrame) -> None | pd.DataFrame:
        cols = df.columns.str.startswith('LC')
        if cols.any():
            df1 = df.loc[:,cols].copy()
            df1.columns = [' '.join(x.split(' ')[1:]) for x in df1.columns]
            return df1
        return None

    def _load_maximums(self):
        # override
        # node maximums
        df = self._load_maximum_from_property('1D Node Maximums')
        if df is not None:
            for col in df.columns[::2]:
                data_type, df1 = self._split_maximum_columns(df, col)
                data_type = self._get_standard_data_type_name(data_type)
                self._maximum_data[data_type] = df1

        # channel maximums
        df = self._load_maximum_from_property('1D Channel Maximums')
        if df is not None:
            for col in df.columns[::2]:
                data_type, df1 = self._split_maximum_columns(df, col)
                data_type = self._get_standard_data_type_name(data_type)
                self._maximum_data[data_type] = df1

        # rl maximums
        df = self._load_maximum_from_property('Reporting Location Points Maximums')
        if df is not None:
            data_type, df1 = self._split_maximum_columns(df, 'Hmax')
            data_type = self._get_standard_data_type_name(data_type)
            self._maximum_data_rl[data_type] = df1
        df = self._load_maximum_from_property('Reporting Location Lines Maximums')
        if df is not None:
            data_type, df1 = self._split_maximum_columns(df, 'Qmax')
            data_type = self._get_standard_data_type_name(data_type)
            self._maximum_data_rl[data_type] = df1
        df = self._load_maximum_from_property('Reporting Location Regions Maximums')
        if df is not None:
            data_type, df1 = self._split_maximum_columns(df, 'Vol max')
            data_type = self._get_standard_data_type_name(data_type)
            self._maximum_data_rl[data_type] = df1

        # 2d results do not have maximums, so need to be post-processed.
        for data_type, results in self._time_series_data_2d.items():
            for res in results:
                max_ = res.max()
                tmax = res.idxmax()
                self._maximum_data_2d[data_type] = pd.DataFrame({'max': max_, 'tmax': tmax})

        if self._gpkgswmm is not None:
            # noinspection PyProtectedMember
            self._maximum_data.update(self._gpkgswmm._maximum_data)

    def _load_maximum_from_property(self, prop: str) -> None | pd.DataFrame:
        p = self._expand_property_path(prop)
        if p:
            try:
                with p.open() as f:
                    index_col = f.readline().split(',')[1].strip('"')
                df = pd.read_csv(p, index_col=index_col, na_values='**********')
                df.index.name = 'id'
                df.drop(df.columns[0], axis=1, inplace=True)
                return df
            except Exception as e:
                logger.warning(f'TPC._load_maximum_from_property(): Error loading maximums {prop}: {e}')
        return None

    def _split_maximum_columns(self, df: pd.DataFrame, col_name: str) -> tuple[str, pd.DataFrame]:
        name = col_name.replace('max', '').strip()
        data_type = self._get_standard_data_type_name(name)
        if data_type != 'energy':
            df1 = df.loc[:, [col_name, f'Time {col_name}']].copy()
        else:
            df1 = df.loc[:, [col_name]].copy()
            df1[[f'Time {col_name}']] = np.nan
        df1.columns = ['max', 'tmax']
        return data_type, df1

    def _load_po_info(self) -> pd.DataFrame:
        d = {'P': 'point', 'L': 'line', 'R': 'polygon'}
        plot_objs = pd.DataFrame()
        # noinspection DuplicatedCode
        po_info = {'id': [], 'data_type': [], 'geometry': [], 'start': [], 'end': [], 'dt': []}
        if self.format.lower() == 'gpkg':
            if self._gpkg2d is not None:
                return self._gpkg2d.po_objs
            else:
                return pd.DataFrame(po_info)

        if self._time_series_data_2d:
            plot_objs = self._gis_plot_objects()
            if plot_objs is None or plot_objs.geom.dtype != np.dtype('O'):
                logger.warning('TPC._load_po_info(): Missing or invalid PLOT.csv. Using TPC to guess PO geometry.')
                plot_objs = self._geom_from_tpc()  # derive geometry from tpc rather than the gis/[...]_PLOT.csv

        for dtype, vals in self._time_series_data_2d.items():
            for df1 in vals:
                dt = np.round((df1.index[1] - df1.index[0]) * 3600., decimals=2)
                start = df1.index[0]
                end = df1.index[-1]
                for col in df1.columns:
                    po_info['id'].append(col)
                    po_info['data_type'].append(dtype)
                    po_info['geometry'].append(d[plot_objs.loc[col, 'geom']])
                    po_info['start'].append(start)
                    po_info['end'].append(end)
                    po_info['dt'].append(dt)

        return pd.DataFrame(po_info)

    def _gis_plot_objects(self) -> None | pd.DataFrame:
        prop = self._expand_property_path('GIS Plot Objects')
        if prop:
            try:
                return pd.read_csv(prop, index_col='id', names=['id', 'domain', 'data_types', 'geom'], header=None)
            except Exception as e:
                logger.warning(f'TPC._gis_plot_objects(): Error loading GIS Plot Objects: {e}')
        elif self.format.lower() == 'gpkg':
            pass
        else:
            logger.error('TPC._gis_plot_objects(): Could not find GIS Plot Objects property.')
        return None

    def _geom_from_tpc(self):
        d = AppendDict()
        df = pd.DataFrame(columns=['geom'])
        df.index.name = 'id'
        for prop, value in self._tpc_reader.iter_properties('^2D', regex=True):
            data_type = re.sub(r'^2D (Point|Line|Region)', '', prop).split('[', 1)[0].strip()
            geom = re.findall('(Point|Line|Region)', prop)[0][0]
            dtype = self._get_standard_data_type_name(data_type)
            d[dtype] = geom
            i = len(d[dtype]) - 1
            df1 = self._time_series_data_2d[dtype][i]
            df2 = pd.DataFrame({'geom': geom}, index=df1.columns)
            df = pd.concat([df, df2[~df2.index.isin(df.index)]], axis=0)
            df.update(df2)
        return df

    def _load_rl_info(self) -> pd.DataFrame:
        d = {'water level': 'point', 'flow': 'line', 'volume': 'polygon'}
        # noinspection DuplicatedCode
        rl_info = {'id': [], 'data_type': [], 'geometry': [], 'start': [], 'end': [], 'dt': []}
        if self.format.lower() == 'gpkg':
            if self._gpkgrl is not None:
                return self._gpkgrl.rl_objs
            else:
                return pd.DataFrame(rl_info)

        for dtype, vals in self._time_series_data_rl.items():
            for df1 in vals:
                dt = np.round((df1.index[1] - df1.index[0]) * 3600., decimals=2)
                start = df1.index[0]
                end = df1.index[-1]
                for col in df1.columns:
                    rl_info['id'].append(col)
                    rl_info['data_type'].append(dtype)
                    rl_info['geometry'].append(d[dtype])
                    rl_info['start'].append(start)
                    rl_info['end'].append(end)
                    rl_info['dt'].append(dt)

        return pd.DataFrame(rl_info)
