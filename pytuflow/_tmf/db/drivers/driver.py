try:
    import pandas as pd
except ImportError:
    from ...stubs import pandas as pd

import logging
from ...tmf_types import PathLike


logger = logging.getLogger('pytuflow')


class DatabaseDriver:
    """Base class for database format drivers. This class is responsible for parsing different database formats
    e.g. CSV files.
    """
    def __init__(self):
        self.fpath = None

    def __repr__(self) -> str:
        """Return a string representation of the driver."""
        return f'<{self.__class__.__name__} {self.fpath}>'

    def test_is_self(self, path: PathLike) -> bool:
        """Test if the database driver looks like the correct driver for the file.

        Parameters
        ----------
        path : PathLike
            The file path to the database file.

        Returns
        -------
        bool
            True if the driver is the correct driver for the file, False otherwise.
        """
        logger.error('_test method must be implemented by driver class')
        raise NotImplementedError

    def name(self) -> str:
        """Return the name of the driver.

        Returns
        -------
        str
            The name of the driver.
        """
        return ''

    def load(self, path: PathLike, header_kwargs: dict, index_col: int | bool, *args, **kwargs) -> pd.DataFrame:
        """Load the database file.

        Parameters
        ----------
        path : PathLike
            The file path to the database file.
        header_kwargs : dict
            **kwargs for DataFrame header that can be passed into pd.load_csv().
        index_col : int | bool
            The column to use as the row labels. If False, nothing is used.
        """
        logger.error('load method must be implemented by driver class')
        raise NotImplementedError
