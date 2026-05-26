import logging
import typing
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .. import const
from ..db.drivers.driver import DatabaseDriver
from .drivers.get_database_driver_class import get_database_driver_class
from ..scope import ScopeList
from ..tmf_types import PathLike
from ..abc.bld_state import BuildState
from ..abc.db import Database

from ..settings import TCFConfig
from .db_entry import DBEntry
from ..tfstrings.increment_number import increment_fpath
from ..misc.dataframe_wrapper import DataFrameWrapper
from ..inp.altered_input import AlteredInputs
from ..context import Context
from ..tfpathlib import TuflowPath

if TYPE_CHECKING:
    # noinspection PyUnusedImports
    from ..abc.cf import ControlFile
    from .db_run_state import DatabaseRunState
    # noinspection PyUnusedImports
    from ..cf.cf_run_state import ControlFileRunState

logger = logging.getLogger('pytuflow')


class DatabaseBuildState(BuildState, Database):
    """Abstract class for storing database information when the model is in the build state.

    Parameters
    ----------
    fpath : PathLike, optional
        Path to the database file. If no path is provided, an empty database will be created.
    config : TCFConfig, optional
        Configuration object for the TUFLOW control file. This is used to store configuration settings
    parent: ControlFile, optional
        Parent control file that this database belongs to.
    scope : ScopeList, optional
        A list of scope objects that will be inherited by the control file itself. Not currently used
        but reserved in case this is useful information in the future.
    driver : tye[DatabaseDriver], optional
        A driver class that can be used to load the database file. If not provided, the driver
        will be guessed based on file extension and content.
    """
    TUFLOW_TYPE = const.DB.DATABASE
    INDEX_COL = 0
    SOURCE_INDEX = -1
    VALUE_INDEX = -1
    TIME_INDEX = -1

    def __init__(self,
                 fpath: PathLike | None = None,
                 config: TCFConfig = None,
                 parent: 'ControlFile' = None,
                 scope: ScopeList = None,
                 driver: type[DatabaseDriver] = None):
        super().__init__()
        #: Path: Path to the database file.
        self.fpath = Path(fpath).resolve() if fpath is not None else None
        #: ControlFile: Parent control that this database belongs to.
        self.parent = parent
        #: TCFConfig: Configuration object for the TUFLOW control file.
        self.config = TCFConfig.from_tcf_config(config) if config is not None else TCFConfig()
        #: AlteredInputs: a list of all changes made to the control file since the last write
        self.altered_inputs = AlteredInputs()
        #: bool: whether the database has been loaded from disk or not.
        self.loaded = False

        self._df = pd.DataFrame()
        self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=self._df.copy())

        self._scope = scope
        self._driver_cls = driver
        self._driver = DatabaseDriver()

        self._dirty = False

        self._header_row = 0

        if not hasattr(self, '_remove_comments'):
            self._remove_comments = True

        if fpath:
            try:
                self._load(self.fpath)
                self.loaded = True
                logger.info('Database file loaded at: {}'.format(fpath))
            except FileNotFoundError:
                logger.warning('Database file could not be found at: {}'.format(fpath))

    def __repr__(self):
        if self.fpath:
            if self.loaded:
                return '<{0}> {1}'.format(self.__class__.__name__, self.fpath.name)
            else:
                return '<{0}> {1} (not found)'.format(self.__class__.__name__, self.fpath.name)
        else:
            return '<{0}> (empty)'.format(self.__class__.__name__)

    @property
    def df(self) -> pd.DataFrame:
        return Database.df.fget(self)

    @df.setter
    def df(self, value: pd.DataFrame):
        if self._df.equals(value):
            return
        self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=value.copy())
        self.record_change()

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> 'DatabaseRunState':
        # docstring inherited
        from .db_run_state import DatabaseRunState
        ctx = context if context else Context(run_context, config=self.config)
        return DatabaseRunState(self, ctx, parent)

    def record_change(self):
        self.entries.clear()
        self._load_from_df(self._df_wrapped)
        self.dirty = True
        self.tcf.altered_inputs.add(self, -1, -1, uuid4(), 'database', self._df)
        self._df = pd.DataFrame(data=self._df_wrapped.copy())

    def undo(self):
        return self.tcf.altered_inputs.undo(self, False)

    def value(self, item: str | int) -> typing.Any:
        # docstring inherited
        if item not in self:
            logger.error(f'Item {item} not found in database')
            raise KeyError(f'Item {item} not found in database')
        try:
            db_ctx = self.context()
        except Exception as e:
            raise ValueError('Database requires a context to resolve value.') from e
        return db_ctx.value(item)

    def write(self, inc: str) -> 'DatabaseBuildState':
        """Write the object to file. From the TCF class, other control files will also be written if
        their ``dirty`` attribute is returned as ``True``.

        Parameters
        ----------
        inc : str, optional
            The increment method to use. The options are:

            * ``"auto"`` - (default) automatically increment the file name by adding +1 to the number at the end of the file name.
              If the file name does not contain a number, it will be added as "001". The increment number from the
              calling class will be used when writing children. E.g. if the TCF is automatically incremented to
              "100", the TGC increment number will be set to "100" regardless of the current number
              in the TGC file name.
            * ``[str]`` - a user defined suffix to add to the file name. This will replace the existing suffix number if
              the user provides a string representation of a number, otherwise it will be appended to the end of
              the file name.
            * ``"inplace"`` - overwrites the existing file without changing the file name. If called from the TCF,
              the children control files and databases can still be incremented up to the TCF increment number.
            * ``None`` - if set to None, no incrementing will take place and the file will be written without
               changing the file name, including children control files and databases. This is very similar
               to the "inplace" option, but will not increment the file name of children control files and databases.

        Returns
        -------
        DatabaseBuildState
            The control file that was written.
        """
        if self.fpath is None or self.fpath == Path():
            logger.error('Database file path is not set. Please provide a valid file path before calling write.')
            raise ValueError('Database file path is not set. Please provide a valid file path before calling write.')
        fpath = increment_fpath(self.fpath, inc)
        if not fpath.parent.exists():
            logger.info('Creating parent directory for database file: {}'.format(fpath.parent))
            fpath.mkdir(parents=True)
        self._df.to_csv(fpath)
        self.fpath = fpath
        self._dirty = False
        return self

    def _find_header_row_end(self, fpath: Path) -> dict:
        return {'header': 0}

    def _load(self, fpath: Path):
        """Loads database from path. Child subclasses should override this method and assign "_head_index" and "_index_col"
        properties before calling this method.

        Parameters
        ----------
        fpath : Path
            Path to the database file.
        """
        if not TuflowPath(fpath).exists():
            raise FileNotFoundError

        if self._driver_cls is not None:
            if not isinstance(self._driver, type):
                raise TypeError('driver argument must be of type DatabaseDriver and not an instance of the class DatabaseDriver')
        else:
            self._driver_cls = get_database_driver_class(fpath)
        self._driver = self._driver_cls()
        if not self._driver.name():
            logger.error(f'Database driver for {fpath} could not be determined or is not implemented yet.')
            raise NotImplementedError(f'Database driver for {fpath} could not be determined or is not implemented yet.')

        self._header_row = self._find_header_row_end(self.fpath)
        self._df = self._driver.load(fpath, self._header_row, self.INDEX_COL, remove_comments=self._remove_comments)
        self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=self._df.copy())
        self._load_from_df(self._df)

    def entry_class(self) -> type[DBEntry]:
        """no-doc"""
        return DBEntry

    def _load_from_df(self, df: pd.DataFrame):
        for index, row in df.iterrows():
            self.entries[index] = self.entry_class()(index, row.tolist(), self.config, self)
