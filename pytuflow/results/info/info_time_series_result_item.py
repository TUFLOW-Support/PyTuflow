from datetime import datetime

from .info_maximums import InfoMaximums
from ..tpc.tpc_time_series_result_item import TPCResultItem
from ..types import PathLike


class InfoResultItem(TPCResultItem):

    def __init__(self, fpath: PathLike) -> None:
        self.maximums = InfoMaximums()
        super().__init__(fpath)

    def load_time_series(self, name: str, fpath: PathLike, reference_time: datetime, index_col=None, id: str = '') -> None:
        super().load_time_series(name, fpath, reference_time, index_col, id)
        self.maximums.append(name, self.time_series[name].df)