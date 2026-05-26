import logging
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .db_build_state import DatabaseBuildState
from ..misc.dataframe_wrapper import DataFrameWrapper
from .. import const

logger = logging.getLogger('pytuflow')


class RainfallDatabase(DatabaseBuildState):
    """Database class for rainfall values.

    Currently, the Database class has not implemented the :meth:`write() <pytuflow.tmf.DatabaseBuildState.write>`
    method, so it should be initialised with a :code:`fpath` to an existing database file as it can't be edited.
    """

    TUFLOW_TYPE = const.DB.RAINFALL

    INDEX_NAME = 'Time'
    COLUMN_NAMES = ['Rainfall_File']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.loaded:
            self._df = pd.DataFrame(columns=self.COLUMN_NAMES)
        else:
            self._df.columns = self.COLUMN_NAMES[:len(self._df.columns)]
        self._df.index.name = self.INDEX_NAME
        self._df_wrapped = DataFrameWrapper(on_change=self.record_change, data=self._df.copy())

    def _find_header_row_end(self, fpath: Path) -> dict:
        return {'header': None}
