import typing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .tabular_output import TabularOutput
from .._tmf import FmCrossSectionDatabaseDriver
from .._pytuflow_types import PathLike, TimeLike, TuflowPath
from ..results import ResultTypeError

if typing.TYPE_CHECKING:
    from .._fm import Handler


class DATCrossSections(TabularOutput):
    """Class for reading Flood Modeller cross-sections from the .dat format.

    Parameters
    ----------
    fpath : PathLike
        The path to the ``.dat`` file.

    Raises
    ------
    ResultTypeError
        Raises :class:`pytuflow.results.ResultTypeError` if the file does not look like a Flood Modeller ``.dat`` file.

    Examples
    --------
    Load a cross-section layer:

    >>> from pytuflow import DATCrossSections
    >>> xs = DATCrossSections('path/to/1d_xs.shp')
    """
    DOMAIN_TYPES = {}
    GEOMETRY_TYPES = {}
    ATTRIBUTE_TYPES = {'xz': ['xz'], 'manning n': ['manning n']}
    ID_COLUMNS = ['name']

    def __init__(self, fpath: PathLike, driver: typing.Any = None):
        super().__init__(fpath)

        self.reference_time = datetime(1990, 1, 1, tzinfo=timezone.utc)
        self.units = ''
        #: TuflowPath: The path to the source output file.
        self.fpath = TuflowPath(fpath)
        #: DataFrame: DataFrame of cross-sections information.
        self.objs = pd.DataFrame(columns=['Name', 'Type'])
        #: int: Number of cross-sections
        self.cross_section_count = 0

        self._driver = FmCrossSectionDatabaseDriver() if driver is None else driver

        if not self.fpath.exists():
            raise FileNotFoundError(f'File does not exist: {fpath}')

        if not self._looks_like_this(self.fpath):
            raise ResultTypeError(f'File does not look like a {self.__class__.__name__} file: {fpath}')

        if self._looks_empty(self.fpath):
            raise EOFError(f'File is empty or incomplete: {fpath}')

        self._load()

    @property
    def cross_sections(self) -> list['Handler']:
        """list[FmCrossSection]: List of loaded cross-sections."""
        return self._driver.cross_sections()

    @staticmethod
    def _looks_like_this(fpath: Path) -> bool:
        return FmCrossSectionDatabaseDriver.test_is_dat(fpath)

    @staticmethod
    def _looks_empty(fpath: PathLike) -> bool:
        try:
            with open(fpath, 'r') as f:
                for line in f:
                    if line.upper().startswith('END GENERAL'):
                        for _ in f:  # check if there is another line
                            return False
        except Exception:
            pass
        return True

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """CrossSections results are static and will not return any times."""
        return []  # data is static - no times exist

    def ids(self, filter_by: str = None) -> list[str]:
        """Returns the IDs from the cross-section layer. The ``filter_by`` argument will not have any affect.

        Parameters
        ----------
        filter_by : str, optional
            Not used by the Flood Modeller cross-section class.

        Returns
        -------
        list[str]
            List of IDs.

        Examples
        --------
        Return all the cross-section IDs in the layer:

        >>> xs = DATCrossSections('/path/to/model.dat')
        >>> xs.ids()
        ['FC01.40', 'FC01.39', 'FC01.38', ..., 'FC02.01', 'FC02.01d']
        """
        if filter_by is not None and filter_by != 'section':
            filter_by = [x.lower() for x in filter_by.split('/') if x.strip()]
            for id_ in filter_by:
                # check if the filter is an ID
                df = self.objs[(self.objs.index.str.lower() == id_.lower()) | (self.objs.name.str.lower() == id_.lower())]
                return df.loc[:,'name'].unique().tolist()
        return self.objs['name'].unique().tolist()

    def data_types(self, filter_by: str = None) -> list[str]:
        """Returns the cross-section types. The ``filter_by`` argument is mostly not used. It can be used to pass
        in a plotting type e.g. ``"timeseries"`` to return an empty list (``"section"`` will return the
        standard types). This is useful if called from an application that wants to check if this result supports a
        given plot type.

        Parameters
        ----------
        filter_by : str, optional
            Mostly not used. It can be used to pass in a plotting type e.g. ``"timeseries"`` to
            return an empty list (``"section"`` will return the standard types). This is useful if called
            from an application that wants to check if this result supports a given plot type.

        Returns
        -------
        list[str]
            List of types.

        Examples
        --------
        Return all the cross-section types in the layer:

        >>> xs = DATCrossSections('/path/to/model.dat')
        >>> xs.data_types()
        ['xz', 'manning n']
        """
        if filter_by is not None and filter_by != 'section':
            filter_by = [x.lower() for x in filter_by.split('/') if x.strip()]
            for id_ in filter_by:
                # check if the filter is an ID
                df = self.objs[(self.objs.index.str.lower() == id_.lower()) | (self.objs.name.str.lower() == id_.lower())]
                if df.empty:
                    return []
        return ['xz', 'manning n']

    def section(self, locations: str | list[str], data_types: str | list[str] = None,
                time: TimeLike = -1, *args, **kwargs) -> pd.DataFrame:
        """Return the cross-section data for given location and cross-section data type.

        The returned dataframe uses a multi-index with the first level being the cross-section ID and the second level
        being the returned data from the cross-section.

        Parameters
        ----------
        locations : str or list[str]
            The cross-section ID(s) to return the data for.
        data_types : str or list[str], optional
            The cross-section data type(s) to return the data for.
        time : TimeLike, optional
            The time to return the data for. Not used for cross-sections.

        Returns
        -------
        pd.DataFrame
            DataFrame of cross-section data.

        Examples
        --------
        Return the cross-section data for a given location and data type:

        >>> xs.section('FC01.08', 'xz')
           FC01.08
                       x        z
        0        0.00000  38.4567
        1        1.16450  38.2227
        2        6.74383  37.4142
        3        6.74534  37.4140
        4        7.58031  36.8805
        ...        ...        ...
        24      40.88000  37.6529
        25      41.44690  37.6526
        26      42.39770  37.6635
        27      43.05550  37.6766
        28      44.40290  37.7324
        """
        locs_original = [locations] if isinstance(locations, str) else locations.copy()
        df, locations, data_types = self._time_series_filter_by(locations, data_types)
        if df.empty:
            return pd.DataFrame()

        df1 = pd.DataFrame()
        for idx, row in df.iterrows():
            uid = str(idx)
            name = row['name']
            xs = self._driver.dat.unit(uid)
            df = xs.df.loc[:,['x', 'y', 'n']]
            df.columns = ['x', 'z', 'manning n']
            cols = []
            if 'xz' in data_types:
                cols = ['x', 'z']
            if 'manning n' in data_types:
                cols = ['x', 'z', 'manning n'] if 'xz' in data_types else ['x', 'manning n']
            df2 = df.loc[:,cols]
            orig_name = uid if uid.lower() in [x.lower() for x in locs_original] else name
            df2.columns = pd.MultiIndex.from_product([[orig_name], df2.columns])
            df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2

        return df1

    def time_series(self, locations: str | list[str] | None, data_types: str | list[str] | None,
                    time_fmt: str = 'relative', *args, **kwargs) -> pd.DataFrame:
        """Not supported for ``CrossSection`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support time-series plotting.')

    def curtain(self, locations: typing.Union[str, list[str]], data_types: typing.Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``CrossSection`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support curtain plotting.')

    def profile(self, locations: typing.Union[str, list[str]], data_types: typing.Union[str, list[str]],
                time: TimeLike, **kwargs) -> pd.DataFrame:
        """Not supported for ``CrossSection`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support vertical profile plotting.')

    def _load(self):
        if self._loaded:
            return
        self.name = self.fpath.stem
        self.objs = self._driver.load(self.fpath)
        self.objs.columns = self.objs.columns.str.lower()
        self.objs['domain'] = '1d'
        self.objs['type'] = 'xz'
        df = pd.DataFrame(self.objs.loc[:, ['name', 'domain']].to_numpy(), index=self.objs.index, columns=['name', 'domain'])
        df['type'] = 'manning n'
        self.objs = pd.concat([self.objs, df], axis=0)
        self.cross_section_count = self.objs.shape[0] // 2
        self._loaded = True

    def _overview_dataframe(self) -> pd.DataFrame:
        return self.objs
