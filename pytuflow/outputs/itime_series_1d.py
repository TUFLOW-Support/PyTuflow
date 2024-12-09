from abc import ABC, abstractmethod

import pandas as pd

from pytuflow.outputs.helpers.get_standard_data_type_name import get_standard_data_type_name
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
        #: pd.DataFrame: 1D information
        self.oned_objs = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt'])
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
        self._lp = lp
        return self._lp.df

    def context_combinations_1d(self, context: list[str]) -> pd.DataFrame:
        ctx = context.copy() if context else []
        df = self.oned_objs.copy()
        df['domain'] = '1d'

        # domain
        something = False
        if '1d' in ctx:
            something = True
            ctx.remove('1d')
        if 'node' in ctx:
            something = True
            df = df[df['geometry'] == 'point']
            ctx.remove('node')
        if 'channel' in ctx:
            something = True
            df = df[df['geometry'] == 'line']
            ctx.remove('channel')

        # if no domain (including 2d/rl) specified then get everything and let other filters do the work
        if not something and '0d' not in context and '2d' not in context and 'po' not in context and 'rl' not in context:
            df = self.oned_objs.copy()
            df['domain'] = '1d'

        # data types
        ctx1 = [get_standard_data_type_name(x) for x in ctx]
        ctx1 = [x for x in ctx1 if x in df['data_type'].unique()]
        if ctx1:
            df = df[df['data_type'].isin(ctx1)]
            for i in range(len(ctx1) - 1, -1, -1):
                ctx.pop(i)

        # ids
        if ctx:
            df = df[df['id'].isin(ctx)]

        return df if not df.empty else pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt', 'domain'])
