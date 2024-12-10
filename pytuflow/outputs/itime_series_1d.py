from abc import ABC, abstractmethod
from typing import Union

import pandas as pd

from pytuflow.outputs.helpers.get_standard_data_type_name import get_standard_data_type_name
from pytuflow.pytuflow_types import PathLike
from pytuflow.outputs.helpers.lp_1d import LP_1D


class ITimeSeries1D(ABC):
    """Interface class for 1D time series outputs.

    Parameters
    ----------
    fpath : :class:`PathLike <pytuflow.pytuflow_types.PathLike>`
        The file path to the TUFLOW output file.
    """

    @abstractmethod
    def __init__(self, *fpath: PathLike) -> None:
        super().__init__()
        #: pd.DataFrame: Node information. Column headers are :code:`[id, bed_level, top_level, nchannel, channels]`
        self.node_info = pd.DataFrame(
            index=['id'],
            columns=['bed_level', 'top_level', 'nchannel', 'channels']
        )

        #: pd.DataFrame: Channel information. Column headers are :code:`[id, us_node, ds_node, us_chan, ds_chan, ispipe, length, us_invert, ds_invert, lbus_obvert, rbus_obvert, lbds_obvert, rbds_obvert]`
        self.channel_info = pd.DataFrame(
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

    def connectivity(self, ids: Union[str, list[str]]) -> pd.DataFrame:
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
        lp = LP_1D(ids, self.node_info, self.channel_info)
        if self._lp is not None and lp == self._lp:
            return self._lp.df

        lp.connectivity()
        self._lp = lp
        return self._lp.df

    def context_combinations_1d(self, context: list[str]) -> pd.DataFrame:
        """Returns a DataFrame of all the 1D output objects that match the context.

        For example, the context may be :code:`['channel']` or :code:`['channel', 'flow']`. The return DataFrame
        is a filtered version of the :code:`oned_objs` DataFrame that matches the context.

        Parameters
        ----------
        context : list[str]
            The context to filter the 1D objects by.

        Returns
        -------
        pd.DataFrame
            The filtered 1D objects
        """
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
            j = len(ctx) - 1
            for i, x in enumerate(reversed(ctx.copy())):
                if get_standard_data_type_name(x) in ctx1:
                    ctx.pop(j - i)

        # ids
        if ctx:
            df = df[df['id'].str.lower().isin(ctx)]

        return df if not df.empty else pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt', 'domain'])
