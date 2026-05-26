import logging
import typing
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from ..abc.run_state import RunState
from ..abc.db import Database
from ..settings import TCFConfig
from ..context import Context
from .drivers.get_database_driver_class import get_database_driver_class



if typing.TYPE_CHECKING:
    from .db_build_state import DatabaseBuildState
    from ..cf.cf_run_state import ControlFileRunState

logger = logging.getLogger('pytuflow')


class DatabaseRunState(RunState, Database):
    """Class for storing the run state of a database.

    This class should not be instantiated directly, but rather it should be created from an instance
    of a BuildState class using the `context` method of the BuildState class.

    Parameters
    ----------
    build_state : DatabaseBuildState
        The BuildState object that the RunState object is based on.
    context : Context
        The context object that the RunState object is based on.
    parent : ControlFileRunState
        The parent control file run state.
    """

    def __init__(self, build_state: 'DatabaseBuildState', context: Context, parent: 'ControlFileRunState'):
        super().__init__(build_state, context, parent)
        #: DatabaseBuildState: The build state that this run state is based on.
        self.bs = build_state
        #: ControlFileRunState: The parent control file run state.
        self.parent = parent
        #: Path: Path to the database file.
        self.fpath = self.bs.fpath
        #: TCFConfig: Configuration object for the TUFLOW control file.
        self.config = self.bs.config
        #: bool: whether the database has been loaded from disk or not.
        self.loaded = self.bs.loaded

        self._df = self.bs.df.to_df()

        self._resolve_scope_in_context()

    def __repr__(self):
        if self.fpath:
            if self.fpath.exists():
                return '<{0}Context> {1}'.format(self.bs.__class__.__name__, self.fpath.name)
            return '<{0}Context> {1} (not found)'.format(self.bs.__class__.__name__, self.fpath.name)
        else:
            return '<DatabaseContext> (empty)'

    @property
    def df(self):
        return self._df

    def value(self, item: str | int) -> int | float | pd.DataFrame:
        """Returns the value of the given index.

        Parameters
        ----------
        item : str | int
            The index/key within the database.

        Returns
        -------
        int | float | pd.DataFrame
            The value of the given index.
        """
        if not self.loaded:
            raise ValueError('Database not loaded')
        if item not in self:
            raise KeyError(f'Item {item} not found in database')

        entry = self[item]
        if entry.uses_source_file:
            source = Path(entry[self.bs.SOURCE_INDEX].value_expanded_path)
            if self.bs.TIME_INDEX != -1:
                header_labels = [entry[self.bs.TIME_INDEX].value, entry[self.bs.VALUE_INDEX].value]
            else:
                header_labels = 'infer'
        else:
            return float(entry[self.bs.VALUE_INDEX].value)

        if not source.exists():
            logger.error('Source file referenced by bcdatabase could not be found at: {}'.format(source))
            raise FileNotFoundError(f'Could not find source file {source}')

        driver = get_database_driver_class(source)
        if driver is None:
            logger.error('File format not implemented yet: {0}'.format(source.name))
            raise NotImplementedError('File format not implemented yet: {0}'.format(source.name))
        source_df = driver().load(source, header_kwargs={'header': header_labels}, index_col=False)
        if header_labels != 'infer':
            header_labels = [x for x in source_df.columns if x.lower() in [str(h).lower() for h in header_labels]]
        source_df = source_df[header_labels] if header_labels != 'infer' else source_df
        if self.bs.TIME_INDEX != -1:
            index = [x for x in source_df.columns if x.lower() == entry[self.bs.TIME_INDEX].value.lower()][0]
            source_df = source_df.set_index(index)

        return source_df

    def _resolve_scope_in_context(self):
        for index, row in self._df.iterrows():
            new_index = self.ctx.translate(index) if isinstance(index, str) else index
            new_row = [self.ctx.translate(x) for x in row]
            self._df.loc[index] = new_row
            config = TCFConfig.from_tcf_config(self.bs.config)
            config.variables = self.ctx.translate
            entry = self.bs.entry_class()(new_index, new_row, config, self)
            self.entries[index] = entry

            if not self.ctx.is_resolved(str(entry.line)):
                logger.error('Database entry has not been completely resolved - {0}'.format(entry.line))
                raise ValueError('Database entry has not been completely resolved - {0}'.format(entry.line))
