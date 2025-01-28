from datetime import datetime
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from pytuflow.outputs.helpers import TPCReader
from pytuflow.outputs.helpers.get_standard_data_type_name import get_standard_data_type_name
from pytuflow.outputs.info import INFO
from pytuflow.pytuflow_types import PathLike, FileTypeError, TimeLike, ResultError
from pytuflow.outputs.helpers.fm_res_driver import FM_ResultDriver
from pytuflow.outputs.helpers.lp_1d_fm import LP1D_FM
from pytuflow.fm import GXY
from pytuflow.fm import DAT
from pytuflow.util.time_util import closest_time_index
from pytuflow.util.logging import get_logger


logger = get_logger()


class FMTS(INFO):
    """Class for handling 1D Flood Modeller time series outputs.

    The accepted result formats are:

    * :code:`.zzn` (requires the accompanying :code:`.zzl` file)
    * :code:`.csv` exported from the Flood Modeller GUI.
    * :code:`.csv` exported using the Flood Modeller API Python library

    Optional DAT and GXY files can be provided to add connectivity and spatial information. The DAT file is preferenced
    over GXY for connectivity information as channel direction around JUNCTION units can be ambiguous in the GXY.
    Spatial information contained in the DAT file is never used and a GXY file is required for spatial information.

    Parameters
    ----------
    fpath : :class:`PathLike <pytuflow.pytuflow_types.PathLike>`
        The path to the flood modeller result file(s). Multiple files can be passed if not using the :code:`.zzn`
        result format. Multiple files are required to be for different result types for the same event, and not
        for multiple events.
    dat : :class:`PathLike <pytuflow.pytuflow_types.PathLike>`, optional
        Path to the DAT file. Required for connectivity information (i.e. required for :meth:`section` plotting).
    gxy : :class:`PathLike <pytuflow.pytuflow_types.PathLike>`, optional
        Path to the GXY file. Required for spatial coordinates.

    Raises
    ------
    FileNotFoundError
        Raises if the result file(s) does not exist.
    FileTypeError
        Raises :class:`pytuflow.pytuflow_types.FileTypeError` if the file(s) does not look like a FM time series result.
    EOFError
        Raises if the result file(s) is empty or incomplete.
    ResultError
        Raises :class:`pytuflow.pytuflow_types.ResultError` if the result file(s) do not contain the expected
        data e.g. if multiple files are provided, but they belong to different models or different events.

    Examples
    --------
    Load results without any reference to the DAT or GXY files - this will not support section plotting and won't
    contain spatial information:

    >>> from pytuflow.outputs import FMTS
    >>> res = FMTS('path/to/result.zzn')

    Load results with a DAT file so that connectivity information is available for section plotting:

    >>> res = FMTS('path/to/result.zzn', dat='path/to/result.dat')

    Load results with a GXY so spatial information is available - a GXY can also be used for connectivity
    without a DAT file, however less contextual information is contained in the GXY and channel directions around
    JUNCTION nodes can be ambiguous. The DAT file is recommended, and is required for plotting :code:`pipes`
    in the section plot:

    >>> res = FMTS('path/to/result.zzn', dat='path/to/result.dat', gxy='path/to/result.gxy')

    Return all node IDs - Only nodes that contain results will be return by default and will be returned with just
    the node name. To return all nodes with unique IDs (:code:`TYPE_SUBTYPE_NAME`), use the :code:`context` parameter:

    >>> res.ids()
    ['FC01.36', 'FC01.35', 'FC01.351cu',... 'FC02', 'ds2_S', 'FC01']
    >>> res.ids('node')
    ['QTBDY__FC01', 'JUNCTION_OPEN_FC01', 'RIVER_SECTION_FC01.40',... 'JUNCTION_OPEN_ds2', 'SPILL__ds2_S']

    Return available result types:

    >>> res.data_types()
    ['flow', 'water level', 'froude', 'velocity', 'mode', 'state']

    Return the :code:`water level` time series for :code:`FC04368`:

    >>> res.time_series('FC01.35', 'stage')
    time      node/stage/FC01.35
    0.000000           44.803001
    0.083333           45.329525
    0.166667           45.717449
    0.250000           45.766171
    0.333333           45.776295
    ...                      ...
    2.666667           45.778118
    2.750000           45.778111
    2.833333           45.778091
    2.916667           45.778099
    3.000000           45.778137

    Return th maximum :code:`water level` along a section between :code:`FC01.31` and :code:`FC01.25`:

    >>> res.section(['FC01.31', 'FC01.25'], 'stage', 0)
        branch_id channel      node   offset  max water level
    0           0      36   FC01.31    0.000        43.308998
    7           0      36   FC01.30   30.758        43.060001
    1           0      37   FC01.30   30.758        43.060001
    8           0      37   FC01.29   62.745        42.870998
    2           0      38   FC01.29   62.745        42.870998
    9           0      38  FC01.28B  112.141        42.409000
    3           0      39  FC01.28B  112.141        42.409000
    10          0      39   FC01.28  146.031        42.105000
    4           0      40   FC01.28  146.031        42.105000
    11          0      40   FC01.27  187.033        41.692001
    5           0      41   FC01.27  187.033        41.692001
    12          0      41   FC01.26  200.826        41.493999
    6           0      42   FC01.26  200.826        41.493999
    13          0      42   FC01.25  233.658        41.021000
    """
    _PLOTTING_CAPABILITY = ['timeseries', 'section']

    def __init__(self, fpath: Union[PathLike, list[PathLike]], dat: PathLike = None, gxy: PathLike = None):
        # private
        self._fpaths = fpath if isinstance(fpath, list) else [fpath]
        self._fpaths = [Path(f) for f in self._fpaths if f]
        self._support_section_plotting = False

        #: list[FM_ResultDriver]: Storage for the result drivers.
        self.storage = []

        #: Path: Path to the DAT file if one was provided
        self.dat_fpath = Path(dat) if dat is not None else None

        #: Path: Path to the GXY file if one was provided
        self.gxy_fpath = Path(gxy) if gxy is not None else None

        #: DAT: DAT object.
        self.dat = None

        #: GXY: GXY object.
        self.gxy = None

        for f in self._fpaths:
            if not f.exists():
                raise FileNotFoundError(f'File not found: {f}')
            if not self.looks_like_this(f):
                raise FileTypeError(f'File does not look like a Flood Modeller time series result: {f}')
            if self.looks_empty(f):
                raise EOFError(f'File is empty or incomplete: {f}')

        super().__init__(self._fpaths[0])

    @staticmethod
    def looks_like_this(fpath: Path) -> bool:
        # docstring inherited
        driver = FM_ResultDriver(fpath)
        return driver.driver_name != ''

    @staticmethod
    def looks_empty(fpath: PathLike) -> bool:
        # docstring inherited
        driver = FM_ResultDriver(fpath)
        return driver.df is None or driver.df.empty

    def times(self, context: str = None, fmt: str = 'relative') -> list[TimeLike]:
        # docstring inherited
        return super().times(context, fmt)

    def data_types(self, context: str = None) -> list[str]:
        # docstring inherited
        dat_types = super().data_types(context)
        if context and 'section' in context:
            if not self._support_section_plotting:
                return []
            if 'pits' in dat_types:
                dat_types.remove('pits')
        return dat_types

    def ids(self, context: str = None) -> list[str]:
        """Returns all the available IDs for the given context. By default, only IDs that contain results are returned.
        The returned IDs are also returned as just their name e.g. :code:`FC01.1_R` rather than the full ID
        e.g. :code:`CONDUIT_CIRCULAR_FC01.1_R`.

        The context argument can be used to add a filter to the returned IDs. Available context objects for this
        class are:

        * :code:`None`: default - returns all :code:`timeseries` IDs (i.e. IDs that contain results).
        * :code:`1d`: same as :code:`None` as class only contains 1D data
        * :code:`node` - returns all nodes/units regardless of whether they contain results. The full ID is also
          returned in case there are duplicate names. Only applicable if a :code:`DAT` or :code:`GXY` file is provided.
        * :code:`channel` - returns all channel IDs. Channel IDs are not returned by when using :code:`None` as
          they don't contain any result data. Only applicable if a :code:`DAT` or :code:`GXY` file is provided.
        * :code:`timeseries`: returns only IDs that have time series data.
        * :code:`section`: returns only IDs that have section data (i.e. long plot data).
        * :code:`[data_type]`: returns only IDs for the given data type. Shorthand data type names can be used.

        Parameters
        ----------
        context : str, optional
            The context to filter the IDs by.

        Returns
        -------
        list[str]
            The available IDs.

        Examples
        --------
        >>> res.ids()
        ['FC01.36', 'FC01.35', 'FC01.351cu',... 'FC02', 'ds2_S', 'FC01']
        >>> res.ids('node')
        ['QTBDY__FC01', 'JUNCTION_OPEN_FC01', 'RIVER_SECTION_FC01.40',... 'JUNCTION_OPEN_ds2', 'SPILL__ds2_S']
        """
        if context and context.lower() == 'channel':
            return self.channel_info.index.tolist()
        if context and context.lower() == 'node':
            return self.node_info.index.tolist()
        return super().ids(context)

    def maximum(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a DataFrame containing the maximum values for the given data types. The returned DataFrame
        will include time of maximum results as well.

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can also be a contextual string, e.g. :code:`channel` to extract the maximum values for all
        channels. The following contexts are available for this class:

        * :code:`None`: returns all maximum values
        * :code:`1d`: returns all maximum values (same as passing in None for locations)
        * :code:`node`

        The returned DataFrame will have an index column corresponding to the location IDs, and the columns
        will be in the format :code:`context/data_type/[max|tmax]`,
        e.g. :code:`node/flow/max`, :code:`node/flow/tmax`

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
             node/flow/max  node/flow/tmax
        ds2       22.05114        1.583333

        Extracting all the maximum results for a given channel:

        >>> res.maximum(['ds1'], None)
             node/flow/max  node/flow/tmax  ...  node/state/max  node/state/tmax
        ds2       22.05114        1.583333  ...             0.0              0.0

        Extracting the maximum flow for all channels:

        >>> res.maximum(None, 'flow')
                    node/flow/max  node/flow/tmax
        FC01.36          0.840000        0.000000
        FC01.35         10.011658        0.333333
        FC01.351cu       3.337249        0.333333
        FC01.351cd       3.337087        0.333333
        FC01.351co       3.337087        0.333333
        ...                   ...             ...
        FC01.2_Rd5       4.428591        1.500000
        FC01.2_Ro5       4.428591        1.500000
        FC02             0.080000        0.000000
        ds2_S           22.051140        1.583333
        FC01             0.920000        0.000000
        """
        return super().maximum(locations, data_types, time_fmt)

    def time_series(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                    time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a time-series DataFrame for the given location(s) and data type(s).

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can also be a contextual string, e.g. :code:`channel` to extract the time-series values for all
        channels. The following contexts are available for this class:

        * :code:`None`: returns all locations
        * :code:`1d`: returns all locations (same as passing in None for locations)
        * :code:`node`

        The returned column names will be in the format :code:`context/data_type/location`
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

        >>> res.time_series('ds2', 'q')
        time      node/q/ds1
        0.000000    0.920000
        0.083333    0.910979
        0.166667    0.886582
        0.250000    0.929299
        ...              ...
        2.666667   14.194231
        2.750000   13.511795
        2.833333   12.955027
        2.916667   12.494930
        3.000000   12.135681

        Extracting all data types for a given location

        >>> res.time_series('ds1', None)
                  node/flow/ds1  node/water level/ds1  ...  node/mode/ds1  node/state/ds1
        time                                           ...
        0.000000       0.920000             36.493000  ...            0.0             0.0
        0.083333       0.910979             36.525406  ...            0.0             0.0
        0.166667       0.886582             36.516323  ...            0.0             0.0
        0.250000       0.929299             36.524315  ...            0.0             0.0
        0.333333       2.275538             36.745884  ...            0.0             0.0
        ...                 ...                   ...  ...            ...             ...
        2.666667      14.194231             37.933880  ...            0.0             0.0
        2.750000      13.511795             37.898212  ...            0.0             0.0
        2.833333      12.955027             37.869987  ...            0.0             0.0
        2.916667      12.494930             37.848312  ...            0.0             0.0
        3.000000      12.135681             37.833549  ...            0.0             0.0

        Extracting all flow results

        >>> res.time_series(None, 'flow')
        time      node/flow/FC01.36  node/flow/FC01.35  ...  node/flow/ds2_S  node/flow/FC01
        0.000000               0.84           0.840000  ...         0.920000            0.92
        0.083333               0.00           5.730267  ...         0.917122            0.00
        0.166667               0.00           9.591267  ...         0.890924            0.00
        0.250000               0.00           9.981448  ...         0.904744            0.00
        0.333333               0.00          10.011658  ...         1.959577            0.00
        ...                     ...                ...  ...              ...             ...
        2.666667               0.00          10.006260  ...        14.305518            0.00
        2.750000               0.00          10.006241  ...        13.612213            0.00
        2.833333               0.00          10.006139  ...        13.029665            0.00
        2.916667               0.00          10.006124  ...        12.559101            0.00
        3.000000               0.00          10.006373  ...        12.182993            0.00
        """
        return super().time_series(locations, data_types, time_fmt)

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Returns a long plot for the given location and data types at the given time. If one location is given,
        the long plot will connect the given location down to the outlet. If 2 locations are given, then the
        long plot will connect the two locations (they must be connectable).

        The locations should correspond to node names (not the full ID). The first location should be upstream
        of the second location as the function will assume the first node is the most upstream point and the second
        node is the most downstream point and accordingly (if the nodes are the other way round then the start and
        end channels will not be exactly correct).

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
        if not self._support_section_plotting:
            raise ResultError('A DAT or GXY file is required for section plotting')

        locations = [locations] if not isinstance(locations, list) else locations

        # convert ids to uids
        locs = [self.id_to_uid(x) for x in locations]
        for i, x in enumerate(reversed(locs)):
            j = len(locations) - 1
            if x is None:
                logger.warning(f'FMTS.section(): Could not find a valid UID for {locations[j]}')
                locs.pop(i)
        if not locs:
            raise ValueError('No valid locations provided.')

        # get locations and data types
        locs, data_types = self._figure_out_loc_and_data_types_lp(locs, data_types, 'node')

        # get the time index
        times = self.times(fmt='absolute') if isinstance(time, datetime) else self.times()
        timeidx = closest_time_index(times, time)

        # get connectivity
        dfconn = self.connectivity(locs)

        # init long plot DataFrame
        df = self._lp.init_lp(dfconn)
        df['node'] = df['node'].str.split('_', n=2).str[-1]

        # loop through data types and add them to the data frame
        for dtype in data_types:
            dtype1 = get_standard_data_type_name(dtype)

            if dtype1 == 'bed level':
                df1 = self._lp.melt_2_columns(dfconn, ['us_invert', 'ds_invert'], dtype)
                df[dtype] = df1[dtype]
            elif dtype1 == 'pipes':
                df1 = self._lp.melt_2_columns(dfconn, ['lbus_obvert', 'lbds_obvert'], dtype)
                df1 = df1.join(self.channel_info['ispipe'], on='channel')
                df1.loc[~df1['ispipe'], dtype] = np.nan
                df[dtype] = df1[dtype]
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
        """Not supported for FMTS results. Raises a :code:`NotImplementedError`.

        See Also
        --------
        :meth:`has_plotting_capability` : Check if a given output class supports a given plotting capability before
           trying to use it.
        """
        return super().curtain(locations, data_types, time)

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for FMTS results. Raises a :code:`NotImplementedError`.

        See Also
        --------
        :meth:`has_plotting_capability` : Check if a given output class supports a given plotting capability before
           trying to use it.
        """
        return super().profile(locations, data_types, time)

    def connectivity(self, ids: Union[str, list[str]]) -> pd.DataFrame:
        # docstring inherited
        lp = LP1D_FM(ids, self.node_info, self.channel_info)
        if self._lp is not None and lp == self._lp:
            return self._lp.df

        lp.connectivity()
        self._lp = lp
        return self._lp.df

    def id_to_uid(self, id_: str) -> str:
        """Converts a unit ID to its UID. Only searches through units that
        contain results. If multiple units are found, it will first preference units that have bed level information
        (requires that the class was initialised with a DAT file) as this will preference units such as
        rivers, conduits, structures etc. over units such as junctions. If multiple are still found, the first instance
        is returned. If no unit is found, :code:`None` is returned

        Parameters
        ----------
        id\_: str
            The unit ID to convert.

        Returns
        -------
        str:
            The uid of the unit.
        """
        # check if id is already a uid
        if id_.lower() in self.node_info.index.str.lower():
            return id_
        df = self.node_info[self.node_info['has_results']].copy()
        df['id2'] = df.index.str.split('_', n=2).str[-1].str.lower()
        df = df[df['id2'] == id_.lower()]
        if df.empty:
            return None
        # if multiple are returned, a unit with a bed elevation is less likely to be a junction
        df1 = df[~np.isnan(df['bed_level'])]
        if df1.empty:
            return df.index[0]
        return df1.index[0]

    def _init_tpc_reader(self) -> TPCReader:
        pass

    def _load(self) -> None:
        # initialise the storage/drivers for each result file
        ids, res_types = None, None
        for fpath in self._fpaths:
            driver = FM_ResultDriver(fpath)
            if driver.driver_name == 'zzn' and len(self._fpaths) > 1:
                raise ResultError('Cannot load multiple results and one of them is a ZZN file')

            if ids is None:
                ids = driver.ids
            else:
                if ids != driver.ids:
                    raise ResultError('Result IDs do not match')

            if res_types is None:
                res_types = driver.result_types
            else:
                if np.intersect1d(res_types, driver.result_types).size:
                    raise ResultError('Duplicate result types found in the result files')

            self.storage.append(driver)

        self.name = self.storage[0].display_name
        for driver in self.storage:
            driver.reference_time = self.reference_time

        # Initialise DAT
        if self.dat_fpath is not None:
            self.dat = DAT(self.dat_fpath)
            self._support_section_plotting = True

        # Initialise GXY
        if self.gxy_fpath is not None:
            self.gxy = GXY(self.gxy_fpath)
            self._support_section_plotting = True

        # load time series
        for driver in self.storage:
            for res_type in driver.result_types:
                stnd = get_standard_data_type_name(res_type)
                self._nd_res_types.append(stnd)  # all results are stored on nodes in flood modeller results
                df = driver.df.loc[:,driver.df.columns.str.contains(f'^{res_type}::')]
                df.columns = [x.split('::')[1] for x in df.columns]
                self._time_series_data[stnd] = df

        # load max data
        self._load_maximums()

        # load node/channel information
        self._load_nodes()
        self._load_channels()
        self._load_1d_info()

        self.node_count = self.node_info.shape[0]
        self.channel_count = self.channel_info.shape[0]

    def _load_nodes(self):
        """Loads FM Nodes into node_info pd.DataFrame."""
        d = {'id': [], 'bed_level': [], 'top_level': [], 'nchannel': [], 'channels': [], 'type': [], 'has_results': [],
             'name': []}
        if self.dat:
            for unit in self.dat.units:
                d['id'].append(unit.uid)
                d['bed_level'].append(unit.bed_level)
                d['top_level'].append(np.nan)
                d['nchannel'].append(len(unit.ups_units) + len(unit.dns_units))
                if d['nchannel'][-1] == 1:
                    d['channels'].append(str(unit.ups_link_ids[0]) if unit.ups_link_ids else str(unit.dns_link_ids[0]))
                else:
                    d['channels'].append([str(x) for x in unit.ups_link_ids] + [str(x) for x in unit.dns_link_ids])
                d['type'].append(f'{unit.type}_{unit.sub_type}')
                d['has_results'].append(unit.id in self.storage[0].ids)
                d['name'].append(unit.id)
        elif self.gxy:
            for unit in self.gxy._nodes:
                d['id'].append(unit.uid)
                d['bed_level'].append(np.nan)
                d['top_level'].append(np.nan)
                ups_links = self.gxy.link_df[self.gxy.link_df['dns_node'] == unit.uid]
                dns_links = self.gxy.link_df[self.gxy.link_df['ups_node'] == unit.uid]
                d['nchannel'].append(len(ups_links) + len(dns_links))
                if d['nchannel'][-1] == 1:
                    d['channels'].append(str(ups_links.index.tolist()[0]) if not ups_links.empty else str(dns_links.index.tolist()[0]))
                else:
                    d['channels'].append([str(x) for x in ups_links.index.tolist()] + [str(x) for x in dns_links.index.tolist()])
                d['type'].append(unit.type)
                d['has_results'].append(unit.id in self.storage[0].ids)
                d['name'].append(unit.id)
        else:
            d['id'] = self.storage[0].ids
            d['bed_level'] = [np.nan for _ in d['id']]
            d['top_level'] = [np.nan for _ in d['id']]
            d['nchannel'] = [0 for _ in d['id']]
            d['channels'] = [[] for _ in d['id']]
            d['type'] = ['' for _ in d['id']]
            d['has_results'] = True
            d['name'] = d['id']

        self.node_info = pd.DataFrame(d)
        self.node_info.set_index('id', inplace=True)

    def _load_channels(self):
        """LoadsFM Channels into channel_info pd.DataFrame."""
        d = {'id': [], 'us_node': [], 'ds_node': [], 'us_chan': [], 'ds_chan': [], 'ispipe': [], 'length': [],
                'us_invert': [], 'ds_invert': [], 'lbus_obvert': [], 'rbus_obvert': [], 'lbds_obvert': [],
                'rbds_obvert': []}
        if self.dat:
            for link in self.dat.links:
                d['id'].append(str(link.id))
                if link.ups_unit:
                    d['us_node'].append(link.ups_unit.uid)
                    if link.ups_unit.ups_link_ids:
                        d['us_chan'].append(str(link.ups_unit.ups_link_ids[0]))
                    else:
                        d['us_chan'].append('')
                else:
                    d['us_node'].append('')
                if link.dns_unit:
                    d['ds_node'].append(link.dns_unit.uid)
                    if link.dns_unit.dns_link_ids:
                        d['ds_chan'].append(str(link.dns_unit.dns_link_ids[0]))
                    else:
                        d['ds_chan'].append('')
                us_obv = np.nan
                ds_obv = np.nan
                if link.ups_unit.unit_type_name() == 'CONDUIT' and link.ups_unit.dx > 0:
                    d['ispipe'].append(True)
                    if link.ups_unit.sub_type.upper() == 'CIRCULAR':
                        us_obv = link.ups_unit.bed_level + link.ups_unit.dia
                        ds_obv = link.dns_unit.bed_level + link.dns_unit.dia
                    elif link.ups_unit.sub_type.upper() == 'RECTANGULAR':
                        us_obv = link.ups_unit.bed_level + link.ups_unit.height
                        ds_obv = link.dns_unit.bed_level + link.dns_unit.height
                    elif link.ups_unit.sub_type.upper() in ['ASYMMETRIC', 'SECTION']:
                        us_obv = link.ups_unit.bed_level + link.ups_unit.section.y.max()
                        ds_obv = link.dns_unit.bed_level + link.dns_unit.section.y.max()
                    elif link.ups_unit.sub_type.upper() in ['FULL', 'FULLARCH']:
                        us_obv = link.ups_unit.bed_level + link.ups_unit.archyt
                        ds_obv = link.dns_unit.bed_level + link.dns_unit.archyt
                    elif link.ups_unit.sub_type.upper() in ['SPRUNG', 'SPRUNGARCH']:
                        us_obv = link.ups_unit.bed_level + link.ups_unit.sprhyt + link.ups_unit.archyt
                        ds_obv = link.dns_unit.bed_level + link.dns_unit.sprhyt + link.dns_unit.archyt
                else:
                    d['ispipe'].append(False)
                length = 0.
                if hasattr(link.ups_unit, 'dx') and not np.isnan(link.ups_unit.dx):
                    length = link.ups_unit.dx
                d['length'].append(length)
                d['us_invert'].append(link.ups_unit.bed_level)
                d['ds_invert'].append(link.dns_unit.bed_level)
                d['lbus_obvert'].append(us_obv)
                d['rbus_obvert'].append(us_obv)
                d['lbds_obvert'].append(ds_obv)
                d['rbds_obvert'].append(ds_obv)
        elif self.gxy:
            for index, row in self.gxy.link_df.iterrows():
                d['id'].append(str(index))
                d['us_node'].append(row['ups_node'])
                d['ds_node'].append(row['dns_node'])
                ups_links = self.gxy.link_df[self.gxy.link_df['dns_node'] == row['ups_node']]
                if not ups_links.empty:
                    d['us_chan'].append(str(ups_links.index.tolist()[0]))
                else:
                    d['us_chan'].append('')
                dns_links = self.gxy.link_df[self.gxy.link_df['ups_node'] == row['dns_node']]
                if not dns_links.empty:
                    d['ds_chan'].append(str(dns_links.index.tolist()[0]))
                else:
                    d['ds_chan'].append('')
                d['ispipe'].append(False)
                d['length'].append(0.)
                d['us_invert'].append(np.nan)
                d['ds_invert'].append(np.nan)
                d['lbus_obvert'].append(np.nan)
                d['rbus_obvert'].append(np.nan)
                d['lbds_obvert'].append(np.nan)
                d['rbds_obvert'].append(np.nan)

        self.channel_info = pd.DataFrame(d)
        self.channel_info.set_index('id', inplace=True)
