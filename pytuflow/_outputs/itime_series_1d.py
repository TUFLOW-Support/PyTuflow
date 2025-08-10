from abc import ABC, abstractmethod
from typing import Union

import pandas as pd

from .helpers.lp_1d import LP1D


class ITimeSeries1D(ABC):
    """Interface class for 1D time series outputs.

    Parameters
    ----------
    fpath : PathLike
        The file path to the TUFLOW output file.
    """

    @abstractmethod
    def __init__(self, *args) -> None:
        super().__init__(*args)
        #: pd.DataFrame: Node information. Column headers are :code:`[id, bed_level, top_level, nchannel, channels]`
        self._node_info = pd.DataFrame(
            index=['id'],
            columns=['bed_level', 'top_level', 'nchannel', 'channels']
        )

        #: pd.DataFrame: Channel information. Column headers are :code:`[id, us_node, ds_node, us_chan, ds_chan, ispipe, length, us_invert, ds_invert, lbus_obvert, rbus_obvert, lbds_obvert, rbds_obvert]`
        self._channel_info = pd.DataFrame(
            index=['id'],
            columns=['us_node', 'ds_node', 'us_chan', 'ds_chan', 'ispipe', 'length', 'us_invert', 'ds_invert',
                     'lbus_obvert', 'rbus_obvert', 'lbds_obvert', 'rbds_obvert']
        )

        #: pd.DataFrame: Information on all 1D output objects. Column headers are :code:`[id, data_type, geometry, start, end, dt]`
        self.oned_objs = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt'])

        #: int: Number of nodes
        self.node_count = 0

        #: int: Number of channels
        self.channel_count = 0

        # private
        self._lp = None

    def _connectivity(self, ids: Union[str, list[str]]) -> pd.DataFrame:
        """Return a DataFrame describing the connectivity between the :code:`ids`.

        :code:`ids` can be a single ID, or a list of IDs. The connectivity for a single ID will trace downstream
        to the outlet of the network. For multiple IDs, one ID must be downstream of all other IDs and the
        connectivity will trace from IDs to the downstream ID.

        Parameters
        ----------
        ids : str | list[str]
            The IDs to trace the connectivity for.

        Returns
        -------
        pd.DataFrame
            The connectivity information.
        """
        lp = LP1D(ids, self._node_info, self._channel_info)
        if self._lp is not None and lp == self._lp:
            return self._lp.df

        lp.connectivity()
        self._lp = lp
        return self._lp.df
