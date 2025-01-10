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
from pytuflow.fm import GXY
from pytuflow.fm import DAT
from pytuflow.util.time_util import closest_time_index


class FMTS(INFO):
    """Class for handling 1D Flood Modeller time series outputs.

    The accepted result formats are:

    * :code:`.zzn` (requires the accompanying :code:`.zzl` file)
    * :code:`.csv` exported from the Flood Modeller GUI.
    * :code:`.csv` exported using the Flood Modeller API Python library

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
    >>> from pytuflow.outputs import FMTS
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
        if context and 'section' in context and 'pits' in dat_types:
            dat_types.remove('pits')
        return dat_types

    def ids(self, context: str = None) -> list[str]:
        # docstring inherited
        if context and context.lower() == 'channel':
            return self.channel_info.index.tolist()
        if context and context.lower() == 'node':
            return self.node_info.index.tolist()
        return super().ids(context)

    def maximum(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time_fmt: str = 'relative') -> pd.DataFrame:
        # docstring inherited
        return super().maximum(locations, data_types, time_fmt)

    def time_series(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                    time_fmt: str = 'relative') -> pd.DataFrame:
        # docstring inherited
        return super().time_series(locations, data_types, time_fmt)

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        # docstring inherited
        if not self._support_section_plotting:
            raise ResultError('A DAT or GXY file is required for section plotting')

        locations = [locations] if not isinstance(locations, list) else locations
        if len(locations) > 2:
            raise ResultError('A maximum of two locations can be provided for a FMTS section plot')

        # convert node id to the channel id - assume first node is upstream of second node (if it is present)
        nd1 = self.node_info[self.node_info['name'].str.lower() == locations[0].lower()].index[0]
        ch1 = self.channel_info[self.channel_info['us_node'] == nd1].index[0]  # downstream channel
        if len(locations) == 2:
            nd2 = self.node_info[self.node_info['name'].str.lower() == locations[1].lower()].index[0]
            ch2 = self.channel_info[self.channel_info['ds_node'] == nd2].index[0]  # upstream channel
            locs = [ch1, ch2]
        else:
            locs = [ch1]

        # get locations and data types
        locations, data_types = self._figure_out_loc_and_data_types_lp(locs, data_types)

        # get the time index
        times = self.times(fmt='absolute') if isinstance(time, datetime) else self.times()
        timeidx = closest_time_index(times, time)

        # get connectivity
        dfconn = self.connectivity(locations)

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
