import logging
import typing
from pathlib import Path

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .db_run_state import DatabaseRunState
from .drivers.get_database_driver_class import get_database_driver_class
from ..context import Context

if typing.TYPE_CHECKING:
    from .bc_dbase import BCDatabase
    from ..cf.cf_run_state import ControlFileRunState

logger = logging.getLogger('pytuflow')


class BCDatabaseRunState(DatabaseRunState):
    """Class for storing the run state of a bc_dbase.csv.

    This class should not be instantiated directly, but rather it should be created from an instance
    of a BuildState class using the `context` method of the BuildState class.

    Parameters
    ----------
    build_state : BCDatabase
        The BuildState object that the RunState object is based on.
    context : Context
        The context object that the RunState object is based on.
    parent : ControlFileRunState
        The parent control file run state.
    """

    def __init__(self, build_state: 'BCDatabase', context: Context, parent: 'ControlFileRunState'):
        #: BCDatabase: the BuildState object that the RunState object is based on.
        self.bs = build_state
        super().__init__(build_state, context, parent)

    def value(self, item: str | int):
        if '|' in str(item):
            df = self._value_with_group(item)
            name, group = [x.strip() for x in str(item).split('|', 1)]
            entry = self[group]
        else:
            df = super().value(item)
            if isinstance(df, pd.DataFrame):
                df.reset_index(inplace=True)
            name = None
            entry = self[item]

        time_col, val_col = [entry[self.bs.TIME_INDEX].value, entry[self.bs.VALUE_INDEX].value]
        if time_col in ['nan', '']:
            time_col = 'Time (min)'  # ts1 default time column
        if val_col in ['nan', '']:
            if name is None:
                logger.error(f'Value column for {item} is empty in bc_database: {self.fpath}')
                raise ValueError(f'Value column for {item} is empty in bc_database: {self.fpath}')
            val_col = name
        is_df = isinstance(df, pd.DataFrame)  # could also be a single float value
        if is_df:
            time_col_ = [col for col in df.columns if str(col).lower() == time_col.lower()]
            if time_col_:
                time_col = time_col_[0]
            val_col_ = [col for col in df.columns if str(col).lower() == val_col.lower()]
            if val_col_:
                val_col = val_col_[0]

        # perform any multiplication or addition on the time and value columns
        if len(entry) > self.bs.TIME_ADD_INDEX and is_df and self.bs.TIME_ADD_INDEX > -1:
            time_add = entry[self.bs.TIME_ADD_INDEX].value
            try:
                time_add = float(time_add)
                if np.isnan(time_add):
                    time_add = 0.0
            except (ValueError, TypeError):
                time_add = 0.0
            df.loc[:, time_col] += time_add
        if len(entry) > self.bs.VALUE_FACTOR_INDEX and self.bs.VALUE_FACTOR_INDEX > -1:
            value_factor = entry[self.bs.VALUE_FACTOR_INDEX].value
            try:
                value_factor = float(value_factor)
                if np.isnan(value_factor):
                    value_factor = 1.0
            except (ValueError, TypeError):
                value_factor = 1.0
            if is_df:
                df.loc[:, val_col] *= value_factor
            else:
                df *= value_factor
        if len(entry) > self.bs.VALUE_ADD_INDEX and self.bs.VALUE_ADD_INDEX > -1:
            value_add = entry[self.bs.VALUE_ADD_INDEX].value
            try:
                value_add = float(value_add)
                if np.isnan(value_add):
                    value_add = 0.0
            except (ValueError, TypeError):
                value_add = 0.0
            if is_df:
                df.loc[:, val_col] += value_add
            else:
                df += value_add

        if isinstance(df, pd.DataFrame):
            return df.set_index(time_col)
        return df

    def _value_with_group(self, item: str | int) -> pd.DataFrame:
        name, group = [x.strip() for x in str(item).split('|', 1)]
        if not self.loaded:
            raise ValueError('Database not loaded')
        if group not in self:
            raise KeyError(f'Item {group} not found in database')

        entry = self[group]
        source = Path(entry[self.bs.SOURCE_INDEX].value_expanded_path)
        header_labels = [name]

        if not source.exists():
            logger.error('Source file referenced by bc_database could not be found at: {}'.format(source))
            raise FileNotFoundError(f'Could not find source file {source}')

        driver = get_database_driver_class(source)()
        if driver is None:
            logger.error('File format not implemented yet: {0}'.format(source.name))
            raise NotImplementedError('File format not implemented yet: {0}'.format(source.name))
        if driver.name() not in ['ts1']:
            logger.error(f'Group syntax "N1|Group" can only be used with TS1 files, not {source.suffix}')
            raise ValueError(f'Group syntax "N1|Group" can only be used with TS1 files, not {source.suffix}')

        source_df = driver.load(source, header_kwargs={'header': header_labels}, index_col=False)

        return source_df[header_labels].reset_index()
