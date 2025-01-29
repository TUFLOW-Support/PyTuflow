from pathlib import Path
import re
from typing import Union

import numpy as np
import pandas as pd
from netCDF4 import Dataset

from pytuflow.outputs.gpkg_1d import GPKG1D
from pytuflow.outputs.gpkg_2d import GPKG2D
from pytuflow.outputs.gpkg_rl import GPKGRL
from pytuflow.outputs.helpers.get_standard_data_type_name import get_standard_data_type_name
from pytuflow.outputs.helpers.nc_ts import NCTS
from pytuflow.outputs.helpers.time_series_extractor import maximum_extractor, time_series_extractor
from pytuflow.outputs.info import INFO
from pytuflow.outputs.itime_series_2d import ITimeSeries2D
from pytuflow.outputs.helpers.tpc_reader import TPCReader
from pytuflow.pytuflow_types import PathLike, AppendDict, TimeLike
from pytuflow.util.logging import get_logger


logger = get_logger()


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

    This class does not need to be explicitly closed as it will load the results into memory and closes any open files
    after initialisation.

    Parameters
    ----------
    fpath : :class:`PathLike <pytuflow.pytuflow_types.PathLike>`
        The path to the output (.tpc) file.

    Raises
    ------
    FileNotFoundError
        Raised if the .tpc file does not exist.
    FileTypeError
        Raises :class:`pytuflow.pytuflow_types.FileTypeError` if the file does not look like a .tpc file.
    EOFError
        Raised if the .tpc file is empty or incomplete.

    Examples
    --------
    Loading a .tpc file:

    >>> from pytuflow.outputs import TPC
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

    def __init__(self, fpath: PathLike):
        # private
        self._time_series_data_2d = AppendDict()
        self._time_series_data_rl = AppendDict()
        self._maximum_data_2d = AppendDict()
        self._maximum_data_rl = AppendDict()
        self._nc_file = None
        self._ncid = None
        self._gis_layers_initialised = False
        self._gpkg1d = None
        self._gpkg2d = None
        self._gpkgrl = None

        #: str: format of the results - options are 'CSV' or 'NC'. If both are specified, the NC will be preferred.
        self.format = 'CSV'

        super(TPC, self).__init__(fpath)

    def __del__(self):
        if self._ncid:
            self._ncid.close()
            self._ncid = None

    def close(self) -> None:
        """Close the result and any open files. Not required to be called explicitly for the TPC output class."""
        pass  # no files are left open

    @staticmethod
    def looks_like_this(fpath: PathLike) -> bool:
        # docstring inherited
        fpath = Path(fpath)
        if fpath.suffix.upper() != '.TPC':
            return False
        try:
            with fpath.open() as f:
                line = f.readline()
                if not line.startswith('Format Version == 2'):
                    return False
        except Exception as e:
            return False
        return True

    @staticmethod
    def looks_empty(fpath: PathLike) -> bool:
        # docstring inherited
        target_line_count = 10  # fairly arbitrary
        try:
            tpc_reader = TPCReader(fpath)
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
        except Exception as e:
            return True

    def context_combinations(self, context: str) -> pd.DataFrame:
        # docstring inherited
        # split context into components
        ctx = [x.strip().lower() for x in context.split('/')] if context else []

        # 1D
        df = super().context_combinations_1d(ctx)

        # 2D
        df1 = self.context_combinations_2d(ctx)

        if df.empty:
            return df1
        if df1.empty:
            return df
        return pd.concat([df, df1], axis=0, ignore_index=True)

    def times(self, context: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns all the available times for the output.

        The context is an optional input that can be used to filter the return further. Valid contexts
        for TPC results are:

        Domain contexts:
        - 1d: 1D result times - nodes and channels will always have the same times
        - node - times for node types (note, there will be no difference between nodes and channels)
        - channel - times for channel types (note, there will be no difference between nodes and channels)
        - 2d (or po): 2D result times - 2D results can have varying times between result types and locations. This
         will return all unique times
        - rl (or 0d): Reporting locations result times. RL results will have the same times for all RL types

        Data type contexts:
        - [data type]: The data type to filter the times by. This will return all times for the given data type.

        Location contexts:
        - [location]: The location to filter the times by. This will return all times for the given location.

        Combine contexts:
        - [context1]/[context2] ...: Combine multiple contexts to filter the times further ('/' delim).

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
        >>> res.times(fmt='absolute')
        [Timestamp('2021-01-01 00:00:00'), Timestamp('2021-01-01 00:01:00'), ..., Timestamp('2021-01-01 03:00:00')]
        """
        return super().times(context, fmt)

    def data_types(self, context: str = None) -> list[str]:
        """Returns all the available data types (result types) for the output given the context.

        The context is an optional input that can be used to filter the return further. Available
        context are:

        Domain contexts:

        * :code:`1d`
        * :code:`2d` (or :code:`po`)
        * :code:`rl` (or :code:`0d`)

        Geometry contexts (note: they are not plural):

        * :code:`node`
        * :code:`channel`
        * :code:`point` - (for 2d and rl domains only - use :code:`node` for 1d domain)
        * :code:`line` - (for 2d and rl domains only - use :code:`channel` for 1d domain)
        * :code:`polygon` (or :code:`region`)

        Location contexts:

        * :code:`[location]`: The location to filter the data_types by.

        Combine contexts:

        * :code:`[context1]/[context2] ...`  Combine multiple contexts to filter the times further ('/' delim).

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
        Get the available data types for 1D :code:`channel` results:

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
        return super().data_types(context)

    def ids(self, context: str = None) -> list[str]:
        """Returns all the available IDs for the output.

        The context is an optional input that can be used to filter the return further. Available
        context are:

        Domain contexts:

        * :code:`1d`
        * :code:`2d` (or :code:`po`)
        * :code:`rl` (or :code:`0d`)

        Geometry contexts (note: they are not plural):

        * :code:`node`
        * :code:`channel`
        * :code:`point` - (for 2d and rl domains only - use :code:`node` for 1d domain)
        * :code:`line` - (for 2d and rl domains only - use :code:`channel` for 1d domain)
        * :code:`polygon` (or :code:`region`)

        Data type contexts:

        * :code:`[data_type]`: The data_type to filter the ids by.

        Combine contexts:

        * :code:`[context1]/[context2] ...`: Combine multiple contexts to filter the times further ('/' delim).

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
        Get the IDs for all :code:`po` results:

        >>> res.ids('po')
        ['po_poly', 'po_point', 'po_line']

        Get the IDs for all :code:`rl line` results:

        >>> res.ids('rl/line')
        ['rl_line']
        """
        return super().ids(context)

    def maximum(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a dataframe containing the maximum values for the given data types. The returned dataframe
        will include time of maximum results as well.

        It's possible to pass in a well known shorthand for the data type e.g. 'q' for flow.

        The location can be an ID or contextual string, e.g. 'channel' to extract the maximum values
        for all channels. An ID can be used alongside a contextual string since there can be duplicate IDs across
        domains e.g. 'test/channel' - where 'test' is the name and 'channel' is additional context. Note, the order
        does not matter, but it doesn't work very well if your ID has a '/' or has the same name as a contextual string
        (e.g. calling a po line 'line').
        For the TPC result class, the following contexts are available:

        Domain contexts:

        * :code:`1d`
        * :code:`2d` (or :code:`po`)
        * :code:`rl` (or :code:`0d`)

        Geometry contexts (note: they are not plural):

        * :code:`node`
        * :code:`channel`
        * :code:`point` - (for 2d and rl domains only - use :code:`node` for 1d domain)
        * :code:`line` - (for 2d and rl domains only - use :code:`channel` for 1d domain)
        * :code:``polygon` (or :code:`region`)

        Combine contexts:

        * :code:`[context1]/[context2] ...`: Combine multiple contexts to filter the times further ('/' delim).

        The returned DataFrame will have an index column corresponding to the location ids, and the columns
        will be in the format :code:`context/data_type/[max|tmax]`,
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
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        context = '/'.join(locations + data_types)
        ctx = self.context_combinations(context)
        if ctx.empty:
            return pd.DataFrame()

        # 1D
        df = super().maximum(locations, data_types, time_fmt)

        # 2D
        df1 = maximum_extractor(ctx[ctx['domain'] == '2d'].data_type.unique(), data_types,
                                self._maximum_data_2d, ctx, time_fmt, self.reference_time)
        df1.columns = [f'po/{x}' for x in df1.columns]
        if df.empty and not df1.empty:
            df = df1
        elif not df1.empty:
            df = pd.concat([df, df1], axis=0)

        # rl
        df1 = maximum_extractor(ctx[ctx['domain'] == 'rl'].data_type.unique(), data_types,
                                self._maximum_data_rl, ctx, time_fmt, self.reference_time)
        df1.columns = [f'rl/{x}' for x in df1.columns]
        if df.empty and not df1.empty:
            df = df1
        elif not df1.empty:
            df = pd.concat([df, df1], axis=0)

        return df

    def time_series(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                    time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a time series dataframe for the given location(s) and data type(s). INFO result types will
        always share a common time index.

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can be an ID or contextual string, e.g. :code:`channel` to extract the maximum values
        for all channels. An ID can be used alongside a contextual string since there can be duplicate IDs across
        domains e.g. :code:`test/channel` - where :code:`test` is the name and :code:`channel` is additional context.
        Note, the order does not matter, but it doesn't work very well if your ID has a '/' or has the same name as a
        contextual string (e.g. calling a po line 'line').
        For the TPC result class, the following contexts are available:

        Domain contexts:

        * :code:`1d`
        * :code:`2d` (or :code:`po`)
        * :code:`rl` (or :code:`0d`)

        Geometry contexts (note: they are not plural):

        * :code: `node`
        * :code: `channel`
        * :code: `point` - (for 2d and rl domains only - use :code:`node` for 1d domain)
        * :code: `line` - (for 2d and rl domains only - use :code:`channel` for 1d domain)
        * :code: `polygon` (or :code:`region`)

        Combine contexts:

        * :code:`[context1]/[context2] ...`: Combine multiple contexts to filter the times further ('/' delim).

        The returned column names will be in the format :code:¬context/data_type/location`
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
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        context = '/'.join(locations + data_types)
        ctx = self.context_combinations(context)
        if ctx.empty:
            return pd.DataFrame()

        share_idx = ctx[['start', 'end', 'dt']].drop_duplicates().shape[0] < 2

        # 1D
        df = time_series_extractor(ctx[ctx['domain'] == '1d'].data_type.unique(), data_types,
                                   self._time_series_data, ctx, time_fmt, share_idx, self.reference_time)
        df.columns = self._prepend_1d_type_to_column_name(df.columns)

        # 2D
        df1 = time_series_extractor(ctx[ctx['domain'] == '2d'].data_type.unique(), data_types,
                                    self._time_series_data_2d, ctx, time_fmt, share_idx, self.reference_time)
        df1.columns = ['{0}/po/{1}/{2}'.format(*x.split('/')) if x.split('/')[0] == 'time' else f'po/{x}' for x in df1.columns]
        if df.empty and not df1.empty:
            df = df1
        elif not df1.empty:
            if share_idx:
                df1.index = df.index
            df = pd.concat([df, df1], axis=1)

        # rl
        df1 = time_series_extractor(ctx[ctx['domain'] == 'rl'].data_type.unique(), data_types,
                                    self._time_series_data_rl, ctx, time_fmt, share_idx, self.reference_time)
        df1.columns = ['{0}/rl/{1}/{2}'.format(*x.split('/')) if x.split('/')[0] == 'time' else f'rl/{x}' for x in df1.columns]
        if df.empty and not df1.empty:
            df = df1
        elif not df1.empty:
            if share_idx:
                df1.index = df.index
            df = pd.concat([df, df1], axis=1, ignore_index=not share_idx)

        return df

    def _load(self) -> None:
        """Load the TPC file into memory. Called by the __init__ method."""
        self.format = self._tpc_reader.get_property('Time Series Output Format', 'CSV')
        if 'CSV' in self.format:
            self.format = 'CSV'  # it is possible to have both CSV and NC and CSV is a more complete format

        if self.format == 'NC':
            self._nc_file = self._expand_property_path('NetCDF Time Series')
            self._ncid = Dataset(self._nc_file, 'r')

        self.reference_time = self._tpc_reader.get_property('Reference Time', self.reference_time)

        # rl counts - up here since it's easy to get and useful when loading time series and maximum data
        self.rl_point_count = self._tpc_reader.get_property('Number Reporting Location Points', 0)
        self.rl_line_count = self._tpc_reader.get_property('Number Reporting Location Lines', 0)
        self.rl_poly_count = self._tpc_reader.get_property('Number Reporting Location Regions', 0)

        # 1d
        super()._load()

        # po
        self.po_objs = self._load_po_info()
        if not self.po_objs.empty:
            self.po_point_count = self.po_objs[self.po_objs['geometry'] == 'point']['id'].unique().size
            self.po_line_count = self.po_objs[self.po_objs['geometry'] == 'line']['id'].unique().size
            self.po_poly_count = self.po_objs[self.po_objs['geometry'] == 'polygon']['id'].unique().size

        # rl
        self.rl_objs = self._load_rl_info()

        # gis layers
        self.gis_layer_p_fpath = self._expand_property_path('GIS Plot Layer Points')
        self.gis_layer_l_fpath = self._expand_property_path('GIS Plot Layer Lines')
        self.gis_layer_r_fpath = self._expand_property_path('GIS Plot Layer Regions')

        # close open files
        if self._ncid:
            self._ncid.close()
            self._ncid = None

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
                data_type = get_standard_data_type_name(data_type)
                self._time_series_data[data_type] = df
                if df.columns.isin(self.node_info.index).all():
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
                            dtype = get_standard_data_type_name(dtype)
                            self._time_series_data[dtype] = df1
                    df1 = self._post_process_channel_losses_2(df)
                    if df1 is not None:
                        dtype = get_standard_data_type_name('Channel Losses')
                        self._time_series_data[dtype] = df1
                else:
                    data_type = get_standard_data_type_name(data_type)
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
                    data_type = get_standard_data_type_name(data_type)
                self._time_series_data_2d[data_type.lower()] = df

    def _load_time_series_from_property(self, prop: str, data_type: str, domain: str, value: str = None) -> pd.DataFrame:
        p = self._expand_property_path(prop, value=value)
        if p or self.format == 'NC':
            try:
                if self.format == 'CSV':
                    df = self._load_time_series_csv(p)
                elif self.format == 'NC':
                    df = self._load_time_series_nc(data_type, domain)
                else:  # GPKG
                    df = self._load_time_series_gpkg(data_type, domain)
                return df
            except Exception as e:
                logger.warning(f'TPC._load_time_series_from_property(): Error loading from {prop}: {e}')

    def _load_time_series_nc(self, dtype: str, domain: str) -> pd.DataFrame:
        df = NCTS.extract_result(self._ncid, dtype, domain)
        if df is None or df.empty:
            logger.warning(f'TPC._load_time_series_nc(): No data found in NetCDF file for {dtype} for domain {domain}.')
        return df

    def _load_time_series_gpkg(self):
        for prop, value in self._tpc_reader.iter_properties('GPKG Time Series'):
            if str(value).lower().endswith('_1d.gpkg'):
                self._gpkg1d = GPKG1D(self._expand_property_path(prop, value=value))
            elif str(value).lower().endswith('_2d.gpkg'):
                self._gpkg2d = GPKG2D(self._expand_property_path(prop, value=value))
            elif str(value).lower().endswith('_rl.gpkg'):
                self._gpkgrl = GPKGRL(self._expand_property_path(prop, value=value))

        if self._gpkg1d is not None:
            self._time_series_data = self._gpkg1d._time_series_data
            self._nd_res_types = self._gpkg1d._nd_res_types

        if self._gpkg2d is not None:
            self._time_series_data_2d = self._gpkg2d._time_series_data_2d

        if self._gpkgrl is not None:
            self._time_series_data_rl = self._gpkgrl._time_series_data_rl

    def _post_process_channel_losses(self, df: pd.DataFrame, dtype: str) -> pd.DataFrame:
        d = {'Channel Entry Losses': 'Entry', 'Channel Additional Losses': 'Additional', 'Channel Exit Losses': 'Exit'}
        cols = df.columns.str.contains(d[dtype])
        if cols.any():
            df1 = df.loc[:,cols].copy()
            df1.columns = [' '.join(x.split(' ')[2:]) for x in df1.columns]
            return df1

    def _post_process_channel_losses_2(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = df.columns.str.startswith('LC')
        if cols.any():
            df1 = df.loc[:,cols].copy()
            df1.columns = [' '.join(x.split(' ')[1:]) for x in df1.columns]
            return df1

    def _load_maximums(self) -> None:
        # override
        # node maximums
        df = self._load_maximum_from_property('1D Node Maximums')
        if df is not None:
            for col in df.columns[::2]:
                data_type, df1 = self._split_maximum_columns(df, col)
                data_type = get_standard_data_type_name(data_type)
                self._maximum_data[data_type] = df1

        # channel maximums
        df = self._load_maximum_from_property('1D Channel Maximums')
        if df is not None:
            for col in df.columns[::2]:
                data_type, df1 = self._split_maximum_columns(df, col)
                data_type = get_standard_data_type_name(data_type)
                self._maximum_data[data_type] = df1

        # rl maximums
        df = self._load_maximum_from_property('Reporting Location Points Maximums')
        if df is not None:
            data_type, df1 = self._split_maximum_columns(df, 'Hmax')
            data_type = get_standard_data_type_name(data_type)
            self._maximum_data_rl[data_type] = df1
        df = self._load_maximum_from_property('Reporting Location Lines Maximums')
        if df is not None:
            data_type, df1 = self._split_maximum_columns(df, 'Qmax')
            data_type = get_standard_data_type_name(data_type)
            self._maximum_data_rl[data_type] = df1
        df = self._load_maximum_from_property('Reporting Location Regions Maximums')
        if df is not None:
            data_type, df1 = self._split_maximum_columns(df, 'Vol max')
            data_type = get_standard_data_type_name(data_type)
            self._maximum_data_rl[data_type] = df1

        # 2d results do not have maximums, so need to be post-processed.
        for data_type, results in self._time_series_data_2d.items():
            for res in results:
                max_ = res.max()
                tmax = res.idxmax()
                self._maximum_data_2d[data_type] = pd.DataFrame({'max': max_, 'tmax': tmax})

    def _load_maximum_from_property(self, prop: str) -> pd.DataFrame:
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

    def _split_maximum_columns(self, df: pd.DataFrame, col_name: str) -> tuple[str, pd.DataFrame]:
        name = col_name.replace('max', '').strip()
        data_type = get_standard_data_type_name(name)
        if data_type != 'energy':
            df1 = df.loc[:, [col_name, f'Time {col_name}']].copy()
        else:
            df1 = df.loc[:, [col_name]].copy()
            df1[[f'Time {col_name}']] = np.nan
        df1.columns = ['max', 'tmax']
        return data_type, df1

    def _load_po_info(self) -> pd.DataFrame:
        d = {'P': 'point', 'L': 'line', 'R': 'polygon'}
        po_info = {'id': [], 'data_type': [], 'geometry': [], 'start': [], 'end': [], 'dt': []}
        if self.format.lower() == 'gpkg':
            if self._gpkg2d is not None:
                return self._gpkg2d.po_objs
            else:
                return pd.DataFrame(po_info)

        if self._time_series_data_2d:
            plot_objs = self._gis_plot_objects()
            if plot_objs is None or plot_objs.geom.dtype != np.dtype('O'):
                logger.warning('TPC._load_po_info(): Missing or invalid PLOT.csv. Using TPC to guess PO geometry...')
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

    def _gis_plot_objects(self) -> pd.DataFrame:
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

    def _geom_from_tpc(self):
        d = AppendDict()
        df = pd.DataFrame(columns=['geom'])
        df.index.name = 'id'
        for prop, value in self._tpc_reader.iter_properties('^2D', regex=True):
            data_type = re.sub(r'^2D (Point|Line|Region)', '', prop).split('[', 1)[0].strip()
            geom = re.findall('(Point|Line|Region)', prop)[0][0]
            dtype = get_standard_data_type_name(data_type)
            d[dtype] = geom
            i = len(d[dtype]) - 1
            df1 = self._time_series_data_2d[dtype][i]
            df2 = pd.DataFrame({'geom': geom}, index=df1.columns)
            df = pd.concat([df, df2[~df2.index.isin(df.index)]], axis=0)
            df.update(df2)
        return df

    def _load_rl_info(self) -> pd.DataFrame:
        d = {'water level': 'point', 'flow': 'line', 'volume': 'polygon'}
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
