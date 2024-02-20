from datetime import datetime
from pathlib import Path
from typing import Union
from ..types import PathLike
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from ..lp_1d import LP_1D
from ..time_util import closest_time_index
from ..iterator_util import Iterator


class TimeSeriesResult(ABC):
    """
    Abstract base class for TUFLOW time series results.

    Methods requiring implementation:
        load() -> None

    e.g. time series results that subclass this:
      - TPC
      - GPKG_TS
      - INFO

    This class can also be used for other plot data such as 1d_ta_tables_check file and bc_check files.
    """

    def __init__(self, fpath: PathLike, *args, **kwargs) -> None:
        super().__init__()
        self.fpath = Path(fpath)
        self.units = ''
        self.sim_id = ''
        self.channels = None
        self.nodes = None
        self.po = None
        self.rl = None
        self.lp_1d = None
        self.reference_time = datetime(1990, 1, 1)
        self.load()

    @abstractmethod
    def load(self, *args, **kwargs) -> None:
        """Load the result file. Called by __init__."""
        raise NotImplementedError

    def init_iterator(self, *args) -> Iterator:
        """Initialise the class iterator."""
        if args:
            return Iterator(*args)
        return Iterator(self.channels, self.nodes, self.po, self.rl)

    def channel_count(self) -> int:
        """Return the number of channels in the result file."""
        if self.channels:
            return self.channels.count()
        return 0

    def node_count(self) -> int:
        """Return the number of nodes in the result file."""
        if self.nodes:
            return self.nodes.count()
        return 0

    def po_count(self) -> int:
        """Return the number of 2d PO objects in the result file."""
        if self.po:
            return self.po.count()
        return 0

    def rl_count(self) -> int:
        """Return the number of 0d RL objects in the result file."""
        if self.rl:
            return self.rl.count()
        return 0

    def ids(self, result_type: Union[str, list[str]] = '', domain: str = '') -> list[str]:
        """
        Return a list ids for the given result type(s) and domain.

        :param result_type:
            The result type can be a single value or a list of values and can be
            the name of the result type (case in-sensitive) or be a well known short name
            e.g. 'Flow' - 'q', 'Velocity' - 'v', etc.
            If no result type is provided, all result types will be assumed to be all available.
        :param domain:
            Domain can be '1d', '2d', '0d' and will limit the returned ids by the domain. A secondary domain option
            can be passed to further limit the ids e.g. '1d node' or '1d channel'. If no domain is provided, all domains
            will be searched.
        """
        iter = self.init_iterator()
        ids = []
        for item in iter.id_result_type([], result_type, domain, 'temporal'):
            for id_ in item.ids:
                if id_ not in ids:
                    ids.append(id_)
        return ids

    def channel_ids(self, result_type: Union[str, list[str]] = '') -> list[str]:
        """
        Returns the channel ids for the given result type(s).

        :param result_type:
            The result type can be a single value or a list of values and can be
            the name of the result type (case in-sensitive) or be a well known short name
            e.g. 'Flow' - 'q', 'Velocity' - 'v', etc.
            If no result type is provided, all result types will be assumed to be all available.
        """
        if self.channels:
            if not result_type:
                return self.channels.ids(None)
            return self.ids(result_type, '1d channel')
        return []

    def node_ids(self, result_type: Union[str, list[str]] = '') -> list[str]:
        """
        Returns the node ids for the given result type.

        :param result_type:
            The result type can be a single value or a list of values and can be
            the name of the result type (case in-sensitive) or be a well known short name
            e.g. 'Water Level' - 'h', 'Energy' - 'e', etc.
            If no result type is provided, all result types will be assumed to be all available.
        """
        if self.nodes:
            if not result_type:
                return self.nodes.ids(None)
            return self.ids(result_type, '1d node')
        return []

    def po_ids(self, result_type: Union[str, list[str]] = '') -> list[str]:
        """
        Returns the PO ids for the given result type(s).

        :param result_type:
            The result type can be a single value or a list of values and can be
            the name of the result type (case in-sensitive) or be a well known short name
            e.g. 'Flow' - 'q', 'Velocity' - 'v', etc.
            If no result type is provided, all result types will be assumed to be all available.
        """
        if self.po:
            if not result_type:
                return self.po.ids(None)
            return self.ids(result_type, '2d')
        return []

    def rl_ids(self, result_type: Union[str, list[str]] = '') -> list[str]:
        """
        Returns the channel ids for the given result type(s).

        :param result_type:
            The result type can be a single value or a list of values and can be
            the name of the result type (case in-sensitive) or be a well known short name
            e.g. 'Flow' - 'q', 'Volume' - 'vol', etc.
            If no result type is provided, all result types will be assumed to be all available.
        """
        if self.rl:
            if not result_type:
                return self.rl.ids(None)
            return self.ids(result_type, '0d')
        return []

    def result_types(self, id: Union[str, list[str]] = '', domain: str = '') -> list[str]:
        """
        Returns a list of result types for the given id(s) and domain.

        :param id:
            The ID can be a single value or a list of values. The ID values are case in-sensitive.
            If no ID is provided, all IDs will be searched (within the provided domain).
        :param domain:
            The domain can be '1d', '2d', '0d' and will limit the returned result types by the domain.
            A secondary domain option can be passed to further limit the ids
            e.g. '1d node' or '1d channel'.
            If no domain is provided, all domains will be searched.
        """
        iter = self.init_iterator()
        result_types = []
        for item in iter.id_result_type(id, [], domain, 'temporal'):
            for rt in item.result_types:
                if rt not in result_types:
                    result_types.append(rt)
        return result_types

    def channel_result_types(self, id: Union[str, list[str]] = '') -> list[str]:
        """
        Returns a list of the result types for the given channel id(s).

        :param id:
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be searched.
        """
        if self.channels:
            if not id:
                return self.channels.result_types(None)
            return self.result_types(id, '1d channel')
        return []

    def node_result_types(self, id: Union[str, list[str]] = '') -> list[str]:
        """
        Returns a list of the result types for the given node id(s).

        :param id:
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be searched.
        """
        if self.nodes:
            if not id:
                return self.nodes.result_types(None)
            return self.result_types(id, '1d node')
        return []

    def po_result_types(self, id: Union[str, list[str]] = '') -> list[str]:
        """
        Returns a list of the result types for the given 2d PO id(s).

        :param id:
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be searched.
        """
        if self.po:
            if not id:
                return self.po.result_types(None)
            return self.result_types(id, '2d')
        return []

    def rl_result_types(self, id: Union[str, list[str]] = '') -> list[str]:
        """
        Returns a list of the result types for the given 0d RL id(s).

        :param id:
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be searched.
        """
        if self.rl:
            if not id:
                return self.rl.result_types(None)
            return self.result_types(id, '0d')
        return []

    def long_plot_result_types(self) -> list[str]:
        """Returns a list of result types available for long plotting."""
        if self.nodes:
            return self.nodes.long_plot_result_types()
        return []

    def timesteps(self, domain: str = '', dtype: str = 'relative') -> list[Union[float, datetime]]:
        """
        Returns a list of time-steps available for the given domain.

        :param domain:
            The domain can be '1d', '2d', '0d' and will limit the returned time-steps by the domain.
        :param dtype:
            The return type can be either 'relative' e.g. hours or 'absolute' e.g. datetime.
            Default is 'relative'.
        """
        iter = self.init_iterator()
        domains = []
        timesteps = []
        for item in iter.id_result_type([], [], domain, 'temporal'):
            if item.result_item.domain not in domains:
                domains.append(item.result_item.domain)
                for timestep in item.result_item.timesteps(dtype):
                    if timestep not in domains:
                        timesteps.append(timestep)
        return sorted(timesteps)

    def time_series(self,
                    id: Union[str, list[str]],
                    result_type: Union[str, list[str]],
                    domain: str = None,
                    use_common_index: bool = True
                    ) -> pd.DataFrame:
        """
        Extract time series data for the given id(s), result type(s), and domain and returned as a DataFrame.

        :param id:
            ID can be either a single value or list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be returned (within the provided domain).
        :param result_type:
            The result type can be a single value or a list of values and can be
            the name of the result type (case in-sensitive) or be a well known short name
            e.g. 'Water Level' - 'h', 'Energy' - 'e', etc.
            If no result type is provided, all result types will be assumed to be all available.
        :param domain:
            The domain can be '1d', '2d', '0d' and will limit the returned time series by the domain.
            A secondary domain option can be passed to further limit the ids
            e.g. '1d node' or '1d channel'.
            If no domain is provided, all domains will be searched.
        :param use_common_index:
            If True, the DataFrame will be returned with a single index column for all the result types (if a
            common index exists). If set to False, each result type value will be returned with a preceding
            index column.
        """
        # collect all time-series data into a single DataFrame
        df = pd.DataFrame()
        iter = self.init_iterator()
        for item in iter.id_result_type(id, result_type, domain, 'temporal'):
            df_ = item.result_item.get_time_series(item.ids, item.result_types)
            df = pd.concat([df, df_.reset_index(drop=True)], axis=1)

        # if a common index exists (e.g. all result types share the same timesteps) then set this as index
        # and remove all duplicate columns.
        if use_common_index:
            common_index_exists = True
            df_ = df.xs('Index', level='Index/Value', axis=1)
            a = df_.to_numpy()
            for i in range(1, a.shape[1]):
                if not np.isclose(a[:, 0], a[:, i], equal_nan=True, atol=0.001).all():  # allow for some tolerance
                    common_index_exists = False
                    break
            if common_index_exists:
                index_name = df.columns[0]
                df.set_index(index_name, inplace=True)
                df.index.name = index_name[-1]
                df = df.xs('Value', level='Index/Value', axis=1)
                df.columns = df.columns.droplevel('Index Name')

        return df.dropna(how='all')

    def maximum(self,
                id: Union[str, list[str]],
                result_type: Union[str, list[str]],
                domain: str = None
                ) -> pd.DataFrame:
        """
        Extract maximum, and time of max data for the given id(s) and result type(s) and return as a DataFrame.

        :param id:
            ID can be either a single value or list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be returned (within the provided domain).
        :param result_type:
            The result type can be a single value or a list of values and can be
            the name of the result type (case in-sensitive) or be a well known short name
            e.g. 'Water Level' - 'h', 'Energy' - 'e', etc.
            If no result type is provided, all result types will be assumed to be all available.
        :param domain:
            The domain can be '1d', '2d', '0d' and will limit the returned time series by the domain.
            A secondary domain option can be passed to further limit the ids
            e.g. '1d node' or '1d channel'.
            If no domain is provided, all domains will be searched.
        """
        df = pd.DataFrame()
        iter = self.init_iterator()
        for item in iter.id_result_type(id, result_type, domain, 'max'):
            df_ = item.result_item.get_maximum(item.ids, item.result_types)
            df_.rename(columns={x: f'{item.result_item_name}::{x}' for x in df_.columns}, inplace=True)
            if df.empty:
                df = df_
            else:
                df = pd.concat([df, df_], axis=1)
        return df

    def long_plot(self,
                  ids: Union[str, list[str]],
                  result_type: Union[str, list[str]],
                  time: Union[float, datetime]
                  ) -> pd.DataFrame:
        """
        Extract long plot data for the given channel ids(s), node result type(s), and time and return as a DataFrame.
        At least one ID must be provided.

        If one ID is provided, the long plot will start from that channel ID and proceed downstream
        to the outlet.
        If multiple IDs are provided, the long plot will connect the IDs. The IDs are required to be connected.
        e.g. if 2 IDs are provided one ID must be downstream of the other ID. If 3 IDs are provided, on ID must be
        downstream of the other 2.

        :param ids:
            ID can be either a single value or list of values. The ID value(s) are case in-sensitive.
        :param result_type:
            The result type can be a single value or a list of values and can be
            the name of the result type (case in-sensitive) or be a well known short name
            e.g. 'Water Level' - 'h', 'Energy' - 'e', etc.
            If no result type is provided, all result types will be assumed to be all available.
        :param time:
            The time-step to extract the long plot data for. The format can be either as a relative time-step (float)
            or as an absolute time-step (datetime).
            The time-step has a tolerance of 0.001 hrs and if no time-step is found,
            the previous time-step will be used.
        """
        if not ids:
            raise ValueError('No ids provided')

        iter = self.init_iterator()
        for item in iter.lp_id_result_type(ids, result_type):
            df = self.connectivity(item.ids)
            if df.empty:
                return pd.DataFrame([], columns=['Offset'] + result_type)

            timestep_index = closest_time_index(self.timesteps(domain='1d'), time)

            return self.lp_1d.long_plot(item.result_types, timestep_index)

    def connectivity(self, ids: Union[str, list[str]]) -> pd.DataFrame:
        """
        Return the connectivity for the given channel ID(s) as a DataFrame with relevant information.
        At least one ID must be provided.

        If one ID is provided, the long plot will start from that channel ID and proceed downstream
        to the outlet.
        If multiple IDs are provided, the long plot will connect the IDs. The IDs are required to be connected.
        e.g. if 2 IDs are provided one ID must be downstream of the other ID. If 3 IDs are provided, on ID must be
        downstream of the other 2.

        :param ids:
            ID can be either a single value or list of values. The ID value(s) are case in-sensitive.
        """
        if not isinstance(ids, list):
            ids = [ids] if ids is not None else []

        ids_lower = [str(x).lower() for x in self.channel_ids()]
        ids_ = []
        for id_ in ids:
            if str(id_).lower() not in ids_lower:
                raise ValueError(f'Invalid channel id: {id_}')
            else:
                i = ids_lower.index(str(id_).lower())
                ids_.append(self.channel_ids()[i])
        ids = ids_

        lp = LP_1D(self.channels, self.nodes, ids)
        if self.lp_1d is not None and lp == self.lp_1d:
            return self.lp_1d.df

        lp.connectivity()
        self.lp_1d = lp
        return lp.df
