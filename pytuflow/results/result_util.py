import pandas as pd
from abc import ABC, abstractmethod

from .abc.channels import Channels
from .abc.nodes import Nodes


class ResultUtil(ABC):
    """
    Class for handling functions that don't belong in either Channels or Nodes class and
    are format specific enough that df can't be massaged into a common format so requires
    sub-classing.

    Although this is an abstract class, it should be the initialised class and it will choose which subclass to use
    depending on the type of channels passed in (TPCChannels or GPKGChannels, etc).
    """

    def __new__(cls, channels: Channels, nodes: Nodes):
        from .tpc.tpc_channels import TPCChannels
        from .gpkg_ts.gpkg_channels import GPKGChannels
        if isinstance(channels, TPCChannels):
            from .tpc.tpc_utils import TPCResultUtil
            cls = TPCResultUtil
        elif isinstance(channels, GPKGChannels):
            from .gpkg_ts.gpkg_ts_utils import GPKG_TSResultUtil
            cls = GPKG_TSResultUtil
        return super().__new__(cls)

    def __init__(self, channels: Channels, nodes: Nodes) -> None:
        self.channels = channels
        self.nodes = nodes

    @abstractmethod
    def extract_culvert_obvert(self, inp_df: pd.DataFrame) -> list[float]:
        """
        Extracts the culvert obverts from the inp_df which should contain a list of channel IDs.

        :param inp_df:
            DataFrame containing a list of channel IDs as one of the columns.
        """
        raise NotImplementedError

    @abstractmethod
    def extract_pit_levels(self, inp_df: pd.DataFrame) -> list[float]:
        """
        Extracts the pit ground levels from the inp_df which should contain a list of channel IDs and node IDs.

        :param inp_df:
            DataFrame containing a list of channel IDs and node IDs as one of the columns.
        """
        raise NotImplementedError
