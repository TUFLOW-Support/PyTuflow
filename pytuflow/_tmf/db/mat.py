import logging
import typing
from pathlib import Path

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .db_build_state import DatabaseBuildState
from .db_run_state import DatabaseRunState
from .mat_db_entry import MatDBEntry
from ..tmf_types import PathLike
from ..misc.dataframe_wrapper import DataFrameWrapper
from ..context import Context
from .. import const

if typing.TYPE_CHECKING:
    from ..cf.cf_run_state import ControlFileRunState


logger = logging.getLogger('pytuflow')


class MatDatabaseRunState(DatabaseRunState):
    """Class for storing the run state of a materials.csv file.

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

    def __init__(self, build_state: 'MatDatabase', context: Context, parent: 'ControlFileRunState'):
        #: MatDatabase: the BuildState object that the RunState object is based on.
        self.bs = build_state
        super().__init__(build_state, context, parent)

    def value(self, item: str | int) -> typing.Any:
        if not self.loaded:
            raise ValueError('Database not loaded')
        if item not in self:
            raise KeyError(f'Item {item} not found in database')

        entry = self.entries[item]
        if entry.is_list():  # depth varying manning's n - not in a file
            try:
                value = entry[self.bs.VALUE_INDEX].value
                values = [float(x) for x in value.strip('"').split(',')]
                x = values[::2]
                y = values[1::2]
                df = pd.DataFrame({'Depth': x, "Manning's n": y}, dtype=np.float64)
                return df.set_index('Depth')
            except (ValueError, TypeError):
                logger.error(f'Could not parse depth-varying mannings n for index {item}')
                raise ValueError(f'Could not parse depth-varying mannings n for index {item}')

        return super().value(item)


class MatDatabaseTMFRunState(DatabaseRunState):
    """Class for storing the run state of a materials.tmf file.

    This class should not be instantiated directly, but rather it should be created from an instance
    of a BuildState class using the `context` method of the BuildState class.

    Parameters
    ----------
    build_state : MatDatabaseTMF
        The BuildState object that the RunState object is based on.
    context : Context
        The context object that the RunState object is based on.
    parent : ControlFileRunState
        The parent control file run state.
    """

    def __init__(self, build_state: 'MatDatabaseTMF', context: Context, parent: 'ControlFileRunState'):
        #: MatDatabaseTMF: the BuildState object that the RunState object is based on.
        self.bs = build_state
        super().__init__(build_state, context, parent)

    def value(self, item: str | int) -> typing.Any:
        if not self.loaded:
            raise ValueError('Database not loaded')
        if item not in self:
            raise KeyError(f'Item {item} not found in database')

        if len(self._df.columns) < 7 or not any([x for x in self._df.loc[int(item), :].tolist()[3:7] if not np.isnan(x) and x != 'nan']):
            return super().value(item)

        # depth varying manning's n
        val = self._df.loc[int(item), :].tolist()[3:7]
        x = val[::2]
        y = val[1::2]
        return pd.DataFrame({'Depth': x, "Manning's n": y}, dtype=np.float64)


class MatDatabase(DatabaseBuildState):
    """Database class for material properties.

    Currently, the Database class has not implemented the :meth:`write() <pytuflow.tmf.DatabaseBuildState.write>`
    method, so it should be initialised with a :code:`fpath` to an existing database file as it can't be edited.
    """
    SOURCE_INDEX = 1
    TIME_INDEX = -1
    VALUE_INDEX = 1

    TUFLOW_TYPE = const.DB.MAT

    COLUMN_NAMES = ['Manning\'s n', 'Rainfall Losses', 'Land Use Hazard ID', 'SRF', 'Fraction Impervious']
    INDEX_NAME = 'Material ID'

    def __init__(self, fpath: PathLike | None = None, *args, **kwargs) -> None:
        # docstring inherited
        self._remove_comments = False
        super().__init__(fpath, *args, **kwargs)
        if not self.loaded:
            self._df = pd.DataFrame(columns=self.COLUMN_NAMES)
            self._df.index.name = self.INDEX_NAME
            self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=self._df.copy())

    def entry_class(self) -> type[MatDBEntry]:
        return MatDBEntry

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> MatDatabaseRunState:
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return MatDatabaseRunState(self, ctx, parent)

    def _find_header_row_end(self, fpath: Path) -> dict:
        idx = -1
        names = None
        inames = -1
        with fpath.open() as f:
            for i, line in enumerate(f):
                data = line.split(',')
                try:
                    int(data[0])
                    idx = i - 1
                    break
                except (ValueError, TypeError):
                    if line.strip().startswith('!') or line.strip().startswith('#'):
                        names = [x.strip(' #!"\'\n\t')for x in line.split(',')]
                        inames = i
                    continue
        if idx == inames and names:
            return {'header': None, 'names': names}
        return {'header': idx}

    def _load(self, fpath: Path):
        super()._load(fpath)
        if not self._df.empty and self._df.index.dtype not in [np.dtype('i4'), np.dtype('i8')]:
            self._df.index = self._df.index.astype(int)
            self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=self._df.copy())


class MatDatabaseTMF(MatDatabase):
    SOURCE_INDEX = -1
    COLUMN_NAMES = ["Manning's n", 'IL', 'CL', 'y1', 'n1', 'y2', 'n2', 'Land Use Hazard ID',
                    'SRF', 'Fraction Impervious']

    TUFLOW_TYPE = const.DB.MAT_TMF

    def write(self, inc: str):
        # tmf header has to be written with an exclamation mark
        added_exclamation = False
        if '!' not in self._df.index.name:
            added_exclamation = True
            self._df.index.name = f'! {self._df.index.name}'
        super().write(inc)
        if added_exclamation:
            self._df.index.name = self._df.index.name.strip('! ')

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> MatDatabaseTMFRunState:
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return MatDatabaseTMFRunState(self, ctx, parent)

    def _find_header_row_end(self, fpath: Path) -> dict:
        return {'header': 'infer'}

    def _load(self, fpath: Path):
        super()._load(fpath)
        self._df.index.name = self.INDEX_NAME
        self._df.columns = self.COLUMN_NAMES[:len(self._df.columns)]
        self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=self._df.copy())


def get_material_database_class(fpath: PathLike) -> type[MatDatabase]:
    if Path(fpath).suffix.lower() == '.csv':
        return MatDatabase
    else:
        return MatDatabaseTMF
