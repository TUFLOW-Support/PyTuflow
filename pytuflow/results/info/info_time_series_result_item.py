from datetime import datetime

from .info_maximums import INFOMaximums
from ..tpc.tpc_time_series_result_item import TPCResultItem
from pytuflow.types import PathLike


class INFOResultItem(TPCResultItem):
    """Base class for Info result items Channels, Nodes, etc."""

    def __init__(self, fpath: PathLike) -> None:
        # docstring inherited
        self.maximums = INFOMaximums()
        super().__init__(fpath)

    def load_time_series(self, name: str, fpath: PathLike, reference_time: datetime, index_col=None, id: str = '') -> None:
        # docstring inherited
        super().load_time_series(name, fpath, reference_time, index_col, id)
        self.maximums.append(name, self.time_series[name].df)
