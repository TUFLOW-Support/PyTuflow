try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

from .driver import DatabaseDriver
from ...misc.case_insensitive_dict import CaseInsDict


class CrossSectionMixin:

    def __init__(self, *args, **kwargs):
        self._args = args
        self._kwargs = kwargs
        super().__init__(*args, **kwargs)

    def copy(self) -> 'CrossSectionMixin':
        """Create a deep copy of the cross-section. This is so that when a RunState class is created, any changes
        to the cross-section do not affect the original.

        Returns
        -------
        CrossSection
            A deep copy of the cross-section.
        """
        xs = self.__class__(*self._args, **self._kwargs)
        for attr in dir(self):
            if attr.startswith('__'):
                val = getattr(self, attr)
                if callable(val):
                    continue
                if isinstance(val, list):
                    try:
                        val = [x.copy() for x in val]
                    except AttributeError:
                        val = val.copy()
                else:
                    try:
                        val = val.copy()
                    except AttributeError:
                        pass
                setattr(xs, attr, val)
        return xs


class CrossSection(CrossSectionMixin):
    """Abstract base class for storing individual cross-section data."""

    __slots__ = ('_args', '_kwargs', 'fpath', 'name', 'df', 'col_name_x', 'col_name_z', 'col_name_n', 'errors', 'id')

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self._args = args
        self._kwargs = kwargs
        #: Path: The file path to the cross-section data.
        self.fpath = None
        #: str: name of the cross-section
        self.name = None
        #: pd.DataFrame: The cross-section data.
        self.df = pd.DataFrame(columns=['X', 'Z'])
        #: str: The column name within the dataframe for the x values.
        self.col_name_x = None
        #: str: The column name within the dataframe for the z values.
        self.col_name_z = None
        #: str: The column name within the dataframe for the mannings n values.
        self.col_name_n = None
        #: list[str]: A list of errors that occurred when loading the cross-section data.
        self.errors = []
        #: int: The cross-section ID.
        self.id = -1

    def __repr__(self) -> str:
        if self.name:
            return f'<CrossSection {self.name}>'
        return '<CrossSection>'

    @property
    def x(self) -> list[float]:
        #: list[float]: The x values of the cross-section.
        if self.col_name_x is not None and self.col_name_x in self.df.columns:
            return self.df[self.col_name_x].tolist()
        return []

    @property
    def z(self) -> list[float]:
        #: list[float]: The z values of the cross-section.
        if self.col_name_z is not None and self.col_name_z in self.df.columns:
            return self.df[self.col_name_z].tolist()
        return []

    @property
    def n(self) -> list[float]:
        #: list[float]: The mannings n values of the cross-section.
        if self.col_name_n is not None and self.col_name_n in self.df.columns:
            return self.df[self.col_name_n].tolist()
        return []

    def load(self, *args, **kwargs) -> None:
        """Load the cross-section data."""
        raise NotImplementedError('Must be overriden by subclass')

    def write(self, *args, **kwargs) -> None:
        """Write the cross-section data."""
        raise NotImplementedError('Must be overriden by subclass')


class CrossSectionDatabaseDriver(CrossSectionMixin, DatabaseDriver):
    """Abstract base class for handling TUFLOW supported cross-section database formats."""

    def __init__(self, *args, **kwargs):
        super(CrossSectionDatabaseDriver, self).__init__()
        self._args = args
        self._kwargs = kwargs
        #: dict[int, CrossSection]: A dictionary of cross-sections.
        self.cross_sections = {}  # id2cross_section
        #: CaseInsDict: A dictionary of cross-section names to cross-section IDs.
        self.name2id = CaseInsDict()
        #: list[CrossSection]: A list of cross-sections that contain wildcards that need resolving.
        self.unresolved_xs = []  # these are cross-sections that contain wildcards that need resolving
        #: bool: Whether the driver supports separate files.
        self.supports_separate_files = False

    def __repr__(self) -> str:
        return '<CrossSectionDatabaseDriver>'

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def xs_is_valid(self, xsid: int) -> bool:
        """Returns whether a given cross-section is valid.

        Parameters
        ----------
        xsid : int
            The cross-section ID.

        Returns
        -------
        bool
            True if the cross-section is valid, False otherwise.
        """
        return True

    def generate_df(self) -> pd.DataFrame:
        """Generate a DataFrame from the cross-sections.

        Returns
        -------
        pd.DataFrame
            A DataFrame containing the cross-section data.
        """
        df = pd.DataFrame()
        for xs in self.cross_sections.values():
            if self.xs_is_valid(xs.id):
                df_ = xs.df.copy()
                df_.columns = pd.MultiIndex.from_tuples(
                    [(xs.name, xs.type, x) for x in df_.columns],
                    names=['Name', 'Type', 'Header']
                )
                df = pd.concat([df, df_], axis=1) if not df.empty else df_
        return df
