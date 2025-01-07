import re
from pathlib import Path
from typing import Union
import typing

import numpy as np
import pandas as pd
from packaging.version import Version

from pytuflow.outputs.helpers.get_standard_data_type_name import get_standard_data_type_name
from pytuflow.outputs.helpers.time_series_extractor import gpkg_time_series_extractor, time_series_extractor, \
    maximum_extractor
from pytuflow.outputs.time_series import TimeSeries
from pytuflow.outputs.itime_series_2d import ITimeSeries2D
from pytuflow.pytuflow_types import PathLike, AppendDict, FileTypeError, TimeLike, TuflowPath
from pytuflow.util.time_util import parse_time_units_string

if typing.TYPE_CHECKING:
    from sqlite3 import Cursor


class GPKG2D(TimeSeries, ITimeSeries2D):
    """Class for handling 2D GeoPackage time series results (.gpkg). The GPKG time series format is a specific
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
    >>> from pytuflow.outputs.gpkg_2d import GPKG2D
    """
    _PLOTTING_CAPABILITY = ['timeseries']

    def __init__(self, fpath: PathLike):
        super(GPKG2D, self).__init__(fpath)

        #: Path: The path to the source output file.
        self.fpath = Path(fpath)
        #: str: The unit system used in the output file.
        self.units = 'si'
        #: Version: the format version
        self.format_version = None

        if not self.fpath.exists():
            raise FileNotFoundError(f'File not found: {self.fpath}')

        # call before tpc_reader is initialised to give a clear error message if it isn't actually a .info time series file
        if not self.looks_like_this(self.fpath):
            raise FileTypeError(f'File does not look like a time series {self.__class__.__name__} file: {fpath}')

        # call after tpc_reader has been initialised so that we know the file can be loaded by the reader
        if self.looks_empty(fpath):
            raise EOFError(f'File is empty or incomplete: {fpath}')

        # private
        self._time_series_data_2d = AppendDict()
        self._maximum_data_2d = AppendDict()
        self._geoms = AppendDict()
        self._gis_layer_p_name = None
        self._gis_layer_l_name = None
        self._gis_layer_r_name = None

        self._load()

    def close(self) -> None:
        """Close the result and any open files associated with the result.
        Not required to be called for this output class as all files are closed after initialisation.
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
                            valid = typ[0].lower() == '2d'
                            break
                if valid is None:  # could not determine if it is valid - could be empty
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

    def context_combinations(self, context: str) -> pd.DataFrame:
        # docstring inherited
        # split context into components
        ctx = [x.strip().lower() for x in context.split('/')] if context else []
        return super().context_combinations_2d(ctx)

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
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        context = '/'.join(locations + data_types)
        ctx = self.context_combinations(context)
        if ctx.empty:
            return pd.DataFrame()

        df = maximum_extractor(ctx[ctx['domain'] == '2d'].data_type.unique(), data_types,
                               self._maximum_data_2d, ctx, time_fmt, self.reference_time)
        df.columns = [f'po/{x}' for x in df.columns]
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
        df = time_series_extractor(ctx[ctx['domain'] == '2d'].data_type.unique(), data_types,
                                   self._time_series_data_2d, ctx, time_fmt, share_idx, self.reference_time)
        df.columns = ['{0}/po/{1}/{2}'.format(*x.split('/')) if x.split('/')[0] == 'time' else f'po/{x}' for x in
                      df.columns]
        return df

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for GPKG2D results. Raises a :code:`NotImplementedError`.

        See Also
        --------
        :meth:`has_plotting_capability` : Check if a given output class supports a given plotting capability before
           trying to use it.
        """
        raise NotImplementedError(f'{__class__.__name__} files do not support section plotting.')

    def curtain(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for GPKG2D results. Raises a :code:`NotImplementedError`.

        See Also
        --------
        :meth:`has_plotting_capability` : Check if a given output class supports a given plotting capability before
           trying to use it.
        """
        raise NotImplementedError(f'{__class__.__name__} files do not support curtain plotting.')

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for GPKG2D results. Raises a :code:`NotImplementedError`.

        See Also
        --------
        :meth:`has_plotting_capability` : Check if a given output class supports a given plotting capability before
           trying to use it.
        """
        raise NotImplementedError(f'{__class__.__name__} files do not support vertical profile plotting.')

    def _load(self):
        import sqlite3
        try:
            conn = sqlite3.connect(self.fpath)
        except Exception as e:
            raise Exception(f'Error connecting to sqlite database: {e}')

        try:
            self.name = re.sub(r'_TS_2D$', '', self.fpath.stem)

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
                self.po_point_count = cur.fetchone()[0]
                self.gis_layer_p_fpath = TuflowPath(self.fpath.parent) / f'{self.fpath.name} >> {self._gis_layer_p_name}'
            if self._gis_layer_l_name:
                cur.execute('SELECT COUNT(*) FROM Geom_L;')
                self.po_line_count = cur.fetchone()[0]
                self.gis_layer_l_fpath = TuflowPath(self.fpath.parent) / f'{self.fpath.name} >> {self._gis_layer_l_name}'
            if self._gis_layer_r_name:
                cur.execute('SELECT COUNT(*) FROM Geom_R;')
                self.po_poly_count = cur.fetchone()[0]
                self.gis_layer_r_fpath = TuflowPath(self.fpath.parent) / f'{self.fpath.name} >> {self._gis_layer_r_name}'

            self._load_time_series(cur, self._time_series_data_2d)
            self._load_maximums(self._time_series_data_2d, self._maximum_data_2d)
            self._load_po_info(cur)
        except Exception as e:
            raise Exception(f'Error loading GPKG2D: {e}')
        finally:
            conn.close()

    def _load_time_series(self, cur: 'Cursor', storage: AppendDict):
        if self._gis_layer_p_name:
            cur.execute(f'SELECT Column_name FROM Timeseries_info WHERE Table_name = "{self._gis_layer_p_name}";')
            data_types = [row[0] for row in cur.fetchall()]
            for dtype in data_types:
                dtype1 = get_standard_data_type_name(dtype)
                storage[dtype1] = gpkg_time_series_extractor(cur, dtype, self._gis_layer_p_name)
                self._geoms[dtype1] = 'point'

        if self._gis_layer_l_name:
            cur.execute(f'SELECT Column_name FROM Timeseries_info WHERE Table_name = "{self._gis_layer_l_name}";')
            data_types = [row[0] for row in cur.fetchall()]
            for dtype in data_types:
                dtype1 = get_standard_data_type_name(dtype)
                storage[dtype1] = gpkg_time_series_extractor(cur, dtype, self._gis_layer_l_name)
                self._geoms[dtype1] = 'line'

        if self._gis_layer_r_name:
            cur.execute(f'SELECT Column_name FROM Timeseries_info WHERE Table_name = "{self._gis_layer_r_name}";')
            data_types = [row[0] for row in cur.fetchall()]
            for dtype in data_types:
                dtype1 = 'max water level' if dtype.lower() == 'max water level' else get_standard_data_type_name(dtype)
                storage[dtype1] = gpkg_time_series_extractor(cur, dtype, self._gis_layer_r_name)
                self._geoms[dtype1] = 'poly'

    def _load_maximums(self, time_series_storage: AppendDict, storage: AppendDict) -> None:
        for data_type, results in time_series_storage.items():
            for res in results:
                max_ = res.max()
                tmax = res.idxmax()
                storage[data_type] = pd.DataFrame({'max': max_, 'tmax': tmax})

    def _load_po_info(self, cur: 'Cursor'):
        po_info = {'id': [], 'data_type': [], 'geometry': [], 'start': [], 'end': [], 'dt': []}
        for dtype, vals in self._time_series_data_2d.items():
            for df1 in vals:
                if df1.empty:
                    continue
                dt = np.round((df1.index[1] - df1.index[0]) * 3600., decimals=2)
                start = df1.index[0]
                end = df1.index[-1]
                for col in df1.columns:
                    po_info['id'].append(col)
                    po_info['data_type'].append(dtype)
                    if len(self._geoms[dtype]) == 1:
                        po_info['geometry'].append(self._geoms[dtype][0])
                    else:
                        po_info['geometry'].append(self._geom_from_id(cur, col))
                    po_info['start'].append(start)
                    po_info['end'].append(end)
                    po_info['dt'].append(dt)

        self.po_objs = pd.DataFrame(po_info)

    def _geom_from_id(self, cur: 'Cursor', id_: str) -> str:
        if self._gis_layer_p_name:
            cur.execute(f'SELECT ID FROM Geom_P WHERE ID = "{id_}";')
            if cur.fetchone():
                return 'point'

        if self._gis_layer_l_name:
            cur.execute(f'SELECT ID FROM Geom_L WHERE ID = "{id_}";')
            if cur.fetchone():
                return 'line'

        if self._gis_layer_r_name:
            cur.execute(f'SELECT ID FROM Geom_R WHERE ID = "{id_}";')
            if cur.fetchone():
                return 'poly'

        return ''

    def _loc_data_types_to_list(self, locations: Union[str, list[str]],
                                data_types: Union[str, list[str]]) -> tuple[list[str], list[str]]:
        if locations is None:
            locations = []
        if not isinstance(locations, list):
            locations = [locations]
        if data_types is None:
            data_types = []
        if not isinstance(data_types, list):
            data_types = [data_types]
        return locations, data_types
