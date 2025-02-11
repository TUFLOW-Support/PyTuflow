from datetime import datetime, timezone
from pathlib import Path
from typing import Union

import pandas as pd

from .helpers.get_standard_data_type_name import get_standard_data_type_name
from .tabular_output import TabularOutput
from pytuflow.tmf import TuflowCrossSection
from pytuflow.util.gis import GISAttributes
from ..pytuflow_types import PathLike, FileTypeError, TimeLike, TuflowPath
from pytuflow.util.logging import get_logger


logger = get_logger()


class CrossSections(TabularOutput):
    """Class for reading TUFLOW cross-section input layers.

    This class does not need to be explicitly closed as it will load the results into memory and closes any open files
    after initialisation.

    Only the attribute information is extracted from the cross-section GIS layer, therefore GDAL is not
    required to be installed to use this class as the supported formats (MIF, SHP, GPKG) all use
    common database formats to store the attribute information.

    Parameters
    ----------
    fpath : :class:`PathLike <pytuflow.pytuflow_types.PathLike>`
        The path to the cross-section GIS Layer (i.e. :code:`1d_xs` layer).

    Raises
    ------
    FileNotFoundError
        Raised if the check file does not exist.
    FileTypeError
        Raises :class:`pytuflow.pytuflow_types.FileTypeError` if the file does not look like a valid check file.
    EOFError
        Raised if the check file is empty or incomplete.

    Examples
    --------
    Load a cross-section layer:

    >>> from pytuflow.outputs import CrossSections
    >>> xs = CrossSections('path/to/1d_xs.shp')


    """

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

        if not self.looks_like_this(self.fpath):
            raise FileTypeError(f'File does not look like a {self.__class__.__name__} file: {fpath}')

        if self.looks_empty(self.fpath):
            raise EOFError(f'File is empty or incomplete: {fpath}')

        self._load()

    @staticmethod
    def looks_like_this(fpath: Path) -> bool:
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
    def looks_empty(fpath: Path) -> bool:
        # docstring inherited
        with GISAttributes(fpath) as attrs:
            return len(list(attrs)) == 0

    def close(self) -> None:
        """Close the result and any open files associated with the result.
        Not required to be called for the INFO output class as all files are closed after initialisation.
        """
        pass  # no files are left open

    def context_filter(self, context: str) -> pd.DataFrame:
        # docstring inherited
        ctx = [x.strip().lower() for x in context.split('/') if x] if context else []

        df = self.objs.copy()
        filtered_something = False

        # type
        possible_types = ['xz', 'hw', 'cs', 'bg', 'lc']
        ctx1 = [x for x in ctx if x in possible_types]
        ctx1 = [x for x in ctx1 if x in df['type'].str.lower().unique()]
        if ctx1:
            filtered_something = True
            df = df[df['type'].str.lower().isin(ctx1)]
            j = len(ctx) - 1
            for i, x in enumerate(reversed(ctx.copy())):
                if x in ctx1:
                    ctx.pop(j - i)

        # ids
        if ctx and not df.empty:
            df1 = df[df['id'].str.lower().isin(ctx)]
            df2 = df[df['source'].str.lower().isin(ctx)]
            df3 = df[df['filename'].str.lower().isin(ctx)]
            df4 = df[df['uid'].str.lower().isin(ctx)]
            df5 = df[df['filepath'].str.lower().isin(ctx)]
            df = pd.DataFrame()
            if not df1.empty:
                df = df1
            if not df2.empty:
                df = pd.concat([df, df2], axis=0) if not df.empty else df2
            if not df3.empty:
                df = pd.concat([df, df3], axis=0) if not df.empty else df3
            if not df4.empty:
                df = pd.concat([df, df4], axis=0) if not df.empty else df4
            if not df5.empty:
                df = pd.concat([df, df5], axis=0) if not df.empty else df5
            if not df.empty:
                j = len(ctx) - 1
                for i, x in enumerate(reversed(ctx.copy())):
                    if (df['id'].str.lower().isin([x.lower()]).any()
                        or df['filename'].str.lower().isin([x.lower()]).any()
                        or df['source'].str.lower().isin([x.lower()]).any()
                        or df['uid'].str.lower().isin([x.lower()]).any()
                        or df['filepath'].str.lower().isin([x.lower()]).any()):
                        ctx.pop(j - i)
                if ctx and not filtered_something:
                    df = pd.DataFrame()

        return df if not df.empty else pd.DataFrame(columns=['id', 'uid', 'type', 'data_type', 'geometry'])

    def times(self, context: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """CrossSections results are static and will not return any times."""
        return []  # data is static - no times exist

    def ids(self, context: str = None) -> list[str]:
        """Returns the IDs within the context from the cross-section layer.

        Available contexts are:

        - :code:`None` - returns all available IDs.
        - :code:`[type]` - returns all IDs of the given type (e.g. :code:`xz`).
        - :code:`[source]` - returns all IDs present in the given source file.

        Parameters
        ----------
        context : str, optional
            The context to filter the IDs by.

        Returns
        -------
        list[str]
            List of IDs.

        Examples
        --------
        Return all the cross-section IDs in the layer:

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
        df = self.context_filter(context)
        return df['id'].unique().tolist()

    def data_types(self, context: str = None) -> list[str]:
        """Returns the cross-section types within the context from the cross-section layer. Types refer to the
        cross-section type e.g. :code:`xz`, :code:`hw`, :code:`cs`, :code:`bg`, :code:`lc`.

        Available contexts are:

        - :code:`None` - returns all available types.
        - :code:`[id]` - returns all types of the given ID.
        - :code:`[source]` - returns all types present in the given source file.

        Parameters
        ----------
        context : str, optional
            The context to filter the types by.

        Returns
        -------
        list[str]
            List of types.

        Examples
        --------
        Return all the cross-section types in the layer:

        >>> xs.data_types()
        ['xz', 'hw']

        If multiple cross-section tables are present in a given CSV file, the cross-section types from a given
        file can be obtained:

        >>> xs.data_types('/path/to/1d_CrossSection.csv')
        ['xz']
        """
        df = self.context_filter(context)
        return df['type'].unique().tolist()

    def section(self, locations: Union[str, list[str]], data_types: Union[str, list[str]] = None,
                time: TimeLike = -1) -> pd.DataFrame:
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
        locations, data_types = self._figure_out_loc_and_data_types(locations, data_types)

        ctx = '/'.join(locations + data_types)
        df = self.context_filter(ctx)

        df1 = pd.DataFrame()
        for i, row in df.iterrows():
            xs = self.cross_sections[row['ind']]
            df2 = xs.df.copy()
            df2.columns = df2.columns.str.lower()
            df2.columns = pd.MultiIndex.from_product([[row['id']], df2.columns])
            df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2

        return df1

    def time_series(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                    time_fmt: str = 'relative') -> pd.DataFrame:
        """Not supported for CrossSection results. Raises a :code:`NotImplementedError`.

        See Also
        --------
        :meth:`has_plotting_capability` : Check if a given output class supports a given plotting capability before
           trying to use it.
        """
        raise NotImplementedError(f'{__class__.__name__} does not support time-series plotting.')

    def curtain(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for CrossSection results. Raises a :code:`NotImplementedError`.

        See Also
        --------
        :meth:`has_plotting_capability` : Check if a given output class supports a given plotting capability before
           trying to use it.
        """
        raise NotImplementedError(f'{__class__.__name__} does not support curtain plotting.')

    def profile(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for CrossSection results. Raises a :code:`NotImplementedError`.

        See Also
        --------
        :meth:`has_plotting_capability` : Check if a given output class supports a given plotting capability before
           trying to use it.
        """
        raise NotImplementedError(f'{__class__.__name__} does not support vertical profile plotting.')

    def _load(self):
        self.name = self.fpath.stem
        with GISAttributes(self.fpath) as attrs:
            self.cross_sections = [TuflowCrossSection(self.fpath.parent, x) for x in attrs]
            _ = [x.load() for x in self.cross_sections]
        self.cross_section_count = len(self.cross_sections)
        self._load_objs()

    def _load_objs(self):
        d = {'id': [], 'filename': [], 'source': [], 'filepath': [], 'type': [], 'uid': [], 'ind': []}
        df = pd.DataFrame(index=[x.source for x in self.cross_sections])
        for i, xs in enumerate(self.cross_sections):
            if df.loc[[xs.source]].shape[0] == 1:
                id_ = Path(xs.source).stem
            else:
                id_ = xs.col1
            d['id'].append(id_)
            d['filename'].append(Path(xs.source).name)
            d['source'].append(xs.source)
            d['filepath'].append(str((self.fpath.parent / xs.source).resolve()))
            d['type'].append(xs.type.lower())
            d['uid'].append(f'{xs.source}:{id_}')
            d['ind'].append(i)
        self.objs = pd.DataFrame(d)

    def _figure_out_loc_and_data_types(self, locations: Union[str, list[str]],
                                       data_types: Union[str, list[str], None]) -> tuple[list[str], list[str]]:
        """Figure out the locations and data types to use."""
        # sort out locations and data types
        if not locations:
            locations = self.ids()
        else:
            locations1 = []
            locations = [locations] if not isinstance(locations, list) else locations
            for loc in locations:
                ids = self.ids(loc)
                if not self.ids(loc):
                    logger.warning(f'HydTablesCheck.section(): Location "{loc}" not found in the output - removing.')
                else:
                    locations1.append(ids[0])
            locations = locations1
            if not locations:
                raise ValueError('No valid locations provided.')

        if not data_types:
            data_types = self.data_types()
        else:
            data_types = [data_types] if not isinstance(data_types, list) else data_types
            valid_types = self.data_types()
            data_types1 = []
            for dtype in data_types:
                stndname = get_standard_data_type_name(dtype)
                if stndname not in valid_types:
                    logger.warning(
                        f'HydTablesCheck.section(): Data type "{dtype}" is not a valid section data type or '
                        f'not in output - removing.'
                    )
                else:
                    data_types1.append(stndname)
            if not data_types1:
                raise ValueError('No valid data types provided.')
            data_types = data_types1

        return locations, data_types
