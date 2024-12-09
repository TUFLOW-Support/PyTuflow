from datetime import timedelta
from pathlib import Path
import re
from typing import Union

import numpy as np
import pandas as pd
from netCDF4 import Dataset

from pytuflow.outputs.helpers.get_standard_data_type_name import get_standard_data_type_name
from pytuflow.outputs.helpers.nc_ts import NC_TS
from pytuflow.outputs.helpers.temporal_properties import TemporalProp
from pytuflow.outputs.helpers.tpc_internal_data_type_mapping import map_standard_data_types_to_tpc_internal
from pytuflow.outputs.info import INFO
from pytuflow.outputs.itime_series_2d import ITimeSeries2D
from pytuflow.outputs.helpers.tpc_reader import TPCReader
from pytuflow.pytuflow_types import PathLike, AppendDict, TimeLike
from pytuflow.util.logging import get_logger


logger = get_logger()


class TPC(INFO, ITimeSeries2D):
    """Class to handle the standard TUFLOW Time Series result file (.tpc).

    This class supports both 1D, 2D, and  reporting location (RL) results. It also supports varying time indexes between
    results, including within a single domain e.g. 2d po results where water levels for one location are at a different
    temporal resolution than another location. This is not something that TUFLOW Classic/HPC will do, however it
    is something that can occur in TUFLOW FV. TUFLOW Classic/HPC can have different time indexes
    between 1D and 2D / RL results.

    This class also supports duplicate IDs across domains e.g. a 1D node called 'test', a PO point called 'test',
    and an RL point called 'test' - these can all have the same ID with a 'Water Level' result attached.

    This class does not need to be explicitly closed as it will load the results into memory and closes any open files
    after initialisation.

    Examples
    --------
    >>> from pytuflow.outputs import TPC
    >>> res = TPC('path/to/file.tpc')
    """

    def __init__(self, fpath: PathLike) -> None:
        # docstring inherited
        # private
        self._time_series_data_2d = AppendDict()
        self._time_series_data_rl = AppendDict()
        self._maximum_data_2d = AppendDict()
        self._maximum_data_rl = AppendDict()
        self._nc_file = None
        self._ncid = None
        self._gis_layers_initialised = False

        #: str: format of the results - options are 'CSV' or 'NC'. If both are specified, the NC will be preferred.
        self.format = 'CSV'

        super(TPC, self).__init__(fpath)

    def __del__(self):
        if self._ncid:
            self._ncid.close()
            self._ncid = None

    def load(self) -> None:
        # docstring inherited
        self.format = self.tpc_reader.get_property('Time Series Output Format', 'CSV')
        if 'CSV' in self.format:
            self.format = 'CSV'  # it is possible to have both CSV and NC and CSV is a more complete format

        if self.format == 'NC':
            self._nc_file = self._expand_property_path('NetCDF Time Series')
            self._ncid = Dataset(self._nc_file, 'r')

        self.reference_time = self.tpc_reader.get_property('Reference Time', self.reference_time)

        # rl counts - up here since it's easy to get and useful when loading time series and maximum data
        self.rl_point_count = self.tpc_reader.get_property('Number Reporting Location Points', 0)
        self.rl_line_count = self.tpc_reader.get_property('Number Reporting Location Lines', 0)
        self.rl_poly_count = self.tpc_reader.get_property('Number Reporting Location Regions', 0)

        # 1d
        super().load()

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
        ctx = [x.lower() for x in context.split()] if context else []

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
        - [context1] [context2] ...: Combine multiple contexts to filter the times further (space delim).

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
        return super().times(context, fmt)

    def data_types(self, context: str = None) -> list[str]:
        """Returns all the available data types (result types) for the output given the context.

        The context is an optional input that can be used to filter the return further. Available
        context are:

        Domain contexts:
        - 1d
        - 2d (or po)
        - rl (or 0d)

        Geometry contexts:
        - node
        - channel
        - point - (for 2d and rl domains only - use 'node' for 1d domain)
        - line - (for 2d and rl domains only - use 'channel' for 1d domain)
        - polygon (or region)

        Location contexts:
        - [location]: The location to filter the data_types by.

        Combine contexts:
        - [context1] [context2] ...: Combine multiple contexts to filter the times further (space delim).

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
        return super().data_types(context)

    def ids(self, context: str = None) -> list[str]:
        """Returns all the available IDs for the output.

        The context is an optional input that can be used to filter the return further. Available
        context are:

        Domain contexts:
        - 1d
        - 2d (or po)
        - rl (or 0d)

        Geometry contexts:
        - node
        - channel
        - point - (for 2d and rl domains only - use 'node' for 1d domain)
        - line - (for 2d and rl domains only - use 'channel' for 1d domain)
        - polygon (or region)

        Data type contexts:
        - [data_type]: The data_type to filter the ids by.

        Combine contexts:
        - [context1] [context2] ...: Combine multiple contexts to filter the times further (space delim).

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
        >>> res.ids('node')
        ['FC01.1_R.1', 'FC01.1_R.2', 'FC01.2_R.1', 'FC01.2_R.2', 'FC04.1_C.1', 'FC04.1_C.2']
        >>> res.ids('channel')
        ['FC01.1_R', 'FC01.2_R', 'FC04.1_C']
        """
        return super().ids(context)

    def maximum(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time_fmt: str = 'relative') -> pd.DataFrame:
        # docstring inherited
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        context = ' '.join(locations + data_types)
        ctx = self.context_combinations(context)
        if ctx.empty:
            return pd.DataFrame()

        # 1D
        df = super().maximum(locations, data_types, time_fmt)

        # 2D
        df1 = self._extract_maximum(data_types, ctx[ctx['domain'] == '2d'].data_type.unique(),
                                    self._maximum_data_2d, ctx, time_fmt)
        df1.columns = [f'po/{x}' for x in df1.columns]
        if df.empty and not df1.empty:
            df = df1
        elif not df1.empty:
            df = pd.concat([df, df1], axis=0)

        # rl
        df1 = self._extract_maximum(data_types, ctx[ctx['domain'] == 'rl'].data_type.unique(),
                                    self._maximum_data_rl, ctx, time_fmt)
        df1.columns = [f'rl/{x}' for x in df1.columns]
        if df.empty and not df1.empty:
            df = df1
        elif not df1.empty:
            df = pd.concat([df, df1], axis=0)

        return df

    def _info_name_correction(self, name: str) -> str:
        # override this as it isn't needed for TPC
        return name

    def _load_time_series(self) -> None:
        """Load time-series data into memory."""
        # load node time series
        for prop, _ in self.tpc_reader.iter_properties(start_after='1D Node Maximums', end_before='1D Channel Maximums'):
            data_type = prop.replace('1D', '').strip()
            df = self._load_time_series_from_property(prop, data_type, '1D')
            if df is not None:
                data_type = get_standard_data_type_name(data_type)
                self._time_series_data[data_type] = df

        # load channel time series
        for prop, _ in self.tpc_reader.iter_properties(start_after='1D Channel Maximums', end_before='Number Reporting Location Points'):
            data_type = prop.replace('1D', '').strip()
            df = self._load_time_series_from_property(prop, data_type, '1D')
            if df is not None:
                if 'Channel Losses' in data_type:
                    for dtype in ['Channel Entry Losses', 'Channel Additional Losses', 'Channel Exit Losses']:
                        df1 = self._post_process_channel_losses(df, dtype)
                        dtype = get_standard_data_type_name(dtype)
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
        for prop, value in self.tpc_reader.iter_properties('^2D', regex=True):
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
                else:
                    df = self._load_time_series_nc(data_type, domain)
                return df
            except Exception as e:
                logger.warning(f'TPC._load_time_series_from_property(): Error loading from {prop}: {e}')

    def _load_time_series_nc(self, dtype: str, domain: str) -> pd.DataFrame:
        df = NC_TS.extract_result(self._ncid, dtype, domain)
        if df is None or df.empty:
            logger.warning(f'TPC._load_time_series_nc(): No data found in NetCDF file for {dtype} for domain {domain}.')
        return df

    def _post_process_channel_losses(self, df: pd.DataFrame, dtype: str) -> pd.DataFrame:
        d = {'Channel Entry Losses': 'Entry', 'Channel Additional Losses': 'Additional', 'Channel Exit Losses': 'Exit'}
        cols = df.columns.str.contains(d[dtype])
        df1 = df.loc[:,cols].copy()
        df1.columns = [' '.join(x.split(' ')[2:]) for x in df1.columns]
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
        plot_objs = self._gis_plot_objects()
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
        else:
            logger.error('TPC._gis_plot_objects(): Could not find GIS Plot Objects property.')

    def _load_rl_info(self) -> pd.DataFrame:
        d = {'water level': 'point', 'flow': 'line', 'volume': 'polygon'}
        rl_info = {'id': [], 'data_type': [], 'geometry': [], 'start': [], 'end': [], 'dt': []}
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
