from .bc_dbase import BCDatabase
from .bc_dbase_run_state import BCDatabaseRunState
from ..context import Context
from ..cf.cf_run_state import ControlFileRunState
from .. import const


class PitInletDatabaseRunState(BCDatabaseRunState):
    pass


class PitInletDatabase(BCDatabase):
    """Database class for pit inlet properties.

    Currently, the Database class has not implemented the :meth:`write() <pytuflow.tmf.DatabaseBuildState.write>`
    method, so it should be initialised with a :code:`fpath` to an existing database file as it can't be edited.
    """
    TUFLOW_TYPE = const.DB.PIT

    INDEX_NAME = 'Name'
    COLUMN_NAMES = ['Source', 'Depth_Col', 'Flow_Col', 'Area', 'Width']

    TIME_ADD_INDEX = -1
    VALUE_FACTOR_INDEX = -1
    VALUE_ADD_INDEX = -1

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: ControlFileRunState | None = None) -> PitInletDatabaseRunState:
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return PitInletDatabaseRunState(self, ctx, parent)
