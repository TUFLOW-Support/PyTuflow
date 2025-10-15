from datetime import datetime, timezone
from pathlib import Path
from typing import Union

import pandas as pd

from .tabular_output import TabularOutput
from .._tmf import TuflowCrossSection
from .._tmf import GISAttributes
from ..util import pytuflow_logging
from .._pytuflow_types import PathLike, TimeLike, TuflowPath
from ..results import ResultTypeError


logger = pytuflow_logging.get_logger()


class CrossSections(TabularOutput):
    """Class for reading TUFLOW cross-section input layers.

    This class does not need to be explicitly closed as it will load the results into memory and closes any open files
    after initialisation.

    Only the attribute information is extracted from the cross-section GIS layer, therefore GDAL is not
    required to be installed to use this class as the supported formats (MIF, SHP, GPKG) all use
    common database formats to store the attribute information.

    Parameters
    ----------
    fpath : PathLike
        The path to the cross-section GIS Layer (i.e. :code:`1d_xs` layer).

    Raises
    ------
    ResultTypeError
        Raises :class:`pytuflow.results.ResultTypeError` if the file does not look like a ``CrossSection`` file.

    Examples
    --------
    Load a cross-section layer:

    >>> from pytuflow import CrossSections
    >>> xs = CrossSections('path/to/1d_xs.shp')
    """

    DOMAIN_TYPES = {}
    GEOMETRY_TYPES = {}
    ATTRIBUTE_TYPES = {'xz': ['xz'], 'hw': ['hw'], 'cs': ['cs'], 'bg': ['bg'], 'lc': ['lc'], 'na': ['na']}
    ID_COLUMNS = ['id', 'uid', 'source', 'filename', 'filepath']

    def __init__(self, fpath: PathLike):
        super().__init__(fpath)

        self.reference_time = datetime(2000, 1, 1, tzinfo=timezone.utc)
        self.units = ''
        #: TuflowPath: The path to the source output file.
        self.fpath = TuflowPath(fpath)
        #: List: List of loaded cross-sections.
        self.cross_sections = []
        #: DataFrame: DataFrame of cross-sections information.
        self.objs = pd.DataFrame()
        #: int: Number of cross-sections
        self.cross_section_count = 0

        if not self.fpath.exists():
            raise FileNotFoundError(f'File does not exist: {fpath}')

        if not self._looks_like_this(self.fpath):
            raise ResultTypeError(f'File does not look like a {self.__class__.__name__} file: {fpath}')

        if self._looks_empty(self.fpath):
            raise EOFError(f'File is empty or incomplete: {fpath}')

        self._load()

    @staticmethod
    def _looks_like_this(fpath: Path) -> bool:
        # docstring inherited
        try:
            with GISAttributes(fpath) as attrs:
                for attr in attrs:
                    field_names = [x.lower() for x in attr.keys()]
                    return len(field_names) >= 9 and field_names[:10] != ['source', 'type', 'flags', 'column_1',
                                                                         'column_2', 'column_3', 'column_4', 'column_5',
                                                                         'column_6']
        except NotImplementedError:
            return False

        return True

    @staticmethod
    def _looks_empty(fpath: Path) -> bool:
        # docstring inherited
        with GISAttributes(fpath) as attrs:
            return len(list(attrs)) == 0

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """CrossSections results are static and will not return any times."""
        return []  # data is static - no times exist

    def ids(self, filter_by: str = None) -> list[str]:
        """Returns the IDs within the filter from the cross-section layer.

        Available filters are:

        - :code:`None` - returns all available IDs.
        - :code:`[type]` - returns all IDs of the given type (e.g. :code:`xz`).
        - :code:`[source]` - returns all IDs present in the given source file.

        Parameters
        ----------
        filter_by : str, optional
            The string to filter the IDs by.

        Returns
        -------
        list[str]
            List of IDs.

        Examples
        --------
        Return all the cross-section IDs in the layer:

        >>> xs = CrossSections('/path/to/1d_xs.shp')
        >>> xs.ids()
        ['1d_xs_M14_C99', '1d_xs_M14_C100', '1d_xs_M14_C101', ..., '1d_xs_M14_ds_weir', '1d_xs_M14_rd_weir']

        If multiple cross-section tables are present in a given CSV file, the cross-section IDs from a given
        file can be obtained:

        >>> xs.ids('/path/to/1d_CrossSection.csv')
        ['1d_xs_M14_C99', '1d_xs_M14_C100']

        Return all the cross-section IDs of a given type:

        >>> xs.ids('xz')
        ['1d_xs_M14_C99', '1d_xs_M14_C100', '1d_xs_M14_C101', ..., '1d_xs_M14_ds_weir', '1d_xs_M14_rd_weir']
        """
        df, _ = self._filter(filter_by)
        return df['id'].unique().tolist()

    def data_types(self, filter_by: str = None) -> list[str]:
        """Returns the cross-section types within the filter from the cross-section layer. Types refer to the
        cross-section type e.g. :code:`xz`, :code:`hw`, :code:`cs`, :code:`bg`, :code:`lc`.

        Available filters are:

        - :code:`None` - returns all available types.
        - :code:`[id]` - returns all types of the given ID.
        - :code:`[source]` - returns all types present in the given source file.

        Parameters
        ----------
        filter_by : str, optional
            The string to filter the types by.

        Returns
        -------
        list[str]
            List of types.

        Examples
        --------
        Return all the cross-section types in the layer:

        >>> xs = CrossSections('/path/to/1d_xs.shp')
        >>> xs.data_types()
        ['xz', 'hw']

        If multiple cross-section tables are present in a given CSV file, the cross-section types from a given
        file can be obtained:

        >>> xs.data_types('/path/to/1d_CrossSection.csv')
        ['xz']
        """
        if filter_by is not None and 'section' in filter_by:
            filter_by = filter_by.replace('section', '').strip('/')
            if not filter_by:
                filter_by = None
        df, _ = self._filter(filter_by)
        return df['type'].unique().tolist()

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]] = None,
                time: TimeLike = -1, *args, **kwargs) -> pd.DataFrame:
        """Return the cross-section data for given location and cross-section type.

        The returned dataframe uses a multi-index with the first level being the cross-section ID and the second level
        being the returned data from the cross-section.

        Parameters
        ----------
        locations : str or list[str]
            The cross-section ID(s) to return the data for.
        data_types : str or list[str], optional
            The cross-section type(s) to return the data for.
        time : TimeLike, optional
            The time to return the data for. Not used for cross-sections.

        Returns
        -------
        pd.DataFrame
            DataFrame of cross-section data.

        Examples
        --------
        Return the cross-section data for a given location and cross-section type:

        >>> xs.section('1d_xs_M14_C99')
           1d_xs_M14_C99
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
        def loc(x: str) -> str:
            if '.csv:' in x.lower():
                df_ = self.objs[self.objs['uid'].str.lower() == x.lower()][['id']]
                if not df_.empty:
                    return df_.iloc[0,0]
            elif '.csv' in x.lower():
                df_ = self.objs[self.objs['source'].str.lower() == Path(x).name.lower()][['id']]
                if not df_.empty:
                    return df_.iloc[0,0]
            else:
                df_ = self.objs[self.objs['id'].str.lower() == x.lower()][['id']]
                if not df_.empty:
                    return df_.iloc[0,0]
            return Path(x).stem

        if locations is not None:
            if not isinstance(locations, (list, tuple)):
                locations = [locations]
            locations = [loc(x) for x in locations]
        df, locations, data_types = self._time_series_filter_by(locations, data_types)
        if df.empty:
            return pd.DataFrame()

        df1 = pd.DataFrame()
        for i, row in df.iterrows():
            xs = self.cross_sections[row['ind']]
            df2 = xs.df.copy()
            df2.columns = df2.columns.str.lower()
            df2.columns = pd.MultiIndex.from_product([[row['id']], df2.columns])
            df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2

        return df1

    def time_series(self, locations: str | list[str] | None, data_types: str | list[str] | None,
                    time_fmt: str = 'relative', *args, **kwargs) -> pd.DataFrame:
        """Not supported for ``CrossSection`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support time-series plotting.')

    def curtain(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``CrossSection`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support curtain plotting.')

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike, **kwargs) -> pd.DataFrame:
        """Not supported for ``CrossSection`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support vertical profile plotting.')

    def _load(self):
        if self._loaded:
            return
        self.name = self.fpath.stem
        with GISAttributes(self.fpath) as attrs:
            self.cross_sections = [TuflowCrossSection(self.fpath.parent, x) for x in attrs]
            _ = [x.load() for x in self.cross_sections]
        self.cross_section_count = len(self.cross_sections)
        self._load_objs()
        self._loaded = True

    def _overview_dataframe(self) -> pd.DataFrame:
        df = self.objs.copy()
        df['domain'] = '1d'
        return df

    def _load_objs(self):
        d = {'id': [], 'filename': [], 'source': [], 'filepath': [], 'type': [], 'uid': [], 'ind': []}
        df = pd.DataFrame(index=[x.source for x in self.cross_sections])
        for i, xs in enumerate(self.cross_sections):
            name = xs.col1 if xs.col1 else Path(xs.source).stem
            if df.loc[[xs.source]].shape[0] == 1:
                id_ = Path(xs.source).stem
            else:
                id_ = xs.col1
            d['id'].append(id_)
            d['filename'].append(Path(xs.source).name)
            d['source'].append(xs.source)
            d['filepath'].append(str((self.fpath.parent / xs.source).resolve()))
            d['type'].append(xs.type.lower())
            d['uid'].append(f'{xs.source}:{name}')
            d['ind'].append(i)
        self.objs = pd.DataFrame(d)
