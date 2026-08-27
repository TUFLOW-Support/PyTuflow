from pathlib import Path

from .xs import CrossSectionDatabaseDriver
from ...tmf_types import PathLike


class XsDatabaseDriver(CrossSectionDatabaseDriver):
    """Base class, and entry point, for handling and loading TUFLOW supported cross-section database formats."""

    def __new__(cls, fpath: PathLike) -> object:
        p = Path(fpath)
        if p.suffix.lower() == '.txt':
            from .xsm11 import MikeCrossSectionDatabaseDriver
            cls = MikeCrossSectionDatabaseDriver
        elif p.suffix.lower() == '.dat':
            from .xsdat import FmCrossSectionDatabaseDriver
            cls = FmCrossSectionDatabaseDriver
        elif p.suffix.lower() == '.pro':
            from .xspro import ProCrossSectionDatabaseDriver
            cls = ProCrossSectionDatabaseDriver
        else:
            # logging handled by caller
            raise ValueError(f'Unknown file type: {p.suffix}')
        return object.__new__(cls)

    def __init__(self, fpath: PathLike) -> None:
        """
        Parameters
        ----------
        fpath : PathLike
            The file path to the database file.
        """
        super().__init__(fpath)
        self.fpath = Path(fpath)
