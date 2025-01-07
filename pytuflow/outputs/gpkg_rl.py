import re
import typing
from typing import Union

import numpy as np
import pandas as pd
from packaging.version import Version

from .gpkg_2d import GPKG2D
from pytuflow.pytuflow_types import PathLike, AppendDict, TuflowPath
from pytuflow.outputs.helpers.time_series_extractor import time_series_extractor, \
    maximum_extractor
from pytuflow.util.time_util import parse_time_units_string

if typing.TYPE_CHECKING:
    from sqlite3 import Cursor


class GPKGRL(GPKG2D):
    """Class for handling RL GeoPackage time series results (.gpkg). The GPKG time series format is a specific
    format published by TUFLOW built on the GeoPackage standard.

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
        Raises :class:`pytuflow.pytuflow_types.FileTypeError` if the file does not look like a 1D time
        series .gpkg file.
    EOFError
        Raised if the .info file is empty or incomplete.

    Examples
    --------
    >>> from pytuflow.outputs.gpkg_rl import GPKGRL
    """

    def __init__(self, fpath: PathLike):
        # private
        self._time_series_data_rl = AppendDict()
        self._maximum_data_rl = AppendDict()

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
                valid = False
            else:
                valid = None
                for table_name in ['Geom_P', 'Geom_L', 'Geom_R']:
                    cur.execute(f'SELECT count(*) FROM sqlite_master WHERE type=\'table\' AND name="{table_name}";')
                    count = int(cur.fetchone()[0])
                    if count:
                        cur.execute(f'SELECT Type FROM "{table_name}" LIMIT 1;')
                        typ = cur.fetchone()
                        if typ:
                            valid = typ[0].lower() == 'rl'
                            break
                if valid is None:  # could not determine if it is valid - could be empty
                    valid = True
        except Exception as e:
            valid = False
        finally:
            conn.close()

        return valid

    def maximum(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time_fmt: str = 'relative') -> pd.DataFrame:
        # docstring inherited
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        context = '/'.join(locations + data_types)
        ctx = self.context_combinations(context)
        if ctx.empty:
            return pd.DataFrame()

        df = maximum_extractor(ctx[ctx['domain'] == 'rl'].data_type.unique(), data_types,
                               self._maximum_data_rl, ctx, time_fmt, self.reference_time)
        df.columns = [f'rl/{x}' for x in df.columns]
        return df

    def time_series(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                    time_fmt: str = 'relative') -> pd.DataFrame:
        # docstring inherited
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        context = '/'.join(locations + data_types)
        ctx = self.context_combinations(context)
        if ctx.empty:
            return pd.DataFrame()

        share_idx = ctx[['start', 'end', 'dt']].drop_duplicates().shape[0] < 2
        df = time_series_extractor(ctx[ctx['domain'] == 'rl'].data_type.unique(), data_types,
                                   self._time_series_data_rl, ctx, time_fmt, share_idx, self.reference_time)
        df.columns = ['{0}/rl/{1}/{2}'.format(*x.split('/')) if x.split('/')[0] == 'time' else f'rl/{x}' for x in
                      df.columns]
        return df

    def _load(self):
        import sqlite3
        try:
            conn = sqlite3.connect(self.fpath)
        except Exception as e:
            raise Exception(f'Error connecting to sqlite database: {e}')

        try:
            self.name = re.sub(r'_TS_RL$', '', self.fpath.stem)

            cur = conn.cursor()
            cur.execute('SELECT Version FROM TUFLOW_timeseries_version;')
            self.format_version = Version(cur.fetchone()[0])

            reference_time = None
            cur.execute(
                'SELECT DISTINCT Table_name, Count, Series_name, Series_units, Reference_time FROM Timeseries_info;')
            for table_name, count, series_name, units, rt in cur.fetchall():
                if reference_time is None:
                    reference_time, _ = parse_time_units_string(rt, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
                                                                '%Y-%m-%d %H:%M:%S')
                if re.findall('_P$', table_name):
                    self._gis_layer_p_name = table_name
                elif re.findall('_L$', table_name):
                    self._gis_layer_l_name = table_name
                else:
                    self._gis_layer_r_name = table_name

                if 'ft' in units.lower():
                    self.units = 'us imperial'

            if reference_time is not None:
                self.reference_time = reference_time

            if self._gis_layer_p_name:
                cur.execute('SELECT COUNT(*) FROM Geom_P;')
                self.rl_point_count = cur.fetchone()[0]
                self.gis_layer_p_fpath = TuflowPath(self.fpath.parent) / f'{self.fpath.name} >> {self._gis_layer_p_name}'
            if self._gis_layer_l_name:
                cur.execute('SELECT COUNT(*) FROM Geom_L;')
                self.rl_line_count = cur.fetchone()[0]
                self.gis_layer_l_fpath = TuflowPath(self.fpath.parent) / f'{self.fpath.name} >> {self._gis_layer_l_name}'
            if self._gis_layer_r_name:
                cur.execute('SELECT COUNT(*) FROM Geom_R;')
                self.rl_poly_count = cur.fetchone()[0]
                self.gis_layer_r_fpath = TuflowPath(self.fpath.parent) / f'{self.fpath.name} >> {self._gis_layer_r_name}'

            self._load_time_series(cur, self._time_series_data_rl)
            self._load_maximums(self._time_series_data_rl, self._maximum_data_rl)
            self._load_rl_info(cur)
        except Exception as e:
            raise Exception(f'Error loading GPKGRL: {e}')
        finally:
            conn.close()

    def _load_rl_info(self, cur: 'Cursor'):
        rl_info = {'id': [], 'data_type': [], 'geometry': [], 'start': [], 'end': [], 'dt': []}
        for dtype, vals in self._time_series_data_rl.items():
            for df1 in vals:
                if df1.empty:
                    continue
                dt = np.round((df1.index[1] - df1.index[0]) * 3600., decimals=2)
                start = df1.index[0]
                end = df1.index[-1]
                for col in df1.columns:
                    rl_info['id'].append(col)
                    rl_info['data_type'].append(dtype)
                    if len(self._geoms[dtype]) == 1:
                        rl_info['geometry'].append(self._geoms[dtype][0])
                    else:
                        rl_info['geometry'].append(self._geom_from_id(cur, col))
                    rl_info['start'].append(start)
                    rl_info['end'].append(end)
                    rl_info['dt'].append(dt)

        self.rl_objs = pd.DataFrame(rl_info)
