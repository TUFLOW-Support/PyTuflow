import re
import typing
from typing import Union

import pandas as pd
from packaging.version import Version

from .gpkg_2d import GPKG2D
from .._pytuflow_types import PathLike, AppendDict, TimeLike

if typing.TYPE_CHECKING:
    from sqlite3 import Cursor


class GPKGRL(GPKG2D):
    """Class for handling RL GeoPackage time series results (:code:`.gpkg` - typically ending with :code:`_RL.gpkg`).
    The GPKG time series format is a specific format published by TUFLOW built on the GeoPackage standard.

    This class can be used to initialise stand-alone GPKG result files, however it is  not required to be used if
    loading GPKG results via the :class:`TPC <pytuflow.outputs.TPC>` class which will load all
    domains automatically (i.e. :code:`GPKG1D`, :code:`GPKG2D`, :code:`GPKGRL`).

    The ``GPKGRL`` class will only load basic properties on initialisation. These are typically properties
    that are easy to obtain from the file without having to load any of the time-series results. Once a method
    requiring more detailed information is called, the full results will be loaded. This makes the ``GPKGRL`` class
    very cheap to initialise.

    Parameters
    ----------
    fpath : PathLike
        The path to the output (.gpkg) file.

    Raises
    ------
    ResultTypeError
        Raises :class:`pytuflow.results.ResultTypeError` if the file does not look like a ``GPKGRL`` file.

    Examples
    --------
    >>> from pytuflow import GPKGRL
    >>> res = GPKGRL('path/to/GPKG_RL.gpkg')

    Querying all the available data types:

    >>> res.data_types()
    ['flow', 'water level', 'volume']

    Querying all RL IDs:

    >>> res.ids()
    ['rl_point', 'rl_line', 'rl_poly']

    Getting the water level time series from the RL point :code:`rl_point`:

    >>> res.time_series('rl_point', 'water level')
    time      rl/water level/rl_point
    0.000000                      NaN
    0.016667                      NaN
    0.033333                      NaN
    0.050000                      NaN
    0.066667                      NaN
    ...                           ...
    2.933333                   40.147
    2.950000                   40.133
    2.966667                   40.116
    2.983334                   40.101
    3.000000                   40.084
    """

    DOMAIN_TYPES = {'rl': ['rl', '0d']}
    GEOMETRY_TYPES = {'point': ['point'], 'line': ['line'], 'polygon': ['polygon', 'region']}
    ATTRIBUTE_TYPES = {}
    ID_COLUMNS = ['id']

    def __init__(self, fpath: PathLike):
        # private
        self._time_series_data_rl = AppendDict()
        self._maximum_data_rl = AppendDict()

        super().__init__(fpath)

    @staticmethod
    def _looks_like_this(fpath: PathLike) -> bool:
        # docstring inherited
        import sqlite3
        # noinspection PyBroadException
        try:
            conn = sqlite3.connect(fpath)
        except Exception:
            return False
        # noinspection PyBroadException
        try:
            cur = conn.cursor()
            cur.execute('SELECT Version FROM TUFLOW_timeseries_version;')
            version = Version(cur.fetchone()[0])
            if version == Version('1.0'):
                # noinspection PyUnusedLocal
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
                    # noinspection PyUnusedLocal
                    valid = True
        except Exception:
            valid = False
        finally:
            conn.close()

        return valid

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns all the available times for the given filter.

        The ``filter_by`` is an optional argument that can be used to filter the return further.Available filters
        for the ``GPKGRL`` class are:

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
        >>> res = GPKGRL('/path/to/plot_results_RL.gpkg')
        >>> res.times()
        [0.0, 0.016666666666666666, ..., 3.0]
        >>> res.times(fmt='absolute')
        [Timestamp('2021-01-01 00:00:00'), Timestamp('2021-01-01 00:01:00'), ..., Timestamp('2021-01-01 03:00:00')]
        """
        return super().times(filter_by, fmt)

    def ids(self, filter_by: str = None) -> list[str]:
        """Returns all the available IDs for the given filter.

        The ``filter_by`` argument can be used to add a filter to the returned IDs. Available filters for the
        ``GPKGRL`` class are:

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

        >>> res = GPKGRL('/path/to/plot_results_RL.gpkg')
        >>> res.ids()
        ['rl_point', 'rl_line', 'rl_polygon']

        Return only line IDs:

        >>> res.ids('line')
        ['rl_line']

        Return IDs that have water level results:

        >>> res.ids('h')
        ['rl_point']
        """
        return super().ids(filter_by)

    def data_types(self, filter_by: str = None) -> list[str]:
        """Returns all the available data types (result types) for the given filter.

        The ``filter_by`` is an optional input that can be used to filter the return further. Available
        filters for the ``GPKGRL`` class are:

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

        >>> res = GPKGRL('/path/to/plot_results_RL.gpkg')
        >>> res.data_types()
        ['water level', 'flow']

        Returning only the :code:`point` data types:

        >>> res.data_types('point')
        ['water level']

        Return only data types for the channel :code:`FC01.1_R`:

        >>> res.data_types('rl_point')
        ['water level']
        """
        return super().data_types(filter_by)

    def maximum(self, locations: str | list[str] | None, data_types: str | list[str] | None,
                time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a DataFrame containing the maximum values for the given data types. The returned DataFrame
        will include time of maximum results as well.

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can also be a filter string, e.g. :code:`line` to extract the maximum values for all
        line geometries. The following filters are available for the ``GPKGRL`` class:

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

        >>> res = GPKGRL('/path/to/plot_results_RL.gpkg')
        >>> res.maximum('rl_line', 'flow')
                  rl/flow/max       rl/flow/tmax
        ds1            59.423           1.383333
        """
        ctx, locations, data_types = self._time_series_filter_by(locations, data_types)
        if ctx.empty:
            return pd.DataFrame()

        # 2D
        return self._append_maximum_2d('rl', self._maximum_data_rl, pd.DataFrame(), ctx, data_types,
                                       time_fmt, self.reference_time)

    def time_series(self, locations: str | list[str] | None, data_types: str | list[str] | None,
                    time_fmt: str = 'relative', *args, **kwargs) -> pd.DataFrame:
        """Returns a time-series DataFrame for the given location(s) and data type(s).

        It's possible to pass in a well known shorthand for the data type e.g. :code:`q` for :code:`flow`.

        The location can also be a filter string, e.g. :code:`line` to extract the time-series values for all
        line geometry types. The following filters are available for the ``GPKGRL`` class:

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

        >>> res = GPKGRL('/path/to/plot_results_RL.gpkg')
        >>> res.time_series('rl_line', 'q')
        Time (h)        rl/q/ds1
        0.000000           0.000
        0.016667           0.000
        ...                  ...
        2.983334           8.670
        3.000000           8.391
        """
        ctx, locations, data_types = self._time_series_filter_by(locations, data_types)
        if ctx.empty:
            return pd.DataFrame()

        share_idx = ctx[['start', 'end', 'dt']].drop_duplicates().shape[0] < 2

        return self._append_time_series_2d('rl', self._time_series_data_rl, pd.DataFrame(), ctx, data_types,
                                           time_fmt, share_idx, self.reference_time)

        # df = self._time_series_extractor(ctx[ctx['domain'] == 'rl'].data_type.unique(), data_types,
        #                                  self._time_series_data_rl, ctx, time_fmt, share_idx, self.reference_time)
        # df.columns = ['{0}/rl/{1}/{2}'.format(*x.split('/')) if x.split('/')[0] == 'time' else f'rl/{x}' for x in
        #               df.columns]
        # return df

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike, *args, **kwargs) -> pd.DataFrame:
        """Not supported for ``GPKGRL`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} files do not support section plotting.')

    def curtain(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``GPKGRL`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} files do not support curtain plotting.')

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike, **kwargs) -> pd.DataFrame:
        """Not supported for ``GPKGRL`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} files do not support vertical profile plotting.')

    def _initial_load(self):
        super()._initial_load()
        self.name = re.sub(r'_TS_RL$', '', self.fpath.stem)

    def _load(self):
        if self._loaded:
            return

        with self.connect(self.fpath) as conn:
            cur = conn.cursor()
            self._load_time_series(cur, self._time_series_data_rl)
            self._load_maximums(self._time_series_data_rl, self._maximum_data_rl)
            self._load_rl_info(cur)

        self._loaded = True

    def _overview_dataframe(self) -> pd.DataFrame:
        df = self.rl_objs.copy()
        df['domain'] = 'rl'
        return df

    def _load_rl_info(self, cur: 'Cursor'):
        self.rl_objs = self._load_info_2d(cur, self._time_series_data_rl)
