import re
from typing import Union, TYPE_CHECKING
from collections import OrderedDict
from packaging.version import Version

import numpy as np
import pandas as pd

from pytuflow.outputs.helpers import TPCReader
from pytuflow.outputs.info import INFO
from pytuflow.outputs.helpers.get_standard_data_type_name import get_standard_data_type_name
from pytuflow.outputs.helpers.time_series_extractor import gpkg_time_series_extractor
from pytuflow.pytuflow_types import PathLike, TimeLike, TuflowPath
from pytuflow.util.time_util import parse_time_units_string

if TYPE_CHECKING:
    from sqlite3 import Cursor


class GPKG1D(INFO):
    """Class for handling 1D GeoPackage time series results (:code:`.gpkg` - typically ending with :code:`_1D.gpkg`
    or :code:`_swmm_ts.gpkg`). The GPKG time series format is a specific format published by TUFLOW built
    on the GeoPackage standard.

    This class can be used to initialise stand-alone GPKG result files (e.g. :code:`swmm_ts.gpkg` results) however it is
    not required to be used if loading results via the :class:`TPC <pytuflow.outputs.TPC>` class which will load all
    domains automatically (i.e. :code:`GPKG1D`, :code:`GPKG2D`, :code:`GPKGRL`). Note: the :code:`swmm_ts.gpkg` is not
    referenced in the TPC file, so will always require to be initialised with this class.

    Parameters
    ----------
    fpath : :class:`PathLike <pytuflow.pytuflow_types.PathLike>`
        The path to the output (.gpkg) file.

    Raises
    ------
    FileNotFoundError
        Raised if the .info file does not exist.
    FileTypeError
        Raises :class:`pytuflow.pytuflow_types.FileTypeError` if the file does not look like a time
        series .gpkg file.
    EOFError
        Raised if the .info file is empty or incomplete.

    Examples
    --------
    Load a :code:`_swmm_ts.gpkg` file:

    >>> from pytuflow.outputs import GPKG1D
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
    def looks_like_this(fpath: PathLike) -> bool:
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
    def looks_empty(fpath: PathLike) -> bool:
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

    def times(self, context: str = None, fmt: str = 'relative') -> list[TimeLike]:
        # docstring inherited
        return super().times(context, fmt)

    def data_types(self, context: str = None) -> list[str]:
        # docstring inherited
        return super().data_types(context)

    def ids(self, context: str = None) -> list[str]:
        # docstring inherited
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
        return super().section(locations, data_types, time)

    def curtain(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for GPKG1D results. Raises a :code:`NotImplementedError`."""
        return super().curtain(locations, data_types, time)

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for GPKG1D results. Raises a :code:`NotImplementedError`."""
        return super().profile(locations, data_types, time)

    def _load(self):
        import sqlite3
        try:
            conn = sqlite3.connect(self.fpath)
        except Exception as e:
            raise Exception(f'Error connecting to sqlite database: {e}')
        try:
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
                    reference_time, _ = parse_time_units_string(rt, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
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

            self._load_channel_info(cur)
            self._load_node_info(cur)
            self._load_time_series(cur)
            self._load_maximums()
            self._load_1d_info()

            self.gis_layer_p_fpath = TuflowPath(self.fpath.parent) / f'{self.fpath.name} >> {self._gis_layer_p_name}'
            self.gis_layer_l_fpath = TuflowPath(self.fpath.parent) / f'{self.fpath.name} >> {self._gis_layer_l_name}'
        except Exception as e:
            raise Exception(f'Error loading GPKG1D: {e}')
        finally:
            conn.close()

    def _init_tpc_reader(self) -> TPCReader:
        pass

    def _load_time_series(self, cur: 'Cursor'):
        # nodes
        cur.execute(f'SELECT Column_name FROM Timeseries_info WHERE Table_name = "{self._gis_layer_p_name}";')
        data_types = [x[0] for x in cur.fetchall()]
        for dtype in data_types:
            dtype1 = 'node flow regime' if dtype == 'Flow Regime' else get_standard_data_type_name(dtype)
            self._nd_res_types.append(dtype1)
            self._time_series_data[dtype1] = gpkg_time_series_extractor(cur, dtype, self._gis_layer_p_name)

        # channels
        cur.execute(f'SELECT Column_name FROM Timeseries_info WHERE Table_name = "{self._gis_layer_l_name}";')
        data_types = [x[0] for x in cur.fetchall()]
        for dtype in data_types:
            dtype1 = 'channel flow regime' if dtype == 'Flow Regime' else get_standard_data_type_name(dtype)
            self._time_series_data[dtype1] = gpkg_time_series_extractor(cur, dtype, self._gis_layer_l_name)

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
            self.channel_info = pd.DataFrame(d)
            self.channel_info.set_index('id', inplace=True)
            self.channel_info['flags'].apply(lambda x: x.split('[')[1].strip(']') if '[' in x else x)
            if self._is_swmm:
                self.channel_info['ispipe'] = (~np.isnan(self.channel_info['lbus_obvert']) & ~np.isnan(self.channel_info['lbds_obvert']))
                self.channel_info['ispit'] = False
            else:
                self.channel_info['ispipe'] = self.channel_info['flags'].str.match(r'.*[CR].*', False)
                self.channel_info['ispit'] = self.channel_info.index == self.channel_info['ds_node']
        else:
            self.channel_info = pd.DataFrame([], columns=COLUMNS)

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
                self.node_info = pd.DataFrame(d)
                self.node_info.set_index('id', inplace=True)
            else:
                self.node_info = pd.DataFrame([], columns=COLUMNS + ['nchannel', 'channels'])
                self.node_info.set_index('id', inplace=True)
        else:
            cur.execute('SELECT ID as id FROM Geom_P;')
            ret = cur.fetchall()
            if ret:
                self.node_info = pd.DataFrame(index=[x[0] for x in ret])
                self.node_info['nchannel'] = 0
                self.node_info['channels'] = ''
            else:
                self.node_info = pd.DataFrame([], columns=['id', 'nchannel', 'channels'])
                self.node_info.set_index('id', inplace=True)

        if self.node_info.empty:
            return

        # get the number of channels and the channels for each node
        chan_info = self.channel_info.loc[~self.channel_info['ispit'],:]  # don't include channels that are pits
        self.node_info['nchannel'] = 0
        self.node_info['channels'] = ''
        for node in self.node_info.index:
            us = chan_info[chan_info['us_node'] == node].index.tolist()
            ds = chan_info[chan_info['ds_node'] == node].index.tolist()
            self.node_info.loc[node, 'nchannel'] = len(us) + len(ds)
            if len(us) + len(ds) == 1:  # to match how it's done in the TPC node_info.csv
                if us:
                    self.node_info.at[node, 'channels'] = us[0]
                else:
                    self.node_info.at[node, 'channels'] = ds[0]
            else:
                self.node_info.at[node, 'channels'] = us + ds

    def _get_pits(self, dfconn: pd.DataFrame) -> np.ndarray:
        if self._is_swmm:
            df = dfconn.copy()
            # get inlet levels at upstream nodes
            df['pit'] = self.node_info.loc[dfconn['us_node'], 'inlet_level'].tolist()
            # need to get the last downstream node since it won't be accounted for by any upstream node
            df['pit_'] = np.nan
            nd = df.iloc[-1, df.columns.get_loc('ds_node')]
            df.iloc[-1, df.columns.get_loc('pit_')] = self.node_info.loc[nd, 'inlet_level']
        else:
            df = dfconn.copy()
            pits = []
            for nd in df['us_node']:
                if nd in self.channel_info.index and self.channel_info.loc[nd, 'ispit']:
                    pits.append(self.channel_info.loc[nd, 'lbus_obvert'])
                else:
                    pits.append(np.nan)
            df['pit'] = pits

            df['pit_'] = np.nan
            nd = dfconn.iloc[-1, dfconn.columns.get_loc('ds_node')]
            if nd in self.channel_info.index and self.channel_info.loc[nd, 'ispit']:
                df.iloc[-1, dfconn.columns.get_loc('pit_')] = self.channel_info.loc[nd, 'lbus_obvert']

        df1 = self._lp.melt_2_columns(df, ['pit', 'pit_'], 'pits')
        return df1['pits'].to_numpy()
