import re
from pathlib import Path
from typing import Union
import typing

import numpy as np
import pandas as pd
from packaging.version import Version

from pytuflow._outputs.gpkg_base import GPKGBase
from pytuflow._outputs.time_series import TimeSeries
from pytuflow._outputs.itime_series_2d import ITimeSeries2D
from pytuflow.pytuflow_types import PathLike, AppendDict, FileTypeError, TimeLike, TuflowPath

if typing.TYPE_CHECKING:
    from sqlite3 import Cursor


class GPKG2D(TimeSeries, ITimeSeries2D, GPKGBase):
    """Class for handling 2D GeoPackage time series results (:code:`.gpkg` - typically ending with :code:`_2D.gpkg`).
    The GPKG time series format is a specific format published by TUFLOW built on the GeoPackage standard.

    This class can be used to initialise stand-alone GPKG result files, however it is  not required to be used if
    loading GPKG results via the :class:`TPC <pytuflow.outputs.TPC>` class which will load all
    domains automatically (i.e. :code:`GPKG1D`, :code:`GPKG2D`, :code:`GPKGRL`).

    The ``GPKG2D`` class will only load basic properties on initialisation. These are typically properties
    that are easy to obtain from the file without having to load any of the time-series results. Once a method
    requiring more detailed information is called, the full results will be loaded. This makes the ``GPKG2D`` class
    very cheap to initialise.

    Parameters
    ----------
    fpath : PathLike
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
    >>> from pytuflow.outputs.gpkg_2d import GPKG2D
    >>> res = GPKG2D('path/to/file_2D.gpkg')

    Querying all the available data types:

    >>> res.data_types()
    ['flow', 'velocity', 'water level']

    Querying all PO line data types:

    >>> res.data_types('line')
    ['flow']

    Querying all PO IDs:

    >>> res.ids()
    ['po_point', 'po_line']

    Querying all PO point IDs:

    >>> res.ids('point')
    ['po_point']

    Getting the water level time series from the PO point :code:`po_point`:

    >>> res.time_series('po_point', 'water level')
    time      po/water level/po_point
    0.000000                   39.073
    0.016667                   39.073
    0.033333                   39.073
    0.050000                   39.073
    0.066667                   39.073
    ...                           ...
    2.933333                   40.566
    2.950000                   40.546
    2.966667                   40.526
    2.983333                   40.506
    3.000000                   40.485
    """

    def __init__(self, fpath: PathLike):
        super().__init__(fpath)

        #: Path: The path to the source output file.
        self.fpath = Path(fpath)
        #: str: The unit system used in the output file.
        self.units = 'si'
        #: Version: the format version
        self.format_version = None

        if not self.fpath.exists():
            raise FileNotFoundError(f'File not found: {self.fpath}')

        # call before tpc_reader is initialised to give a clear error message if it isn't actually a .info time series file
        if not self._looks_like_this(self.fpath):
            raise FileTypeError(f'File does not look like a time series {self.__class__.__name__} file: {fpath}')

        # call after tpc_reader has been initialised so that we know the file can be loaded by the reader
        if self._looks_empty(fpath):
            raise EOFError(f'File is empty or incomplete: {fpath}')

        # private
        self._time_series_data_2d = AppendDict()
        self._maximum_data_2d = AppendDict()
        self._geoms = AppendDict()
        self._gis_layer_p_name = None
        self._gis_layer_l_name = None
        self._gis_layer_r_name = None

        self._loaded = False
        self._initial_load()

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

        The ``filter_by`` is an optional argument that can be used to filter the return further.Available filters
        for the ``GPKG2D`` class are:

        * :code:`None`: default - returns all available times
        * :code:`point`:
        * :code:`line`:
        * :code:`polygon`: (or :code:`region`)
        * :code:`[id]`: returns only data types for the given ID.
        * :code:`[data_type]`: returns only data types for the given data type. Shorthand data type names can be used.

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
        self._load()
        return super().times(filter_by, fmt)

    def ids(self, filter_by: str = None) -> list[str]:
        """Returns all the available IDs for the given filter.

        The ``filter_by`` argument can be used to add a filter to the returned IDs. Available filters for the
        ``GPKG2D`` class are:

        * :code:`None`: default - returns all available times
        * :code:`point`:
        * :code:`line`:
        * :code:`polygon`: (or :code:`region`)
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
        ['po_point', 'po_line', 'po_polygon']

        Return only line IDs:

        >>> res.ids('line')
        ['po_line']

        Return IDs that have water level results:

        >>> res.ids('h')
        ['po_point']
        """
        self._load()
        return super().ids(filter_by)

    def data_types(self, filter_by: str = None) -> list[str]:
        """Returns all the available data types (result types) for the given filter.

        The ``filter_by`` is an optional input that can be used to filter the return further. Available
        filters for the ``GPKG2D`` class are:

        * :code:`None`: default - returns all available times
        * :code:`point`:
        * :code:`line`:
        * :code:`polygon`: (or :code:`region`)
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
        The below examples demonstrate how to use the ``filter_by`` argument to filter the returned data types.
        The first example returns all data types:

        >>> res.data_types()
        ['water level', 'flow', 'velocity']

        Returning only the :code:`point` data types:

        >>> res.data_types('point')
        ['water level', 'velocity']

        Return only data types for the channel :code:`FC01.1_R`:

        >>> res.data_types('po_point')
        ['water level']
        """
        self._load()
        return super().data_types(filter_by)

    def maximum(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a DataFrame containing the maximum values for the given data types. The returned DataFrame
        will include time of maximum results as well.

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can also be a filter string, e.g. :code:`line` to extract the maximum values for all
        line geometries. The following filters are available for the ``GPKG2D`` class:

        * :code:`None`: default - returns all available times
        * :code:`point`:
        * :code:`line`:
        * :code:`polygon`: (or :code:`region`)

        The returned DataFrame will have an index column corresponding to the location IDs, and the columns
        will be in the format :code:`obj/data_type/[max|tmax]`,
        e.g. :code:`po/flow/max`, :code:`po/flow/tmax`

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
        Extracting the maximum flow for a given location:

        >>> res.maximum('po_line', 'flow')
                  po/flow/max       po/flow/tmax
        ds1            59.423           1.383333
        """
        self._load()
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        filter_by = '/'.join(locations + data_types)
        ctx = self._filter(filter_by)
        if ctx.empty:
            return pd.DataFrame()

        df = self._maximum_extractor(ctx[ctx['domain'] == '2d'].data_type.unique(), data_types,
                                     self._maximum_data_2d, ctx, time_fmt, self.reference_time)
        df.columns = [f'po/{x}' for x in df.columns]
        return df

    def time_series(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                    time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a time-series DataFrame for the given location(s) and data type(s).

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can also be a filter string, e.g. :code:`line` to extract the time-series values for all
        line geometry types. The following filters are available for the ``GPKG2D`` class:

        * :code:`None`: default - returns all available times
        * :code:`point`:
        * :code:`line`:
        * :code:`polygon`: (or :code:`region`)

        The returned column names will be in the format :code:`obj/data_type/location`
        e.g. :code:`po/flow/FC01.1_R`. The :code:`data_type` name in the column heading will be identical to the
        data type  name passed into the function e.g. if :code:`h` is used instead of :code:`water level`, then the
        return will be :code:`po/h/FC01.1_R.1`.

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
        Extracting flow for a given line.

        >>> res.time_series('po_line', 'q')
        Time (h)        po/q/ds1
        0.000000           0.000
        0.016667           0.000
        ...                  ...
        2.983334           8.670
        3.000000           8.391
        """
        self._load()
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        filter_by = '/'.join(locations + data_types)
        ctx = self._filter(filter_by)
        if ctx.empty:
            return pd.DataFrame()

        share_idx = ctx[['start', 'end', 'dt']].drop_duplicates().shape[0] < 2
        df = self._time_series_extractor(ctx[ctx['domain'] == '2d'].data_type.unique(), data_types,
                                         self._time_series_data_2d, ctx, time_fmt, share_idx, self.reference_time)
        df.columns = ['{0}/po/{1}/{2}'.format(*x.split('/')) if x.split('/')[0] == 'time' else f'po/{x}' for x in
                      df.columns]
        return df

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``GPKG2D`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} files do not support section plotting.')

    def curtain(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``GPKG2D`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} files do not support curtain plotting.')

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``GPKG2D`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} files do not support vertical profile plotting.')

    def _initial_load(self):
        self.name = re.sub(r'_TS_2D$', '', self.fpath.stem)
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute('SELECT Version FROM TUFLOW_timeseries_version;')
            self.format_version = Version(cur.fetchone()[0])

            reference_time = None
            cur.execute(
                'SELECT DISTINCT Table_name, Count, Series_name, Series_units, Reference_time FROM Timeseries_info;')
            for table_name, count, series_name, units, rt in cur.fetchall():
                if reference_time is None:
                    reference_time, _ = self._parse_time_units_string(rt, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
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

    def _load(self):
        if self._loaded:
            return

        with self._connect() as conn:
            cur = conn.cursor()
            self._load_time_series(cur, self._time_series_data_2d)
            self._load_maximums(self._time_series_data_2d, self._maximum_data_2d)
            self._load_po_info(cur)

        self._loaded = True

    def _filter(self, filter_by: str) -> pd.DataFrame:
        # docstring inherited
        # split filter into components
        filter_by = [x.strip().lower() for x in filter_by.split('/')] if filter_by else []
        return super()._combinations_2d(filter_by)

    def _load_time_series(self, cur: 'Cursor', storage: AppendDict):
        if self._gis_layer_p_name:
            cur.execute(f'SELECT Column_name FROM Timeseries_info WHERE Table_name = "{self._gis_layer_p_name}";')
            data_types = [row[0] for row in cur.fetchall()]
            for dtype in data_types:
                dtype1 = self._get_standard_data_type_name(dtype)
                storage[dtype1] = self._gpkg_time_series_extractor(cur, dtype, self._gis_layer_p_name)
                self._geoms[dtype1] = 'point'

        if self._gis_layer_l_name:
            cur.execute(f'SELECT Column_name FROM Timeseries_info WHERE Table_name = "{self._gis_layer_l_name}";')
            data_types = [row[0] for row in cur.fetchall()]
            for dtype in data_types:
                dtype1 = self._get_standard_data_type_name(dtype)
                storage[dtype1] = self._gpkg_time_series_extractor(cur, dtype, self._gis_layer_l_name)
                self._geoms[dtype1] = 'line'

        if self._gis_layer_r_name:
            cur.execute(f'SELECT Column_name FROM Timeseries_info WHERE Table_name = "{self._gis_layer_r_name}";')
            data_types = [row[0] for row in cur.fetchall()]
            for dtype in data_types:
                dtype1 = 'max water level' if dtype.lower() == 'max water level' else self._get_standard_data_type_name(dtype)
                storage[dtype1] = self._gpkg_time_series_extractor(cur, dtype, self._gis_layer_r_name)
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

        self._po_objs = pd.DataFrame(po_info)

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
