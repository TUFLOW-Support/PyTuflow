from pathlib import Path

from .xsdb import XsDatabaseDriver
from ...tmf_types import PathLike


class MikeCrossSectionDatabaseDriver(XsDatabaseDriver):
    """Mike11 cross-section database driver.

    .. note::

        This driver is not implemented yet.
    """

    def test_is_self(self, path: PathLike) -> bool:
        # docstring inherited
        return Path(path).suffix.lower() == '.txt'

    def name(self) -> str:
        # docstring inherited
        return 'mike11_cross_section'

    def load(self, path: PathLike, *args, **kwargs):
        # docstring inherited
        # logging handled by caller
        raise NotImplementedError('Mike11 cross-section database not implemented yet')
