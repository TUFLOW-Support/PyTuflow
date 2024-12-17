import re
from typing import Union, TYPE_CHECKING
from collections import OrderedDict
from packaging.version import Version

import numpy as np
import pandas as pd

from pytuflow.outputs.helpers import TPCReader
from pytuflow.outputs.info import INFO
from pytuflow.outputs.helpers.get_standard_data_type_name import get_standard_data_type_name
from pytuflow.outputs.helpers.gpkg_time_series_extractor import gpkg_time_series_extractor
from pytuflow.pytuflow_types import PathLike, TimeLike

if TYPE_CHECKING:
    from sqlite3 import Cursor


class GPKG_TS_1D(INFO):
    """Class for handling GeoPackage time series results. The GPKG time series format is a specific format published
     by TUFLOW built on the GeoPackage standard.

    This class does not need to be explicitly closed as it will load the results into memory and closes any open files
    after initialisation.

    Parameters
    ----------
    fpath : :class:`PathLike <pytuflow.pytuflow_types.PathLike>`
        The path to the output (.gpkg) file.

    Raises
    ------
    FileNotFoundError
        Raised if the .info file does not exist.
    FileTypeError
        Raises :class:`pytuflow.pytuflow_types.FileTypeError` if the file does not look like a time series .info file.
    EOFError
        Raised if the .info file is empty or incomplete.

    Examples
    --------
    >>> from pytuflow.outputs import GPKG_TS_1D
    >>> res = GPKG_TS_1D('path/to/file.gpkg')
    """

    _PLOTTING_CAPABILITY = ['timeseries', 'section']

    def __init__(self, fpath: PathLike):
        #: Version: the format version
        self.format_version = None

        # private properties
        self._gis_layer_p_name = None
        self._gis_layer_l_name = None

        super().__init__(fpath)

    def close(self) -> None:
        """Close the result and any open files associated with the result.
        Not required to be called for the GPKG TS output class as all files are closed after initialisation.
        """
        pass  # no files are left open

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
            _ = cur.fetchone()[0]
            valid = True
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
        """Not supported for GPKG_TS_1D results. Raises a :code:`NotImplementedError`.

        See Also
        --------
        :meth:`has_plotting_capability` : Check if a given output class supports a given plotting capability before
           trying to use it.
        """
        raise NotImplementedError('GPKG_TS_1D outputs do not support curtain plotting.')

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for GPKG_TS_1D results. Raises a :code:`NotImplementedError`.

        See Also
        --------
        :meth:`has_plotting_capability` : Check if a given output class supports a given plotting capability before
           trying to use it.
        """
        raise NotImplementedError('GPKG_TS_1D outputs do not support vertical profile plotting.')

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
                self.name = re.sub(r'_swmm_ts$', '', self.fpath.stem)
            else:
                self.name = re.sub(r'_TS_1D$', '', self.fpath.stem)
            cur.execute('SELECT DISTINCT Table_name, Count, Series_name, Series_units FROM Timeseries_info;')
            for table_name, count, series_name, units in cur.fetchall():
                if re.findall('_P$', table_name):
                    self.node_count = count
                    self._gis_layer_p_name = table_name
                else:
                    self.channel_count = count
                    self._gis_layer_l_name = table_name
                if series_name.lower() == 'water level' and units.lower() == 'ft':
                    self.units = 'us imperial'

            self._load_channel_info(cur)
            self._load_node_info(cur)
            self._load_time_series(cur)
            self._load_maximums()
            self._load_1d_info()
        except Exception as e:
            raise Exception(f'Error loading GPKG_TS_1D: {e}')
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
        if self.format_version < Version('1.1'):
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
            if self.format_version < Version('1.1'):
                self.channel_info['ispipe'] = (~np.isnan(self.channel_info['lbus_obvert']) & ~np.isnan(self.channel_info['lbds_obvert']))
                self.channel_info['ispit'] = False
            else:
                self.channel_info['ispipe'] = self.channel_info['flags'].str.match(r'.*[CR].*', False)
                self.channel_info['ispit'] = self.channel_info.index == self.channel_info['ds_node']
        else:
            self.channel_info = pd.DataFrame([], columns=COLUMNS)

    def _load_node_info(self, cur: 'Cursor'):
        if self.format_version < Version('1.1'):
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
