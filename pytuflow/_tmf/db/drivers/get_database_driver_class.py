from pathlib import Path

from .driver import DatabaseDriver
from .csv import CsvDatabaseDriver
from .ts1 import TS1DatabaseDriver
from .xstf import TuflowCrossSectionDatabaseDriver
from .xsdat import FmCrossSectionDatabaseDriver


def get_database_driver_class(fpath: Path) -> type[DatabaseDriver]:
    """Returns the appropriate database driver class for the given file.

    Can be used for both database and the database source files.
    """
    if FmCrossSectionDatabaseDriver.test_is_dat(fpath):
        return FmCrossSectionDatabaseDriver
    if TS1DatabaseDriver.test_is_ts1(fpath):
        return TS1DatabaseDriver
    if CsvDatabaseDriver.test_is_csv(fpath):
        return CsvDatabaseDriver
    if TuflowCrossSectionDatabaseDriver.test_is_tf_xs(fpath):
        return TuflowCrossSectionDatabaseDriver
    return DatabaseDriver
