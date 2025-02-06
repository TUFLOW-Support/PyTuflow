from abc import abstractmethod
from datetime import datetime, timezone

from .tabular_output import TabularOutput
from ..pytuflow_types import PathLike


class CheckTable(TabularOutput):

    @abstractmethod
    def __init__(self, *fpath: PathLike):
        super().__init__(*fpath)
        self.reference_time = datetime(2000, 1, 1, tzinfo=timezone.utc)
        self.units = ''
