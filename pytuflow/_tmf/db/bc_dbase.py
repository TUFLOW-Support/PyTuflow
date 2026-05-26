import logging
import typing

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .db_build_state import DatabaseBuildState
from .bc_dbase_entry import BCDatabaseEntry
from .. import const
from ..misc.dataframe_wrapper import DataFrameWrapper
from ..context import Context


if typing.TYPE_CHECKING:
    from .bc_dbase_run_state import BCDatabaseRunState
    # noinspection PyUnusedImports
    from ..cf.cf_run_state import ControlFileRunState

logger = logging.getLogger('pytuflow')


class BCDatabase(DatabaseBuildState):
    """Database class for boundary conditions.

    Currently, the Database class has not implemented the :meth:`write() <pytuflow.tmf.DatabaseBuildState.write>`
    method, so it should be initialised with a :code:`fpath` to an existing database file as it can't be edited.
    """
    SOURCE_INDEX = 1
    TIME_INDEX = 2
    VALUE_INDEX = 3
    TIME_ADD_INDEX = 4
    VALUE_FACTOR_INDEX = 5
    VALUE_ADD_INDEX = 6

    TUFLOW_TYPE = const.DB.BC_DBASE

    INDEX_NAME = 'Name'
    COLUMN_NAMES = ['Source', 'Column 1', 'Column 2', 'Add Col 1',
                    'Mult Col 2', 'Add Col 2', 'Column 3', 'Column 4']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.loaded:
            # initialise an empty dataframe with the expected columns
            self._df = pd.DataFrame(columns=self.COLUMN_NAMES)
            self._df.index.name = self.INDEX_NAME
            self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=self._df.copy())

    def value(self, item: str | int) -> typing.Any:
        # docstring inherited - override method to handle group syntax ("N1|Group")
        group = item if '|' not in item else item.split('|')[1].strip()
        if group not in self:
            logger.error(f'Item {group} not found in database')
            raise KeyError(f'Item {group} not found in database')
        try:
            db_ctx = self.context()
        except Exception as e:
            raise ValueError('Database requires a context to resolve value.') from e
        return db_ctx.value(item)

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> 'BCDatabaseRunState':
        # docstring inherited
        from .bc_dbase_run_state import BCDatabaseRunState
        ctx = context if context else Context(run_context, config=self.config)
        return BCDatabaseRunState(self, ctx, parent)

    def entry_class(self) -> type[BCDatabaseEntry]:
        return BCDatabaseEntry
