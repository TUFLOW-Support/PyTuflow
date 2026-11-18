import csv
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


class TMFMixin:

    def _is_plottable(self, item: str | int, df: pd.DataFrame) -> bool:
        """no-doc"""
        if len(df.columns) < 7 or not any([x for x in df.loc[int(item), :].tolist()[3:7] if not np.isnan(x) and x != 'nan']):
            return False
        return True


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

    def is_plottable(self, item: str | int) -> bool:
        """no-doc"""
        entry = self.entries[item]
        return super().is_plottable(item) or entry.is_list()

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


class MatDatabaseTMFRunState(DatabaseRunState, TMFMixin):
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

    def is_plottable(self, item: str | int) -> bool:
        """no-doc"""
        return super().is_plottable(item) or self._is_plottable(item, self._df)

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
    
    def is_plottable(self, item: str | int) -> bool:
        """no-doc"""
        entry = self.entries[item]
        return super().is_plottable(item) or entry.is_list()

    def _find_header_row_end(self, fpath: Path) -> dict:
        """Locate the materials table header despite blank/comment preambles.

        pandas counts header rows after skipping blank lines, whereas source
        line numbers include those lines. Use skiprows for physical preambles.
        """
        header_line = None
        commented_names = None
        with fpath.open(encoding='utf-8-sig') as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                fields = line.split(',')
                first = fields[0].strip()
                if first.startswith(('!', '#')):
                    if first.lstrip('!# ').casefold() == 'material id':
                        commented_names = [
                            field.strip(' #!').strip('"').strip("'").strip()
                            for field in fields
                        ]
                    continue
                try:
                    int(first)
                except (ValueError, TypeError):
                    header_line = i
                    commented_names = None
                    continue
                if header_line is not None:
                    return self._csv_header_options(fpath, header_line)
                if commented_names is not None:
                    return {'skiprows': i, 'header': None, 'names': commented_names}
                return {'skiprows': i, 'header': None, 'skipinitialspace': True}
        if header_line is not None:
            return self._csv_header_options(fpath, header_line)
        return {'header': 0}

    @staticmethod
    def _csv_header_options(fpath: Path, header_line: int) -> dict:
        # TUFLOW permits spaces before quoted fields and free-form trailing
        # comments. Commas in a declared comment column must not send the CSV
        # driver into its headerless, quote-unaware fallback parser.
        with fpath.open(encoding='utf-8-sig') as stream:
            for _ in range(header_line):
                next(stream)
            fields = next(csv.reader(stream, skipinitialspace=True))
        options = {'skiprows': header_line, 'header': 0, 'skipinitialspace': True}
        for index, field in enumerate(fields):
            if field.lstrip().startswith('!'):
                options['usecols'] = list(range(index + 1))
                break
        return options

    def _load_from_df(self, df: pd.DataFrame):
        """Discard empty and comment-only material rows before indexing IDs."""
        # CSV separator rows and whole-line comments are not material records.
        # Keep malformed nonempty rows so integer-ID validation still rejects them.
        comments = [isinstance(key, str) and key.lstrip().startswith(('!', '#')) for key in df.index]
        empty = df.isna().all(axis=1) & df.index.isna()
        self._df = df.loc[~(empty | np.asarray(comments, dtype=bool))].copy()
        self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=self._df.copy())
        super()._load_from_df(self._df)

    def _load(self, fpath: Path):
        super()._load(fpath)
        if not self._df.empty and self._df.index.dtype not in [np.dtype('i4'), np.dtype('i8')]:
            self._df.index = self._df.index.astype(int)
            self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=self._df.copy())


class MatDatabaseTMF(MatDatabase, TMFMixin):
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
    
    def is_plottable(self, item: str | int) -> bool:
        """no-doc"""
        return super().is_plottable(item) or self._is_plottable(item, self._df)

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
