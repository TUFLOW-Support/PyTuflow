import logging
import typing

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .db_run_state import DatabaseRunState
from .xs_db_entry import XSDBEntry, FMXSDBEntry
from .drivers.xs import CrossSectionDatabaseDriver
from .. import const
from ..db.db_build_state import DatabaseBuildState
from ..context import Context

from ..scope import ScopeList

if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from ..cf.cf_run_state import ControlFileRunState


logger = logging.getLogger('pytuflow')


# noinspection PyUnresolvedReferences
class FMDatabaseMixin:

    def __getitem__(self, item):
        if self.driver.name() == 'dat_cross_section':
            unit = self.driver.dat.unit(item)
            if unit:
                item = unit[0].uid if isinstance(unit, list) else unit.uid
        return super().__getitem__(item)

    def __contains__(self, item: str | int):
        if self.driver.name() == 'dat_cross_section':
            unit = self.driver.dat.unit(item)
            if unit:
                item = unit[0].uid if isinstance(unit, list) else unit.uid
        return super().__contains__(item)


class CrossSectionDatabaseRunState(FMDatabaseMixin, DatabaseRunState):

    def __init__(self, build_state: 'CrossSectionDatabase', context: Context, parent: 'ControlFileRunState'):
        #: CrossSectionDatabase: The build state that this run state is based on.
        self.bs = build_state
        self.driver = build_state.driver
        super().__init__(build_state, context, parent)

    def _resolve_scope_in_context(self):
        if self.driver.name() == 'dat_cross_section':
            self._df = self.bs.df.to_df()
            self.entries = self.bs.entries
        else:
            super()._resolve_scope_in_context()

    def value(self, item: str) -> pd.DataFrame:
        if not self.loaded:
            raise ValueError('Database not loaded')
        if item not in self:
            raise KeyError(f'Item {item} not found in database')

        entry = self[item]

        return entry.cross_section()


class CrossSectionDatabase(FMDatabaseMixin, DatabaseBuildState):
    """Database class for storing cross-sections.

    Currently, the Database class has not implemented the :meth:`write() <pytuflow.tmf.DatabaseBuildState.write>`
    method, so it should be initialised with a :code:`fpath` to an existing database file as it can't be edited.
    """
    TUFLOW_TYPE = const.DB.XS

    @property
    def driver(self) -> CrossSectionDatabaseDriver:
        return self._driver

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> CrossSectionDatabaseRunState:
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return CrossSectionDatabaseRunState(self, ctx, parent)

    def _load_from_df(self, df: pd.DataFrame):
        if self._driver.name() == 'dat_cross_section':
           for idx, _ in df.iterrows():
               self.entries[idx] = FMXSDBEntry(idx, self._driver.dat.unit(idx))
        else:
            super()._load_from_df(df)

    def entry_class(self) -> type[XSDBEntry]:
        return XSDBEntry

    def figure_out_file_scopes(self, scope_list: ScopeList) -> None:
        """no-doc"""
        pass
