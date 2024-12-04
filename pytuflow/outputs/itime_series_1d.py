from abc import ABC, abstractmethod

import pandas as pd

from pytuflow.pytuflow_types import PathLike, LongPlotExtractionLocation
from pytuflow.outputs.helpers.lp_1d import LP_1D


class ITimeSeries1D(ABC):
    """Interface class for 1D time series outputs."""

    @abstractmethod
    def __init__(self, *fpath: PathLike) -> None:
        super().__init__()
        #: pd.DataFrame: Node information. Column headers are 'id', 'bed_level', 'top_level', 'nchannel', 'channels'
        self.node_info = pd.DataFrame(
            index=['id'],
            columns=['bed_level', 'top_level', 'nchannel', 'channels']
        )
        #: pd.DataFrame: Channel information. Column headers are 'id', 'us_node', 'ds_node', 'us_chan', 'ds_chan', 'ispipe', 'length', 'us_invert', 'ds_invert', 'lbus_obvert', 'rbus_obvert', 'lbds_obvert', 'rbds_obvert'
        self.chan_info = pd.DataFrame(
            index=['id'],
            columns=['us_node', 'ds_node', 'us_chan', 'ds_chan', 'ispipe', 'length', 'us_invert', 'ds_invert',
                     'lbus_obvert', 'rbus_obvert', 'lbds_obvert', 'rbds_obvert']
        )
        #: int: Number of nodes
        self.node_count = 0
        #: int: Number of channels
        self.channel_count = 0

        # private
        self._lp = None

    def connectivity(self, ids: LongPlotExtractionLocation) -> pd.DataFrame:
        """Return a DataFrame describing the connectivity between the `ids`.

        The ids can be a single ID, or a list of IDS. The connectivity for a single ID will trace downstream
        to the outlet of the network. For multiple IDS, one ID must be downstream of all other IDs and the
        connectivity will trace from IDs to the downstream ID.

        Parameters
        ----------
        ids : :doc:`pytuflow.pytuflow_types.LongPlotExtractionLocation`
            The IDs to trace the connectivity for.

        Returns
        -------
        pd.DataFrame
            The connectivity information.
        """
        lp = LP_1D(ids, self.node_info, self.chan_info)
        if self._lp is not None and lp == self._lp:
            return self._lp.df

        lp.connectivity()
        self.lp = lp
        return self.lp.df
