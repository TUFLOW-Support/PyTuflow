import logging
import typing
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .db_build_state import DatabaseBuildState
from .db_run_state import DatabaseRunState
from .db_entry import DBEntry
from .. import const
from ..misc.case_insensitive_dict import CaseInsDictOrdered
from ..misc.dataframe_wrapper import DataFrameWrapper
from ..tmf_types import PathLike
from ..context import Context


if typing.TYPE_CHECKING:
    from ..cf.cf_run_state import ControlFileRunState

logger = logging.getLogger('pytuflow')


class SoilDatabaseRunState(DatabaseRunState):
    """Class for storing the run state of a soil.tsoilf file.

    This class should not be instantiated directly, but rather it should be created from an instance
    of a BuildState class using the `context` method of the BuildState class.

    Parameters
    ----------
    build_state : MatDatabase
        The BuildState object that the RunState object is based on.
    context : Context
        The context object that the RunState object is based on.
    parent : ControlFileRunState
        The parent control file run state.
    """

    def __init__(self, build_state: 'SoilDatabase', context: Context, parent: 'ControlFileRunState'):
        #: SoilDatabase: the BuildState object that the RunState object is based on.
        self.bs = build_state
        super().__init__(build_state, context, parent)

    def value(self, item: int) -> dict[str, str | float | None]:
        if not self.loaded:
            raise ValueError('Database not loaded')
        if item not in self:
            raise KeyError(f'Item {item} not found in database')

        d = CaseInsDictOrdered()

        entry = self[item]
        method = entry[1].value.upper()
        d['method'] = method
        if method == 'NONE':
            return d

        def populate_common(a: dict[str, str | float | None], dbentry: DBEntry, jdx: int):
            a['Residual Water Content'] = float(dbentry[jdx].value) if len(dbentry) > jdx and dbentry[jdx] else None
            a['Saturated Water Content'] = float(dbentry[jdx + 1].value) if len(dbentry) > jdx + 1 and dbentry[jdx + 1] else None
            a['alpha'] = float(dbentry[jdx + 2].value) if len(dbentry) > jdx + 2 and dbentry[jdx + 2] else None
            a['n'] = float(dbentry[jdx + 3].value) if len(dbentry) > jdx + 3 and dbentry[jdx + 3] else None
            a['L'] = float(dbentry[jdx + 4].value) if len(dbentry) > jdx + 4 and dbentry[jdx + 4] else None

        if method == 'ILCL':
            d['IL'] = float(entry[2].value)
            d['CL'] = float(entry[3].value)
            d['Porosity'] = float(entry[4].value) if len(entry) > 4 and entry[4] else None
            d['Initial Moisture'] = float(entry[5].value) if len(entry) > 5 and entry[5] else 0.
            d['Horizontal Conductivity'] = float(entry[6].value) if len(entry) > 6 and entry[6] else None
            populate_common(d, entry, 7)
            return d

        if method == 'GA':
            try:
                float(entry[2].value)
                usda = False
            except ValueError:
                usda = True

            if usda:
                d['USDA Soil Type'] = entry[2].value.strip(' \t\n"\'')
                idx = 3
            else:
                d['Suction'] = float(entry[2].value) if len(entry) > 2 and entry[2] else None
                d['Hydraulic Conductivity'] = float(entry[3].value) if len(entry) > 3 and entry[3] else None
                d['Porosity'] = float(entry[4].value) if len(entry) > 4 and entry[4] else None
                idx = 5
            d['Initial Moisture'] = float(entry[idx].value) if len(entry) > idx and entry[idx] else None
            d['Max Ponding Depth'] = float(entry[idx+1].value) if len(entry) > idx + 1 and entry[idx+1] else None
            d['Horizontal Conductivity'] = float(entry[idx+2].value) if len(entry) > idx + 2 and entry[idx+2] else None
            populate_common(d, entry, idx + 3)
            return d

        if method == 'HO':
            d['IL'] = float(entry[2].value)
            d['IL Rate'] = float(entry[3].value)
            d['Final Loss Rate'] = float(entry[4].value)
            d['Ex Decay Rate'] = float(entry[5].value)
            d['Porosity'] = float(entry[6].value) if len(entry) > 6 and entry[6] else None
            d['Initial Moisture'] = float(entry[7].value) if len(entry) > 7 and entry[7] else 0.
            d['Horizontal Conductivity'] = float(entry[8].value) if len(entry) > 8 and entry[8] else None
            populate_common(d, entry, 9)
            return d

        if method == 'CO':
            d['Hydraulic Conductivity'] = float(entry[2].value)
            d['Porosity'] = float(entry[3].value)
            d['Initial Moisture'] = float(entry[4].value) if len(entry) > 4 and entry[4] else 0.
            d['Horizontal Conductivity'] = float(entry[5].value) if len(entry) > 5 and entry[5] else None
            populate_common(d, entry, 6)
            return d

        if method == 'SCS':
            d['Curve Number'] = float(entry[2].value)
            d['Initial Abstraction Ratio'] = float(entry[3].value)
            populate_common(d, entry, 6)
            return d

        logger.error(f'Soil method {method} is not implemented or not recognised')
        raise NotImplementedError(f'Soil method {method} is not implemented or not recognised')


class SoilDatabase(DatabaseBuildState):
    """Database class for soil properties.

    Currently, the Database class has not implemented the :meth:`write() <pytuflow.tmf.DatabaseBuildState.write>`
    method, so it should be initialised with a :code:`fpath` to an existing database file as it can't be edited.
    """
    SOURCE_INDEX = -1
    TIME_INDEX = -1
    VALUE_INDEX = 1
    TUFLOW_TYPE = const.DB.SOIL

    COLUMN_NAMES = ['Method'] + [f'Column {i}' for i in range(1, 20)]
    INDEX_NAME = 'Soil ID'

    def __init__(self, fpath: PathLike | None = None, *args, **kwargs) -> None:
        # docstring inherited
        super().__init__(fpath, *args, **kwargs)
        if not self.loaded:
            self._df = pd.DataFrame(columns=self.COLUMN_NAMES[:10])
        else:
            self._df.columns = self.COLUMN_NAMES[:len(self._df.columns)]
        self._df.index.name = self.INDEX_NAME
        self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=self._df.copy())

    def _find_header_row_end(self, fpath: Path) -> dict:
        return {'header': None}

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> SoilDatabaseRunState:
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return SoilDatabaseRunState(self, ctx, parent)
