import re
from typing import Union, TYPE_CHECKING
from collections import OrderedDict
from packaging.version import Version

import numpy as np
import pandas as pd

from pytuflow._outputs.gpkg_base import GPKGBase
from pytuflow._outputs.helpers.tpc_reader import TPCReader
from pytuflow._outputs.info import INFO
from pytuflow._pytuflow_types import PathLike, TimeLike, TuflowPath

if TYPE_CHECKING:
    from sqlite3 import Cursor


class GPKG1D(INFO, GPKGBase):
    """Class for handling 1D GeoPackage time series results (:code:`.gpkg` - typically ending with :code:`_1D.gpkg`
    or :code:`_swmm_ts.gpkg`). The GPKG time series format is a specific format published by TUFLOW built
    on the GeoPackage standard.

    This class can be used to initialise stand-alone GPKG result files (e.g. :code:`swmm_ts.gpkg` results) however it is
    not required to be used if loading results via the :class:`TPC <pytuflow.outputs.TPC>` class which will load all
    domains automatically (i.e. :code:`GPKG1D`, :code:`GPKG2D`, :code:`GPKGRL`). Note: the :code:`swmm_ts.gpkg` is not
    referenced in the TPC file, so will always require to be initialised with this class.

    The ``GPKG1D`` class will only load basic properties on initialisation. These are typically properties
    that are easy to obtain from the file without having to load any of the time-series results. Once a method
    requiring more detailed information is called, the full results will be loaded. This makes the ``GPKG1D`` class
    very cheap to initialise.

    Parameters
    ----------
    fpath : PathLike
        The path to the output (.gpkg) file.

    Raises
    ------
    ResultTypeError
        Raises :class:`pytuflow.results.ResultTypeError` if the file does not look like a ``GPKG1D`` file.

    Examples
    --------
    Load a :code:`_swmm_ts.gpkg` file:

    >>> from pytuflow import GPKG1D
    >>> res = GPKG1D('path/to/output_swmm_ts.gpkg')

    Querying all the available data types:

    >>> res.data_types()
    ['depth', 'water level', 'storage volume', 'lateral inflow', 'total inflow', 'flood losses', 'net lateral inflow',
    'flow', 'channel depth', 'velocity', 'channel volume', 'channel capacity']

    Querying all the available channel IDs:

    >>> res.ids('channel')
    ['FC01.1_R', 'FC01.2_R', 'FC04.1_C', 'Pipe1', 'Pipe10', 'Pipe11', 'Pipe13', 'Pipe14', 'Pipe15', 'Pipe16', 'Pipe2',
    'Pipe20', 'Pipe3', 'Pipe4', 'Pipe6', 'Pipe7', 'Pipe8', 'Pipe9']

    Extracting time series data for a given channel and data type:

    >>> res.time_series('Pipe1', 'flow')
    time      channel/flow/Pipe1
    0.000000            0.000000
    0.083333            0.000000
    0.166667            0.000000
    0.250000            0.000000
    0.333333            0.000038
    ...                      ...
    2.666667            0.009748
    2.750000            0.008384
    2.833333            0.007280
    2.916667            0.005999
    3.000000            0.004331

    For more examples, see the documentation for the individual methods.
    """

    def __init__(self, fpath: PathLike):
        #: Version: the format version
        self.format_version = None

        # private properties
        self._gis_layer_p_name = None
        self._gis_layer_l_name = None
        self._is_swmm = False

        super().__init__(fpath)

    @staticmethod
    def _looks_like_this(fpath: PathLike) -> bool:
        # docstring inherited
        import sqlite3
        try:
            conn = sqlite3.connect(fpath)
        except Exception as e:
            return False
        try:
            cur = conn.cursor()
            cur.execute('SELECT Version FROM TUFLOW_timeseries_version;')
            version = Version(cur.fetchone()[0])
            if version == Version('1.0'):
                valid = True
            else:
                cur.execute('SELECT Type FROM Geom_L LIMIT 1;')
                typ = cur.fetchone()
                if typ:
                    typ = typ[0]
                    valid = bool(re.findall(r'^Chan', typ))
                else:
                    valid = True  # cannot check any result if there aren't any
        except Exception as e:
            valid = False
        finally:
            conn.close()
        return valid

    @staticmethod
    def _looks_empty(fpath: PathLike) -> bool:
        # docstring inherited
        import sqlite3
        try:
            conn = sqlite3.connect(fpath)
        except Exception as e:
            return True
        try:
            cur = conn.cursor()
            cur.execute('SELECT DISTINCT Table_name, Count FROM Timeseries_info;')
            count = sum([int(x[1]) for x in cur.fetchall()])
            empty = count == 0
        except Exception:
            empty = True
        finally:
            conn.close()
        return empty

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns all the available times for the given filter.

        The ``filter_by`` is an optional input that can be used to filter the return further. Valid filters
        for the ``GPKG1D`` class are:

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
        return super().times(filter_by, fmt)

    def ids(self, filter_by: str = None) -> list[str]:
        """Returns all the available IDs for the given filter.

        The ``filter_by`` argument can be used to add a filter to the returned IDs. Available filters for the ``GPKG1D``
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
        return super().ids(filter_by)

    def data_types(self, filter_by: str = None) -> list[str]:
        """Returns all the available data types (result types) for the given filter.

        The ``filter_by`` is an optional input that can be used to filter the return further. Available
        filters for the ``GPKG1D`` class are:

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
        return super().data_types(filter_by)

    def maximum(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a DataFrame containing the maximum values for the given data types. The returned DataFrame
        will include time of maximum results as well.

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can also be a filter string, e.g. :code:`channel` to extract the maximum values for all
        channels. The following filters are available for the ``GPKG1D`` class:

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
        return super().maximum(locations, data_types, time_fmt)

    def time_series(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                    time_fmt: str = 'relative', *args, **kwargs) -> pd.DataFrame:
        """Returns a time-series DataFrame for the given location(s) and data type(s).

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can also be a filter string, e.g. :code:`channel` to extract the time-series values for all
        channels. The following filters are available for the ``GPKG1D`` class:

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
        return super().time_series(locations, data_types, time_fmt)

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike, *args, **kwargs) -> pd.DataFrame:
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
        return super().section(locations, data_types, time)

    def curtain(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``GPKG1D`` results. Raises a :code:`NotImplementedError`."""
        return super().curtain(locations, data_types, time)

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``GPKG1D`` results. Raises a :code:`NotImplementedError`."""
        return super().profile(locations, data_types, time)

    def _initial_load(self):
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute('SELECT Version FROM TUFLOW_timeseries_version;')
            self.format_version = Version(cur.fetchone()[0])
            if self.format_version < Version('1.1'):
                self._is_swmm = True
                self.name = re.sub(r'_swmm_ts$', '', self.fpath.stem)
            else:
                self.name = re.sub(r'_TS_1D$', '', self.fpath.stem)

            reference_time = None
            cur.execute(
                'SELECT DISTINCT Table_name, Count, Series_name, Series_units, Reference_time FROM Timeseries_info;')
            for table_name, count, series_name, units, rt in cur.fetchall():
                if reference_time is None:
                    reference_time, _ = self._parse_time_units_string(rt, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
                                                                '%Y-%m-%d %H:%M:%S')
                if re.findall('_P$', table_name):
                    self.node_count = count
                    self._gis_layer_p_name = table_name
                else:
                    self.channel_count = count
                    self._gis_layer_l_name = table_name
                if series_name.lower() == 'water level' and units.lower() == 'ft':
                    self.units = 'us imperial'
            if reference_time is not None:
                self.reference_time = reference_time

            self.gis_layer_p_fpath = TuflowPath(self.fpath.parent) / f'{self.fpath.name} >> {self._gis_layer_p_name}'
            self.gis_layer_l_fpath = TuflowPath(self.fpath.parent) / f'{self.fpath.name} >> {self._gis_layer_l_name}'

    def _load(self):
        if self._loaded:
            return

        with self._connect() as conn:
            cur = conn.cursor()
            self._load_channel_info(cur)
            self._load_node_info(cur)
            self._load_time_series(cur)
            self._load_maximums()
            self._load_1d_info()

        self._loaded = True

    def _init_tpc_reader(self) -> TPCReader:
        pass

    def _load_time_series(self, cur: 'Cursor'):
        # nodes
        cur.execute(f'SELECT Column_name FROM Timeseries_info WHERE Table_name = "{self._gis_layer_p_name}";')
        data_types = [x[0] for x in cur.fetchall()]
        for dtype in data_types:
            dtype1 = 'node flow regime' if dtype == 'Flow Regime' else self._get_standard_data_type_name(dtype)
            self._nd_res_types.append(dtype1)
            self._time_series_data[dtype1] = self._gpkg_time_series_extractor(cur, dtype, self._gis_layer_p_name)

        # channels
        cur.execute(f'SELECT Column_name FROM Timeseries_info WHERE Table_name = "{self._gis_layer_l_name}";')
        data_types = [x[0] for x in cur.fetchall()]
        for dtype in data_types:
            dtype1 = 'channel flow regime' if dtype == 'Flow Regime' else self._get_standard_data_type_name(dtype)
            self._time_series_data[dtype1] = self._gpkg_time_series_extractor(cur, dtype, self._gis_layer_l_name)

    def _load_channel_info(self, cur: 'Cursor'):
        COLUMNS = ['id', 'flags', 'length', 'us_node', 'ds_node', 'us_invert', 'ds_invert',
                   'lbus_obvert', 'rbus_obvert', 'lbds_obvert', 'rbds_obvert']
        TYPE_MAP = [str, str, float, str, str, float, float, float, float, float, float]
        if self._is_swmm:
            cur.execute(
                'SELECT '
                'l.ID as id, '
                'l.Shape as flags, '
                'l.Length as length, '
                'p1.ID as "us_node", '
                'p2.ID as "ds_node", '
                'l.US_Invert as "us_invert", '
                'l.DS_Invert as "ds_invert", '
                'l.US_Obvert as "lbus_obvert", '
                'l.US_Obvert as "rbus_obvert", '
                'l.DS_Obvert as "lbds_obvert", '
                'l.DS_Obvert as "rbds_obvert" '
                'FROM Lines_L AS l '
                'LEFT JOIN Points_P as p1 ON l.US_Node = p1.fid '
                'LEFT JOIN Points_P as p2 ON l.DS_Node = p2.fid;'
            )
        else:
            cur.execute(
                'SELECT '
                'l.ID as id, '
                'l.Type as flags, '
                'l.Length as length, '
                'p1.ID as us_node, '
                'p2.ID as ds_node, '
                'l.US_Invert as us_invert, '
                'l.DS_Invert as ds_invert, '
                'l.LBUS_Obvert as lbus_obvert, '
                'l.RBUS_Obvert as rbus_obvert, '
                'l.LBDS_Obvert as lbds_obvert, '
                'l.RBDS_Obvert as lbds_obvert '
                'from Geom_L as l '
                'LEFT JOIN Geom_P as p1 ON l.US_Node = p1.fid '
                'LEFT JOIN Geom_P as p2 ON l.DS_Node = p2.fid;'
            )
        ret = cur.fetchall()
        if ret:
            d = OrderedDict({x: [] for x in COLUMNS})
            for row in ret:
                for i, col in enumerate(COLUMNS):
                    try:
                        d[col].append(TYPE_MAP[i](row[i]))
                    except (TypeError, ValueError):
                        d[col].append(np.nan)
            self._channel_info = pd.DataFrame(d)
            self._channel_info.set_index('id', inplace=True)
            self._channel_info['flags'].apply(lambda x: x.split('[')[1].strip(']') if '[' in x else x)
            if self._is_swmm:
                self._channel_info['ispipe'] = (~np.isnan(self._channel_info['lbus_obvert']) & ~np.isnan(self._channel_info['lbds_obvert']))
                self._channel_info['ispit'] = False
            else:
                self._channel_info['ispipe'] = self._channel_info['flags'].str.match(r'.*[CR].*', False)
                self._channel_info['ispit'] = self._channel_info.index == self._channel_info['ds_node']
        else:
            self._channel_info = pd.DataFrame([], columns=COLUMNS)

    def _load_node_info(self, cur: 'Cursor'):
        if self._is_swmm:
            COLUMNS = ['id', 'bed_level', 'top_level', 'inlet_level']
            TYPE_MAP = [str, float, float, float]
            cur.execute(
                'SELECT '
                'ID as id, '
                'Invert_elevation as "bed_level", '
                'Top_elevation as "top_level", '
                'Inlet_elevation as "inlet_level" '
                'FROM Points_P;'
            )
            ret = cur.fetchall()
            if ret:
                d = OrderedDict({x: [] for x in COLUMNS})
                for row in ret:
                    for i, col in enumerate(COLUMNS):
                        try:
                            d[col].append(TYPE_MAP[i](row[i]))
                        except (TypeError, ValueError):
                            d[col].append(np.nan)
                self._node_info = pd.DataFrame(d)
                self._node_info.set_index('id', inplace=True)
            else:
                self._node_info = pd.DataFrame([], columns=COLUMNS + ['nchannel', 'channels'])
                self._node_info.set_index('id', inplace=True)
        else:
            cur.execute('SELECT ID as id FROM Geom_P;')
            ret = cur.fetchall()
            if ret:
                self._node_info = pd.DataFrame(index=[x[0] for x in ret])
                self._node_info['nchannel'] = 0
                self._node_info['channels'] = ''
            else:
                self._node_info = pd.DataFrame([], columns=['id', 'nchannel', 'channels'])
                self._node_info.set_index('id', inplace=True)

        if self._node_info.empty:
            return

        # get the number of channels and the channels for each node
        chan_info = self._channel_info.loc[~self._channel_info['ispit'], :]  # don't include channels that are pits
        self._node_info['nchannel'] = 0
        self._node_info['channels'] = ''
        for node in self._node_info.index:
            us = chan_info[chan_info['us_node'] == node].index.tolist()
            ds = chan_info[chan_info['ds_node'] == node].index.tolist()
            self._node_info.loc[node, 'nchannel'] = len(us) + len(ds)
            if len(us) + len(ds) == 1:  # to match how it's done in the TPC node_info.csv
                if us:
                    self._node_info.at[node, 'channels'] = us[0]
                else:
                    self._node_info.at[node, 'channels'] = ds[0]
            else:
                self._node_info.at[node, 'channels'] = us + ds

    def _get_pits(self, dfconn: pd.DataFrame) -> np.ndarray:
        if self._is_swmm:
            df = dfconn.copy()
            # get inlet levels at upstream nodes
            df['pit'] = self._node_info.loc[dfconn['us_node'], 'inlet_level'].tolist()
            # need to get the last downstream node since it won't be accounted for by any upstream node
            df['pit_'] = np.nan
            nd = df.iloc[-1, df.columns.get_loc('ds_node')]
            df.iloc[-1, df.columns.get_loc('pit_')] = self._node_info.loc[nd, 'inlet_level']
        else:
            df = dfconn.copy()
            pits = []
            for nd in df['us_node']:
                if nd in self._channel_info.index and self._channel_info.loc[nd, 'ispit']:
                    pits.append(self._channel_info.loc[nd, 'lbus_obvert'])
                else:
                    pits.append(np.nan)
            df['pit'] = pits

            df['pit_'] = np.nan
            nd = dfconn.iloc[-1, dfconn.columns.get_loc('ds_node')]
            if nd in self._channel_info.index and self._channel_info.loc[nd, 'ispit']:
                df.iloc[-1, dfconn.columns.get_loc('pit_')] = self._channel_info.loc[nd, 'lbus_obvert']

        df1 = self._lp.melt_2_columns(df, ['pit', 'pit_'], 'pits')
        return df1['pits'].to_numpy()
