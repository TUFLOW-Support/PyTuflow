import pandas as pd

from .channels import Channels
from .nodes import Nodes


class Utils:
    """
    Class for handling functions that don't belong in either Channels or Nodes class and
    are format specific enough that df can't be massaged into a common format so require
    sub-classing.
    """

    def __new__(cls, channels: Channels, nodes: Nodes):
        from ..tpc.tpc_channels import TPCChannels
        from ..gpkg_ts.gpkg_channels import GPKGChannels
        if isinstance(channels, TPCChannels):
            from ..tpc.tpc_utils import TPC_Utils
            cls = TPC_Utils
        elif isinstance(channels, GPKGChannels):
            from ..gpkg_ts.gpkg_ts_utils import GPKG_TS_Utils
            cls = GPKG_TS_Utils
        return super().__new__(cls)

    def __init__(self, channels: Channels, nodes: Nodes) -> None:
        self.channels = channels
        self.nodes = nodes

    def extract_culvert_obvert(self, inp_df: pd.DataFrame) -> list[float]:
        raise NotImplementedError

    def extract_pit_levels(self, inp_df: pd.DataFrame) -> list[float]:
        raise NotImplementedError
