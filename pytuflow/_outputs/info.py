import re
from datetime import datetime
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from .helpers.tpc_reader import TPCReader
from .itime_series_1d import ITimeSeries1D
from .time_series import TimeSeries
from .._pytuflow_types import PathLike, TimeLike, AppendDict
from ..util._util.logging import get_logger
from ..results import ResultTypeError

logger = get_logger()


class INFO(TimeSeries, ITimeSeries1D):
    """Class for reading TUFLOW info time series results (:code:`.info`). These are text files with a :code:`.info`
    extension (typically found in the 1D output folder and ending with :code:`_1d.info` and not :code:`.2dm.info`)
    that are output by the 2013 TUFLOW release. The format is similar to the TPC format, however
    does not include :code:`2d_po` or Reporting Location (:code:`0d_rl`) results.

    The ``INFO`` class will only load basic properties on initialisation. These are typically properties
    that are easy to obtain from the file without having to load any of the time-series results. Once a method
    requiring more detailed information is called, the full results will be loaded. This makes the ``INFO`` class
    very cheap to initialise.

    Parameters
    ----------
    fpath : PathLike
        The path to the output (.info) file.

    Raises
    ------
    ResultTypeError
        Raises :class:`pytuflow.results.ResultTypeError` if the file does not look like a time series ``INFO`` file.

    Examples
    --------
    Load a :code:`.info` file:

    >>> from pytuflow import INFO
    >>> res = INFO('path/to/file.info')

    Querying all the available data types:

    >>> res.data_types()
    ['water level', 'flow', 'velocity']

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

    def __init__(self, fpath: PathLike):
        super().__init__(fpath)

        #: Path: The path to the source output file.
        self.fpath = Path(fpath)
        #: str: The unit system used in the output file.
        self.units = 'si'

        if not self.fpath.exists():
            raise FileNotFoundError(f'File not found: {self.fpath}')

        # call before tpc_reader is initialised to give a clear error message if it isn't actually a .info time series file
        if not self._looks_like_this(self.fpath):
            raise ResultTypeError(f'File does not look like a time series {self.__class__.__name__} file: {fpath}')

        # call after tpc_reader has been initialised so that we know the file can be loaded by the reader
        if self._looks_empty(fpath):
            raise EOFError(f'File is empty or incomplete: {fpath}')

        # private properties
        self._tpc_reader = self._init_tpc_reader()
        self._time_series_data = AppendDict()
        self._maximum_data = AppendDict()
        self._nd_res_types = []

        self._loaded = False  # whether the results have been fully loaded
        self._initial_load()

    @staticmethod
    def _looks_like_this(fpath: PathLike) -> bool:
        # docstring inherited
        fpath = Path(fpath)
        if fpath.suffix.upper() != '.INFO':
            return False
        try:
            with fpath.open() as f:
                line = f.readline()
                if not line.startswith('Format Version == 1'):
                    return False
        except Exception as e:
            return False
        return True

    @staticmethod
    def _looks_empty(fpath: PathLike) -> bool:
        # docstring inherited
        tpc_reader = TPCReader(fpath)
        target_line_count = 10  # fairly arbitrary
        if tpc_reader.property_count() < target_line_count:
            return True
        node_count = tpc_reader.get_property('Number Nodes')
        channel_count = tpc_reader.get_property('Number Channels')
        if node_count + channel_count == 0:
            return True
        return False

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns all the available times for the given filter.

        The ``filter_by`` is an optional input that can be used to filter the return further. Valid filters
        for the ``INFO`` class are:

        * :code:`None`: default - returns all available times
        * :code:`1d`
        * :code:`node`: returns only node times
        * :code:`channel`: returns only channel times
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
        >>> res.times()
        [0.0, 0.016666666666666666, ..., 3.0]
        >>> res.times(fmt='absolute')
        [Timestamp('2021-01-01 00:00:00'), Timestamp('2021-01-01 00:01:00'), ..., Timestamp('2021-01-01 03:00:00')]
        """
        self._load()
        return super().times(filter_by, fmt)

    def ids(self, filter_by: str = None) -> list[str]:
        """Returns all the available IDs for the given filter.

        The ``filter_by`` argument can be used to add a filter to the returned IDs. Available filters for the ``INFO``
        class are:

        * :code:`None`: default - returns all :code:`timeseries` IDs
        * :code:`1d`: same as :code:`None` as class only contains 1D data
        * :code:`node`
        * :code:`channel`
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
        The below examples demonstrate how to use the ``filter_by`` argument to filter the returned IDs.
        The first example returns all IDs:

        >>> res.ids()
        ['FC01.1_R', 'FC01.2_R', 'FC04.1_C', 'FC01.1_R.1', 'FC01.1_R.2', 'FC01.2_R.1', 'FC01.2_R.2', 'FC04.1_C.1', 'FC04.1_C.2']

        Return only node IDs:

        >>> res.ids('node')
        ['FC01.1_R.1', 'FC01.1_R.2', 'FC01.2_R.1', 'FC01.2_R.2', 'FC04.1_C.1', 'FC04.1_C.2']

        Return IDs that have water level results:

        >>> res.ids('h')
        ['FC01.1_R.1', 'FC01.1_R.2', 'FC01.2_R.1', 'FC01.2_R.2', 'FC04.1_C.1', 'FC04.1_C.2']
        """
        self._load()
        if filter_by and 'section' in filter_by:
            filter_by = 'node'
        elif filter_by and 'timeseries' in filter_by:
            filter_by = None
        return super().ids(filter_by)

    def data_types(self, filter_by: str = None) -> list[str]:
        """Returns all the available data types (result types) for the given filter.

        The ``filter_by`` is an optional input that can be used to filter the return further. Available
        filters for the ``INFO`` class are:

        * :code:`None`: default - returns all :code:`timeseries` data types
        * :code:`1d`: same as :code:`None` as class only contains 1D data
        * :code:`node`
        * :code:`channel`
        * :code:`timeseries`: returns only IDs that have time series data.
        * :code:`section`: returns only IDs that have section data (i.e. long plot data).
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
        The below examples demonstrate how to use the filter argument to filter the returned data types. The first
        example returns all data types:

        >>> res.data_types()
        ['water level', 'flow', 'velocity']

        Returning only the :code:`node` data types:

        >>> res.data_types('node')
        ['water level']

        Return only data types for the channel :code:`FC01.1_R`:

        >>> res.data_types('FC01.1_R')
        ['flow', 'velocity']

        Return data types that are available for plotting section data:

        >>> res.data_types('section')
        ['bed level', 'pipes', 'pits', 'water level', 'max water level']
        """
        self._load()
        if filter_by and 'section' in filter_by:
            dtypes = super().data_types('node')
            dtypes += [f'max {x}' for x in dtypes if x in self._maximum_data]
            return ['bed level', 'pipes', 'pits'] + dtypes
        elif filter_by and 'timeseries' in filter_by:
            filter_by = None
        return super().data_types(filter_by)

    def maximum(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a DataFrame containing the maximum values for the given data types. The returned DataFrame
        will include time of maximum results as well.

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can also be a filter string, e.g. :code:`channel` to extract the maximum values for all
        channels. The following filters are available for the ``INFO`` class:

        * :code:`None`: returns all maximum values
        * :code:`1d`: returns all maximum values (same as passing in None for locations)
        * :code:`node`
        * :code:`channel`

        The returned DataFrame will have an index column corresponding to the location IDs, and the columns
        will be in the format :code:`obj/data_type/[max|tmax]`,
        e.g. :code:`channel/flow/max`, :code:`channel/flow/tmax`

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

        >>> res.maximum('ds1', 'flow')
             channel/flow/max  channel/flow/tmax
        ds1            59.423           1.383333

        Extracting all the maximum results for a given channel:

        >>> res.maximum(['ds1'], None)
             channel/Flow/max  ...  channel/Velocity/tmax
        ds1            59.423  ...               0.716667

        Extracting the maximum flow for all channels:

        >>> res.maximum(None, 'flow')
                 channel/flow/max   channel/flow/tmax
        ds1                 59.423           1.383333
        ds2                 88.177           1.400000
        ...                  ...              ...
        FC04.1_C             9.530           1.316667
        FC_weir1            67.995           0.966667
        """
        self._load()
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        filter_by = '/'.join(locations + data_types)
        ctx = self._filter(filter_by)
        if ctx.empty:
            return pd.DataFrame()

        df = self._maximum_extractor(ctx[ctx['domain'] == '1d'].data_type.unique(), data_types,
                                     self._maximum_data, ctx, time_fmt, self.reference_time)
        df.columns = self._prepend_1d_type_to_column_name(df.columns)

        return df

    def time_series(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                    time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a time-series DataFrame for the given location(s) and data type(s).

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can also be a filter string, e.g. :code:`channel` to extract the time-series values for all
        channels. The following filters are available for the ``INFO`` class:

        * :code:`None`: returns all locations
        * :code:`1d`: returns all locations (same as passing in None for locations)
        * :code:`node`
        * :code:`channel`

        The returned column names will be in the format :code:`obj/data_type/location`
        e.g. :code:`channel/flow/FC01.1_R`. The :code:`data_type` name in the column heading will be identical to the
        data type  name passed into the function e.g. if :code:`h` is used instead of :code:`water level`, then the
        return will be :code:`node/h/FC01.1_R.1`.

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

        Extracting all flow results

        >>> res.time_series(None, 'flow')
        Time (h)  channel/flow/ds1  ...  channel/flow/FC_weir1
        0.000000             0.000  ...                    0.0
        0.016667             0.000  ...                    0.0
        ...                    ...  ...                    ...
        2.983334             8.670  ...                    0.0
        3.000000             8.391  ...                    0.0
        """
        self._load()
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        filter_by = '/'.join(locations + data_types)
        ctx = self._filter(filter_by)
        if ctx.empty:
            return pd.DataFrame()

        share_idx = ctx[['start', 'end', 'dt']].drop_duplicates().shape[0] < 2
        df = self._time_series_extractor(ctx[ctx['domain'] == '1d'].data_type.unique(), data_types,
                                         self._time_series_data, ctx, time_fmt, share_idx, self.reference_time)
        df.columns = self._prepend_1d_type_to_column_name(df.columns)

        return df

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Returns a long plot for the given location and data types at the given time. If one location is given,
        the long plot will connect the given location down to the outlet. If 2 locations are given, then the
        long plot will connect the two locations (they must be connectable). If more than 2 locations are given,
        multiple long plots will be produced (each long plot will be given a unique :code:`branch_id`),
        however one channel must be a common downstream location and the other
        channels must be upstream of this location.

        The order of the locations in the :code:`location` parameter does not matter as both directions are
        checked, however it will be faster to include the upstream location first as this will be the first connection
        checked.

        The returned DataFrame will have the following columns:

        * :code:`branch_id`: The branch ID. If more than 2 pipes are provided, or the channels diverge at an intersection,
          then multiple branches will be returned. The same channel could be in multiple branches. The branch id
          starts at zero for the first branch, and increments by one for each additional branch.
        * :code:`channel`: The channel ID.
        * :code:`node`: The node ID.
        * :code:`offset`: The offset along the long plot
        * :code:`[data_types]`: The data types requested.

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the section data for. Unlike other plotting methods, the location cannot be None.
        data_types : str | list[str]
            The data type to extract the section data for. If None is passed in, all node data types will be returned.
        time : TimeLike
            The time to extract the section data for.

        Returns
        -------
        pd.DataFrame
            The section data.

        Raises
        ------
        ValueError
            Raised if no valid :code:`locations` are provided or if :code:`data_types` is not :code:`None`
            but the provided :code:`data_types` are all invalid. A value error is also raised if more than one location
            is provided and the locations are not connected.

        Examples
        --------
        Extracting a long plot from a given channel :code:`ds1` to the outlet at :code:`1.0` hours:

        >>> res.section('ds1', ['bed', 'level', 'max level'], 1.)
            branch_id  channel       node  offset     bed    level  max level
        0           0      ds1      ds1.1     0.0  35.950  38.7880    39.0671
        6           0      ds1      ds1.2    30.2  35.900  38.6880    38.9963
        1           0      ds2      ds1.2    30.2  35.900  38.6880    38.9963
        7           0      ds2      ds2.2    88.8  35.320  38.1795    38.5785
        2           0      ds3      ds2.2    88.8  35.320  38.1795    38.5785
        8           0      ds3      ds3.2   190.0  34.292  37.1793    37.4158
        3           0      ds4      ds3.2   190.0  34.292  37.1793    37.4158
        9           0      ds4      ds4.2   301.6  33.189  35.6358    35.9533
        4           0      ds5      ds4.2   301.6  33.189  35.6358    35.9533
        10          0      ds5      ds5.2   492.7  31.260  33.9942    34.3672
        5           0  ds_weir      ds5.2   492.7  32.580  33.9942    34.3672
        11          0  ds_weir  ds_weir.2   508.9  32.580  32.9532    33.4118

        Extracting a long plot between :code:`ds1` and :code:`ds4` at :code:`1.0` hours:

        >>> res.section(['ds1', 'ds4'], ['bed', 'level', 'max level'], 1.)
           branch_id channel   node  offset     bed    level  max level
        0          0     ds1  ds1.1     0.0  35.950  38.7880    39.0671
        4          0     ds1  ds1.2    30.2  35.900  38.6880    38.9963
        1          0     ds2  ds1.2    30.2  35.900  38.6880    38.9963
        5          0     ds2  ds2.2    88.8  35.320  38.1795    38.5785
        2          0     ds3  ds2.2    88.8  35.320  38.1795    38.5785
        6          0     ds3  ds3.2   190.0  34.292  37.1793    37.4158
        3          0     ds4  ds3.2   190.0  34.292  37.1793    37.4158
        7          0     ds4  ds4.2   301.6  33.189  35.6358    35.9533
        """
        self._load()
        # get locations and data types
        locations, data_types = self._figure_out_loc_and_data_types_lp(locations, data_types, 'channel')

        # get the time index
        times = self.times(fmt='absolute') if isinstance(time, datetime) else self.times()
        timeidx = self._closest_time_index(times, time)

        # get connectivity
        dfconn = self._connectivity(locations)

        # init long plot DataFrame
        df = self._lp.init_lp(dfconn)

        # loop through data types and add them to the data frame
        for dtype in data_types:
            dtype1 = self._get_standard_data_type_name(dtype)

            if dtype1 == 'bed level':
                df1 = self._lp.melt_2_columns(dfconn, ['us_invert', 'ds_invert'], dtype)
                df[dtype] = df1[dtype]
            elif dtype1 == 'pipes':
                df1 = self._lp.melt_2_columns(dfconn, ['lbus_obvert', 'lbds_obvert'], dtype)
                df1 = df1.join(self._channel_info['ispipe'], on='channel')
                df1.loc[~df1['ispipe'], dtype] = np.nan
                df[dtype] = df1[dtype]
            elif dtype1 == 'pits':
                df[dtype] = self._get_pits(dfconn)
            elif 'tmax' in dtype1:
                dtype1 = dtype1.replace('TMax', '').strip()
                df[dtype] = self._maximum_data[dtype1][0].loc[df['node'], 'tmax'].tolist()
            elif 'max' in dtype1:
                dtype1 = dtype1.replace('Max', '').strip()
                df[dtype] = self._maximum_data[dtype1][0].loc[df['node'], 'max'].tolist()
            else:  # temporal result
                idx = self._time_series_data[dtype1][0].index[timeidx]
                df[dtype] = self._time_series_data[dtype1][0].loc[idx, df['node']].tolist()

        return df

    def curtain(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``INFO`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support curtain plotting.')

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``INFO`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support vertical profile plotting.')

    def _initial_load(self) -> None:
        """Does an initial, light-weight, load of some of the basic properties."""
        self.name = self._tpc_reader.get_property('Simulation ID')
        self.units = 'si' if self._tpc_reader.get_property('Units') == 'METRIC' else 'us customary'
        self.node_count = self._tpc_reader.get_property(r'Number (?:1D\s)?Nodes', 0, regex=True)
        self.channel_count = self._tpc_reader.get_property(r'Number (?:1D\s)?Channels', 0, regex=True)

    def _load(self):
        if self._loaded:
            return
        self._load_node_info()
        self._load_chan_info()
        self._load_time_series()
        self._load_maximums()
        self._load_1d_info()
        self._loaded = True

    def _filter(self, filter_by: str) -> pd.DataFrame:
        # docstring inherited
        # split filter into components
        ctx = [x.strip().lower() for x in filter_by.split('/')] if filter_by else []
        return super()._combinations_1d(ctx)

    def _init_tpc_reader(self) -> TPCReader:
        """Initialise the TPCReader object."""
        return TPCReader(self.fpath)

    def _info_name_correction(self, name: str) -> str:
        """Correct the name of the file. Only required for INFO results and should be overerriden by subclasses."""
        return name.replace('_1d_','_1d_1d_')

    def _expand_property_path(self, prop: str, regex: bool = False, value: str = None) -> Path:
        """Expands the property value into a full path. Returns None if the property does not exist."""
        prop_path = self._tpc_reader.get_property(prop, None, regex) if value is None else value
        if prop_path not in [None, 'NONE']:
            if 'node info' in prop.lower() or 'channel info' in prop.lower():
                prop_path = self._info_name_correction(prop_path)
            return self.fpath.parent / prop_path

    def _load_node_info(self) -> None:
        """Load node info DataFrame."""
        node_info_csv = self._expand_property_path(r'(?:1D\s)?Node Info', regex=True)
        if node_info_csv is not None:
            try:
                self._node_info = pd.read_csv(
                    node_info_csv,
                    engine='python',
                    index_col='id',
                    names=['no', 'id', 'bed_level', 'top_level', 'nchannel', 'channels'],
                    header=None,
                    on_bad_lines=lambda x: x[:5] + [tuple(x[5:])],
                )
                self._node_info.drop('no', axis=1, inplace=True)
                self._node_info.drop('Node', axis=0, inplace=True)
                self._node_info.replace({'bed_level': '**********'}, np.nan, inplace=True)
                self._node_info.replace({'top_level': '**********'}, np.nan, inplace=True)
                self._node_info['bed_level'] = self._node_info['bed_level'].astype(float)
                self._node_info['top_level'] = self._node_info['bed_level'].astype(float)
                self._node_info['nchannel'] = self._node_info['nchannel'].astype(int)
            except Exception as e:
                logger.warning(f'INFO._load_node_info(): Error loading node info: {e}')

    def _load_chan_info(self) -> None:
        """Load channel info DataFrame."""
        chan_info_csv = self._expand_property_path(r'(?:1D\s)?Channel Info', regex=True)
        if chan_info_csv is not None:
            try:
                self._channel_info = pd.read_csv(
                    chan_info_csv,
                    engine='python',
                    index_col='id',
                    names=['no', 'id', 'us_node', 'ds_node', 'us_channel', 'ds_channel', 'flags', 'length', 'form_loss',
                           'n', 'pslope', 'us_invert', 'ds_invert', 'lbus_obvert', 'rbus_obvert', 'lbds_obvert',
                           'rbds_obvert', 'pblockage'],
                    header=None,
                    skiprows=1,
                    na_values=['**********'],
                    converters={
                        'length': float,
                        'form_loss Loss': float,
                        'n': float,
                        'pSlope': float,
                        'us_invert': float,
                        'ds_invert': float,
                        'lbus_obvert': float,
                        'rbus_obvert': float,
                        'lbds_obvert': float,
                        'rbds_obvert': float,
                        'pblockage': float,
                    }
                )
                self._channel_info.drop('no', axis=1, inplace=True)
                self._channel_info['ispipe'] = self._channel_info['flags'].str.match(r'.*[CR].*', False)
            except Exception as e:
                logger.warning(f'INFO._load_chan_info(): Error loading channel info: {e}')

    def _load_1d_info(self) -> None:
        """Loads the 1D info into a single table with data type and temporal information."""
        info = {'id': [], 'data_type': [], 'geometry': [], 'start': [], 'end': [], 'dt': []}
        for dtype, vals in self._time_series_data.items():
            for df1 in vals:
                dt = np.round((df1.index[1] - df1.index[0]) * 3600., decimals=2)
                start = df1.index[0]
                end = df1.index[-1]
                for col in df1.columns:
                    info['id'].append(col)
                    info['data_type'].append(dtype)
                    info['geometry'].append('point' if dtype in self._nd_res_types else 'line')
                    info['start'].append(start)
                    info['end'].append(end)
                    info['dt'].append(dt)

        self._oned_objs = pd.DataFrame(info)

    def _load_time_series(self) -> None:
        """Load time-series data into memory."""
        self._nd_res_types = ['water level']
        for res in ['Water Levels', 'Flows', 'Velocities']:
            p = self._expand_property_path(res)
            if p is not None:
                try:
                    df = self._load_time_series_csv(p)
                    stnd = self._get_standard_data_type_name(res)  # convert to a standard data type name
                    self._time_series_data[stnd] = df
                except Exception as e:
                    logger.warning(f'INFO._load_time_series(): Error loading time series from {p}: {e}')

    def _load_time_series_csv(self, fpath: Path) -> pd.DataFrame:
        """Load the time-series data from the CSV file into a DataFrame."""
        with fpath.open() as f:
            header = f.readline()
            index_col = header.split(',')[1].strip('"')
        df = pd.read_csv(fpath, na_values='**********', index_col=index_col)
        df.index.name = 'Time (h)'
        df.drop(df.columns[0], axis=1, inplace=True)
        df.rename(columns={x: self._csv_col_name_corr(x) for x in df.columns}, inplace=True)
        return df

    def _csv_col_name_corr(self, name: str) -> str:
        """Correct the column name in the CSV file to be just the id."""
        if not re.findall(r'(Entry|Additional|Exit) LC', name):
            name = ' '.join(name.split(' ')[1:])
        name = re.sub(r'\[.*]', '', name).strip()
        return name

    def _load_maximums(self) -> None:
        """Load the result maximums."""
        # info class does not have actual maximums, so need to be post-processed.
        for data_type, results in self._time_series_data.items():
            for res in results:
                max_ = res.max()
                tmax = res.idxmax()
                self._maximum_data[data_type] = pd.DataFrame({'max': max_, 'tmax': tmax})

    def _prepend_1d_type_to_column_name(self, columns: pd.Index) -> pd.Index:
        """Prepend 'node' or 'channel' to the column names.
        Requires all results to be 1D (no mixed in in po or rl results).
        """
        def col_names(x):
            x1 = x.split('/')
            t = len(x1) > 2  # is time column
            dtype = x1[1] if t else x1[0]
            dtype = self._get_standard_data_type_name(dtype)
            c = 'node' if dtype in self._nd_res_types else 'channel'
            return f'{x1[0]}/{c}/{x1[1]}/{x1[2]}' if t else f'{c}/{x1[0]}/{x1[1]}'

        return columns.to_series().apply(col_names)

    def _loc_data_types_to_list(self, locations: Union[str, list[str], None],
                                       data_types: Union[str, list[str], None]) -> tuple[list[str], list[str]]:
        """Convert locations and data_types to list format."""
        locations = locations if locations is not None else []
        locations = locations if isinstance(locations, list) else [locations]
        data_types = data_types if data_types is not None else []
        data_types = data_types if isinstance(data_types, list) else [data_types]
        return locations, data_types

    def _figure_out_loc_and_data_types_lp(self, locations: Union[str, list[str]],
                                          data_types: Union[str, list[str], None],
                                          filter_by: str) -> tuple[list[str], list[str]]:
        """Figure out the locations and data types to use - long profile edition."""
        # sort out locations and data types
        if not locations:
            raise ValueError('No locations provided.')
        else:
            valid_loc = self.ids(filter_by)
            valid_loc_lower = [x.lower() for x in valid_loc]
            locations1 = []
            locations = [locations] if not isinstance(locations, list) else locations
            for loc in locations:
                if loc.lower() not in valid_loc_lower:
                    logger.warning(f'INFO.section(): Location "{loc}" not found in the output - removing.')
                else:
                    locations1.append(valid_loc[valid_loc_lower.index(loc.lower())])
            locations = locations1
            if not locations:
                raise ValueError('No valid locations provided.')

        if not data_types:
            data_types = self.data_types('section')
        else:
            data_types = [data_types] if not isinstance(data_types, list) else data_types
            valid_types = self.data_types('section')
            data_types1 = []
            for dtype in data_types:
                if self._get_standard_data_type_name(dtype) not in valid_types:
                    logger.warning(
                        f'INFO.section(): Data type "{dtype}" is not a valid section data type or '
                        f'not in output - removing.'
                    )
                else:
                    data_types1.append(dtype)
            if not data_types1:
                raise ValueError('No valid data types provided.')
            data_types = data_types1

        return locations, data_types

    def _get_pits(self, dfconn: pd.DataFrame) -> np.ndarray:
        """Get the pit data for the long plot."""
        y = []
        for i, row in dfconn.iterrows():
            nd = row['us_node']
            pits = self._channel_info[
                (self._channel_info['ds_node'] == nd) & (self._channel_info['us_channel'] == '------')
                & (self._channel_info['ds_channel'] == '------')].index.tolist()
            if pits:
                y.append(self._channel_info.loc[pits[0], 'lbus_obvert'])
            else:
                y.append(np.nan)
            if i + 1 == dfconn.shape[0]:
                nd = row['ds_node']
                pits = self._channel_info[
                    (self._channel_info['us_node'] == nd) & (self._channel_info['us_channel'] == '------')
                    & (self._channel_info['ds_channel'] == '------')].index.tolist()
                if pits:
                    y.append(self._channel_info.loc[pits[0], 'lbus_obvert'])
                else:
                    y.append(np.nan)
            else:
                y.append(np.nan)

        return np.array(y)
