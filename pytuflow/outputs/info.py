import logging
import re
from datetime import timedelta, datetime
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from pytuflow.outputs.helpers.tpc_reader import TPCReader
from pytuflow.outputs.itime_series_1d import ITimeSeries1D
from pytuflow.outputs.time_series import TimeSeries
from pytuflow.pytuflow_types import PathLike, TimeLike, AppendDict, CaseInsDict
from pytuflow.util import flatten
from pytuflow.util.logging import get_logger
from pytuflow.util.time_util import closest_time_index

logger = get_logger()


class INFO(TimeSeries, ITimeSeries1D):
    """Class for reading TUFLOW info time series results (.info). These are text files with a '.info' extension
    (not '.2dm.info') that are output by the 2013 TUFLOW release. The format is similar to the TPC format, however
    does not include 2D or RL results.

    This class does not need to be explicitly closed as it will load the results into memory and closes any open files
    after initialisation.

    Examples
    --------
    >>> from pytuflow.outputs import INFO
    >>> info = INFO('path/to/file.info')
    """

    PLOTTING_CAPABILITY = ['timeseries', 'section']
    ALTERNATE_DATA_TYPE_NAMES = CaseInsDict({
        'Water Levels': ['water level', 'water levels', 'water_level', 'water_levels', 'h', 'stage', 'level', 'levels'],
        'Flows': ['flow', 'flows', 'q'],
        'Velocities': ['velocity', 'velocities', 'vel', 'v'],
        'Water Levels Max': ['water level max', 'water_level_max', 'water level maximum', 'water_level_maximum',
                             'water levels max', 'water_levels_max', 'maxh', 'maximumh',
                            'max water level', 'max_water_level', 'max water levels', 'max_water_levels', 'max h',
                            'max_h', 'max stage', 'max_stage', 'max level', 'max_level', 'max levels', 'max levels'],
        'Water Levels TMax': ['water level tmax', 'water_level_tmax', 'water level tmaximum', 'water_level_tmaximum',
                              'water levels tmax', 'water_levels_tmax', 'tmaxh', 'tmaximumh',
                              'tmax water level', 'tmax_water_level', 'tmax water levels', 'tmax_water_levels', 'tmax h',
                              'tmax_h', 'tmax stage', 'tmax_stage', 'tmax level', 'tmax_level', 'tmax levels',
                              'tmax levels', 'time of max h', 'time_of_max_h', 'time of max level', 'time_of_max_level',
                              'time of max water level', 'time_of_max_water_level', 'time of max stage',
                              'time_of_max_stage'],
        'Bed Level': ['bed level', 'bed levels', 'bed_level', 'bed_levels', 'bed', 'bathymetry', 'bathy', 'z',
                      'ground level', 'ground_level', 'ground levels', 'ground_levels'],
        'Pipes': ['pipes', 'pipe', 'culverts', 'culvert', 'culverts and pipes', 'culverts_and_pipes'],
        'Pits': ['pits', 'pit', 'pit level', 'pit_level', 'pit levels', 'pit_levels']
    })

    def __init__(self, fpath: PathLike) -> None:
        """
        Parameters
        ----------
        fpath : PathLike
            The path to the 1D time-series .info output file.
        """
        super(INFO, self).__init__(fpath)

        #: Path: The path to the 1D time-series .info output file.
        self.fpath = Path(fpath)

        # call before tpc_reader is initialised to give a clear error message if it isn't actually a .info time series file
        if not self.looks_like_this(fpath):
            raise ValueError(f'File does not look like a time series .info file: {fpath}')

        #: :doc:`TPCReader<pytuflow.outputs.helpers.tpc_reader.TPCReader>`: The TPC reader for the .info file. The INFO file format uses the TPC format.
        self.tpc_reader = TPCReader(self.fpath)

        # call after tpc_reader has been initialised so that we know the file can be loaded by the reader
        if self.looks_empty(fpath):
            raise ValueError(f'File is empty or incomplete: {fpath}')

        # private properties
        self._time_series_data = AppendDict()
        self._maximum_data = AppendDict()

        self.load()

    def load(self) -> None:
        # docstring inherited
        self.name = self.tpc_reader.get_property('Simulation ID')
        self.node_count = self.tpc_reader.get_property('Number Nodes')
        self.channel_count = self.tpc_reader.get_property('Number Channels')
        self._load_node_info()
        self._load_chan_info()
        self._load_time_series()
        self._load_maximums()

    def close(self):
        # docstring inherited
        pass  # no files are left open

    @staticmethod
    def looks_like_this(fpath: PathLike) -> bool:
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
    def looks_empty(fpath: PathLike) -> bool:
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

    def times(self, context: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns all the available times for the output.

        The context is an optional input that can be used to filter the return further. For INFO results, the
        returned times will be the same regardless of the context, so it is not recommended to pass in any
        context. Valid contexts for INFO results are:
        - '1d': returns all data types
        - 'node': returns only node data types
        - 'channel': returns only channel data types
        - 'timeseries': returns only IDs that have time series data. This will be all IDs for INFO results.
        - 'section': returns only IDs that have section data (i.e. long plot data). This is identical to 'nodes'
        for INFO results
        - [id]: returns only data types for the given ID.
        - [data_type]: returns only IDs for the given data type.

        Parameters
        ----------
        context : str, optional
            The context to filter the times by.
        fmt : str, optional
            The format for the times. Options are 'relative' or 'absolute'.

        Returns
        -------
        list[TimeLike]
            The available times in the requested format.

        Examples
        --------
        >>> res.times()
        [0.0, 0.016666666666666666, ..., 3.0]
        >>> res.times('absolute')
        [Timestamp('2021-01-01 00:00:00'), Timestamp('2021-01-01 00:01:00'), ..., Timestamp('2021-01-01 03:00:00')]
        """
        # validate context
        if context:
            data_types = flatten([self._data_type_to_alternate_name(x) for x in self.data_types()])
            possible_contexts = ['1d', 'node', 'channel', 'timeseries', 'section'] + self.ids() + data_types
            if context.lower() not in possible_contexts:
                raise ValueError(f'Invalid context: {context}')
        # all times are the same so context doesn't actually matter
        times = []
        for data_type, results in self._time_series_data.items():
            for res_df in results:
                times = res_df.index.tolist()
                break

        if fmt in ['absolute', 'datetime']:
            times = [self.reference_time + timedelta(hours=x) for x in times]

        return times

    def data_types(self, context: str = None) -> list[str]:
        """Returns all the available data types (result types) for the output given the context.

        The context is an optional input that can be used to filter the return further. Available
        context objects for the INFO result class are:
        - '1d': returns all data types
        - 'node': returns only node data types
        - 'channel': returns only channel data types
        - 'timeseries': returns only IDs that have time series data. This will be all IDs for INFO results.
        - 'section': returns only IDs that have section data (i.e. long plot data).
        - [id]: returns only data types for the given ID.

        Parameters
        ----------
        context : str, optional
            The context to filter the data types by.

        Returns
        -------
        list[str]
            The available data types.

        Examples
        --------
        The below examples demonstrate how to use the context argument to filter the returned data types. The first
        example returns all data types, the second returns only node data types, the third returns only channel data
        types, and the fourth returns only data types for the channel 'FC01.1_R' which is the same as using
        the 'channels' context for INFO results.

        >>> res.data_types()
        ['Water Level', 'Flow', 'Velocity']
        >>> res.data_types('node')
        ['Water Level']
        >>> res.data_types('channel')
        ['Flow', 'Velocity']
        >>> res.data_types('FC01.1_R')
        ['Flow', 'Velocity']
        """
        # validate context
        if context:
            possible_contexts = ['node', 'channel', '1d', 'section', 'timeseries'] + self.ids()
            if context.lower() not in possible_contexts:
                raise ValueError(f'Invalid context: {context}')

        if not context or context.lower() in ['1d', 'timeseries']:
            return ['Water Level', 'Flow', 'Velocity']

        if context.lower() == 'section':
            return ['Water Level', 'Water Level Max', 'Water Level TMax', 'Bed Level', 'Pits', 'Pipes']

        # if context is not node or channel, figure out which one it is
        if context.lower() not in ['node', 'channel']:
            if context.lower() == 'section':
                context = 'node'
            elif context.lower() in self.node_info.index.str.lower():
                context = 'node'
            else:
                context = 'channel'

        if context.lower() == 'node':
            return ['Water Level']

        return ['Flow', 'Velocity']

    def ids(self, context: str = None) -> list[str]:
        """Returns all the available IDs for the output.

        The context argument can be used to add a filter to the returned IDs. Available context objects for the INFO
        result class are:
        - '1d': returns all IDs
        - 'node': returns only node IDs
        - 'channel': returns only channel IDs
        - 'timeseries': returns only IDs that have time series data. This will be all IDs for INFO results.
        - 'section': returns only IDs that have section data (i.e. long plot data). This is identical to 'nodes'
        for INFO results
        - [data_type]: returns only IDs for the given data type.

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
        The below examples demonstrate how to use the context argument to filter the returned IDs. The first example
        returns all IDs, the second returns only node IDs, the third returns only channel IDs, and the fourth returns
        only water level IDs which is the same as using the 'nodes' context for INFO results.

        >>> res.ids()
        ['FC01.1_R', 'FC01.2_R', 'FC04.1_C', 'FC01.1_R.1', 'FC01.1_R.2', 'FC01.2_R.1', 'FC01.2_R.2', 'FC04.1_C.1', 'FC04.1_C.2']
        >>> res.ids('node')
        ['FC01.1_R.1', 'FC01.1_R.2', 'FC01.2_R.1', 'FC01.2_R.2', 'FC04.1_C.1', 'FC04.1_C.2']
        >>> res.ids('channel')
        ['FC01.1_R', 'FC01.2_R', 'FC04.1_C']
        >>> rse.ids('h')
        ['FC01.1_R.1', 'FC01.1_R.2', 'FC01.2_R.1', 'FC01.2_R.2', 'FC04.1_C.1', 'FC04.1_C.2']
        """
        # validate context argument
        if context:
            data_types = flatten([self._data_type_to_alternate_name(x) for x in self.data_types()])
            possible_contexts = ['node', 'channel', '1d', 'section', 'timeseries'] + data_types
            if context.lower() not in possible_contexts:
                raise ValueError(f'Invalid context: {context}')

        if not context or context.lower() in ['1d', 'timeseries']:
            return self.chan_info.index.tolist() + self.node_info.index.tolist()

        # if context is not node or channel, figure out which one it is
        if context.lower() not in ['node', 'channel']:
            if context.lower() == 'section':
                context = 'node'
            elif context.lower() in self.ALTERNATE_DATA_TYPE_NAMES['water levels']:
                context = 'node'
            else:
                context = 'channel'

        if context.lower() == 'node':
            return self.node_info.index.tolist()

        return self.chan_info.index.tolist()

    def maximum(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time_fmt: str = 'relative') -> pd.DataFrame:
        # docstring inherited
        locations, data_types = self._figure_out_loc_and_data_types(locations, data_types)

        locations_lower = [x.lower() for x in locations]
        df = pd.DataFrame()
        for dtype in data_types:
            dtype1 = self._alternate_name_to_data_type(dtype)  # get the correct data_type name
            if dtype1 not in self._time_series_data:
                continue
            for res_df in self._maximum_data[dtype1]:
                idxs = [res_df.index.str.lower().get_loc(x) for x in locations_lower if x in res_df.index.str.lower()]
                if not idxs:
                    continue
                rows = res_df.index[idxs]
                df1 = res_df.loc[rows]
                if time_fmt == 'absolute':
                    df1['tmax'] = df1['tmax'].apply(lambda x: self.reference_time + timedelta(hours=x))
                ctx = 'node' if dtype1 == 'Water Levels' else 'channel'
                df1.columns = [f'{ctx}/{dtype}/{x}' for x in df1.columns]
                if df.empty:
                    df = df1
                else:
                    df = pd.concat([df, df1], axis=1)

        return df

    def time_series(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                    time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a time series dataframe for the given location(s) and data type(s). INFO result types will
        always share a common time index.

        It's possible to pass in a well known short-hand for the data type e.g. 'q' for flow.

        The returned column names will be in the format 'context/data_type/location' e.g. 'channel/flow/FC01.1_R'.
        The data_type name in the column heading will be identical to the data type name passed into the
        function e.g. if 'h' is used instead of 'water level', then the return will be 'node/h/FC01.1_R.1'.

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
        locations, data_types = self._figure_out_loc_and_data_types(locations, data_types)

        # note INFO has no need to worry about multiple index columns
        locations_lower = [x.lower() for x in locations]
        df = pd.DataFrame()
        for dtype in data_types:
            dtype1 = self._alternate_name_to_data_type(dtype)  # get the correct data_type name
            if dtype1 not in self._time_series_data:
                continue
            for res_df in self._time_series_data[dtype1]:
                idxs = [res_df.columns.str.lower().get_loc(x) for x in locations_lower if x in res_df.columns.str.lower()]
                if not idxs:
                    continue
                cols = res_df.columns[idxs]
                df1 = res_df.loc[:, cols]
                ctx = 'node' if dtype1 == 'Water Levels' else 'channel'
                df1.columns = [f'{ctx}/{dtype}/{x}' for x in df1.columns]
                if df.empty:
                    df = df1
                else:
                    df = pd.concat([df, df1], axis=1)

        if time_fmt in ['absolute', 'datetime']:
            df = df.reindex(self.times(fmt='absolute'))

        return df

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Returns a long plot for the given location and data types at the given time. If one location is given,
        the the long plot will connect the given location down to the outlet. If 2 locations are given, then the
        long plot will connect the two locations (they must be connectable). If more than 2 locations are given,
        multiple long plot will be produced, however one channel must be a common downstream location and the other
        channels must be upstream of this location.

        The order the locations are contained in the `location` parameter does not matter as both directions are
        checked, however it will be faster to include the upstream location first as this will be the first connection
        checked.

        The returned DataFrame will have the following columns:
        - 'branch_id': The branch ID. If more than 2 pipes are provided, or the channels diverge at an intersection,
        then multiple branches will be returned. The same channel could be in multiple branches. The branch id
        starts at zero for the first branch, and increments by one for each additional branch.
        - 'channel': The channel ID.
        - 'node': The node ID.
        - 'offset': The offset along the long plot
        - [data_types]: The data types requested.

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

        Examples
        --------
        Extracting a long plot from a given channel ("ds1") to the outlet at 1.0 hours:

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

        Extracting a long plot between "ds1" and "ds4" at 1.0 hours:

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
        # get locations and data types
        locations, data_types = self._figure_out_loc_and_data_types_lp(locations, data_types)

        # get the time index
        times = self.times(fmt='absolute') if isinstance(time, datetime) else self.times()
        timeidx = closest_time_index(times, time)

        # get connectivity
        dfconn = self.connectivity(locations)

        # init long plot DataFrame
        df = self.lp.init_lp(dfconn)

        # loop through data types and add them to the data frame
        for dtype in data_types:
            dtype1 = self._alternate_name_to_data_type(dtype)

            if dtype1 == 'Bed Level':
                df1 = self.lp.melt_2_columns(dfconn, ['us_invert', 'ds_invert'], dtype)
                df[dtype] = df1[dtype]
            elif dtype1 == 'Pipes':
                df1 = self.lp.melt_2_columns(dfconn, ['lbus_obvert', 'lbds_obvert'], dtype)
                df1 = df1.join(self.chan_info['ispipe'], on='channel')
                df1.loc[~df1['ispipe'], dtype] = np.nan
                df[dtype] = df1[dtype]
            elif dtype1 == 'Pits':
                y = []
                for i, row in dfconn.iterrows():
                    nd = row['us_node']
                    pits = self.chan_info[(self.chan_info['ds_node'] == nd) & (self.chan_info['us_channel'] == '------')
                                          & (self.chan_info['ds_channel'] == '------')].index.tolist()
                    if pits:
                        y.append(self.chan_info.loc[pits[0], 'lbus_obvert'])
                    else:
                        y.append(np.nan)
                    if i + 1 == dfconn.shape[0]:
                        nd = row['ds_node']
                        pits = self.chan_info[(self.chan_info['us_node'] == nd) & (self.chan_info['us_channel'] == '------')
                                              & (self.chan_info['ds_channel'] == '------')].index.tolist()
                        if pits:
                            y.append(self.chan_info.loc[pits[0], 'lbus_obvert'])
                        else:
                            y.append(np.nan)
                    else:
                        y.append(np.nan)
                df[dtype] = y
            elif 'TMax' in dtype1:
                dtype1 = dtype1.replace('TMax', '').strip()
                df[dtype] = self._maximum_data[dtype1][0].loc[df['node'], 'tmax'].tolist()
            elif 'Max' in dtype1:
                dtype1 = dtype1.replace('Max', '').strip()
                df[dtype] = self._maximum_data[dtype1][0].loc[df['node'], 'max'].tolist()
            else:  # temporal result
                idx = self._time_series_data[dtype1][0].index[timeidx]
                df[dtype] = self._time_series_data[dtype1][0].loc[idx, df['node']].tolist()

        return df

    def curtain(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Returns a dataframe containing curtain plot data for the given location and data type.

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the curtain data for.
        data_types : str | list[str]
            The data type to extract the curtain data for.
        time : TimeLike
            The time to extract the curtain data for.

        Returns
        -------
        pd.DataFrame
            The curtain data.
        """
        raise NotImplementedError('.INFO files do not support curtain plotting.')

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Returns a dataframe containing vertical profile data for the given location and data type.

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the profile data for.
        data_types : str | list[str]
            The data type to extract the profile data for.
        time : TimeLike
            The time to extract the profile data for.

        Returns
        -------
        pd.DataFrame
            The profile data.
        """
        raise NotImplementedError('.INFO files do not support vertical profile plotting.')

    def _info_name_correction(self, name: str) -> str:
        """Correct the name of the file. Only required for INFO results and should be overerriden by subclasses."""
        return name.replace('_1d_','_1d_1d_')

    def _expand_property_path(self, prop: str) -> Path:
        """Expands the property value into a full path. Returns None if the property does not exist."""
        prop_path = self.tpc_reader.get_property(prop, None)
        if prop_path is not None:
            if prop in ['Channel Info', 'Node Info']:
                prop_path = self._info_name_correction(prop_path)
            return self.fpath.parent / prop_path

    def _load_node_info(self) -> None:
        """Load node info DataFrame."""
        node_info_csv = self._expand_property_path('Node Info')
        if node_info_csv is not None:
            try:
                self.node_info = pd.read_csv(
                    node_info_csv,
                    engine='python',
                    index_col='id',
                    names=['no', 'id', 'bed_level', 'top_level', 'nchannel', 'channels'],
                    header=None,
                    on_bad_lines=lambda x: x[:5] + [tuple(x[5:])],
                )
                self.node_info.drop('no', axis=1, inplace=True)
                self.node_info.drop('Node', axis=0, inplace=True)
                self.node_info.replace({'bed_level': '**********'}, np.nan, inplace=True)
                self.node_info.replace({'top_level': '**********'}, np.nan, inplace=True)
                self.node_info['bed_level'] = self.node_info['bed_level'].astype(float)
                self.node_info['top_level'] = self.node_info['bed_level'].astype(float)
                self.node_info['nchannel'] = self.node_info['nchannel'].astype(int)
            except Exception as e:
                logger.warning(f'INFO._load_node_info(): Error loading node info: {e}')

    def _load_chan_info(self) -> None:
        """Load channel info DataFrame."""
        chan_info_csv = self._expand_property_path('Channel Info')
        if chan_info_csv is not None:
            try:
                self.chan_info = pd.read_csv(
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
                self.chan_info.drop('no', axis=1, inplace=True)
                self.chan_info['ispipe'] = self.chan_info['flags'].str.match(r'.*[CR].*', False)
            except Exception as e:
                logger.warning(f'INFO._load_chan_info(): Error loading channel info: {e}')

    def _load_time_series(self) -> None:
        """Load time-series data into memory."""
        for res in ['Water Levels', 'Flows', 'Velocities']:
            p = self._expand_property_path(res)
            if p is not None:
                try:
                    df = self._load_time_series_csv(p)
                    self._time_series_data[res] = df
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

    def _data_type_to_alternate_name(self, name: str) -> list[str]:
        """Returns alternate names for the given data type."""
        name = self._alternate_name_to_data_type(name)
        return self.ALTERNATE_DATA_TYPE_NAMES.get(name, name)

    def _alternate_name_to_data_type(self, data_type: str) -> str:
        """Returns the correct data type name to use from a given alternate name for the data type."""
        for key, value in self.ALTERNATE_DATA_TYPE_NAMES.items():
            if data_type.lower() in value:
                return key
        return data_type

    def _figure_out_loc_and_data_types(self, locations: Union[str, list[str], None],
                                       data_types: Union[str, list[str], None]) -> tuple[list[str], list[str]]:
        """Figure out the locations and data types to use."""
        if locations and not isinstance(locations, list):
            locations = [locations]
        if data_types and not isinstance(data_types, list):
            data_types = [data_types]

        if not locations and not data_types:
            locations = self.ids()
            data_types = self.data_types()
        if not locations:
            ctx = []
            for x in ['node', 'channel']:
                for y in data_types:
                    if self._alternate_name_to_data_type(y) in [self._alternate_name_to_data_type(z) for z in
                                                                self.data_types(x)]:
                        ctx.append(x)
            if not ctx:
                locations = []
            elif len(ctx) > 1:
                locations = self.ids()
            else:
                locations = self.ids(ctx[0])
        if not data_types:
            ctx = [x for x in ['node', 'channel'] for y in locations if y in self.ids(x)]
            if not ctx:
                data_types = []
            elif len(ctx) > 1:
                data_types = self.data_types()
            else:
                data_types = self.data_types(ctx[0])

        return locations, data_types

    def _figure_out_loc_and_data_types_lp(self, locations: Union[str, list[str]],
                                          data_types: Union[str, list[str], None]) -> tuple[list[str], list[str]]:
        """Figure out the locations and data types to use - long profile edition."""
        # sort out locations and data types
        if not locations:
            raise ValueError('No locations provided.')
        else:
            valid_loc = self.ids('channel')
            valid_loc_lower = [x.lower() for x in valid_loc]
            locations1 = []
            locations = [locations] if not isinstance(locations, list) else locations
            for loc in locations:
                if loc.lower() not in valid_loc_lower:
                    logger.warning(f'INFO.section(): Location {loc} not found in the output - ignoring.')
                else:
                    locations1.append(valid_loc[valid_loc_lower.index(loc.lower())])
            locations = locations1
            if not locations:
                raise ValueError('No valid locations provided.')

        if not data_types:
            data_types = [self._alternate_name_to_data_type(x) for x in self.data_types('section')]
        else:
            valid_types = [self._alternate_name_to_data_type(x) for x in self.data_types('section')]
            data_types = [x for x in data_types if self._alternate_name_to_data_type(x) in valid_types]
            if not data_types:
                logger.warning(f'INFO.section(): No valid data types provided ({data_types}).')

        return locations, data_types
