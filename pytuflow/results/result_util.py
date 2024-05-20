import pandas as pd

from .abc.channels import Channels
from .abc.nodes import Nodes


class ResultUtil:
    """Class for handling functions that don't belong in either Channels or Nodes class and
    are format specific enough that df can't be massaged into a common format so requires
    sub-classing.

    Although this is an abstract class, it should be the entry point and it will choose which subclass to use
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
        #: :doc:`Channels <pytuflow.results.Channels>`: Channels object.
        self.channels = channels
        #: :doc:`Nodes <pytuflow.results.Nodes>`: Nodes object.
        self.nodes = nodes

    def extract_culvert_obvert(self, inp_df: pd.DataFrame) -> list[float]:
        """Extracts culvert obvert levels from the input channels pd.DataFrame.

        Parameters
        ----------
        inp_df : pd.DataFrame
            Input channels DataFrame.

        Returns
        -------
        list[float]
            List of culvert obvert levels.
        """
        return []

    def extract_pit_levels(self, inp_df: pd.DataFrame) -> list[float]:
        """Extracts pit levels from the input channels pd.DataFrame.

        Parameters
        ----------
        inp_df : pd.DataFrame
            Input channels DataFrame.

        Returns
        -------
        list[float]
            List of pit levels.
        """
        return []
