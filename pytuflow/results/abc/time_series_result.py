from datetime import datetime
from pathlib import Path
from typing import Union
from pytuflow.types import PathLike
from abc import ABC, abstractmethod

import numpy as np
import pandas as pd

from ..lp_1d import LP_1D
from pytuflow.util.time_util import closest_time_index
from ..iterator_util import Iterator
from pytuflow.types import TimeLike


class TimeSeriesResult(ABC):
    """
    Abstract base class for TUFLOW time series results.

    | Methods requiring overriding:
    |    :code:`load() -> None`
    |    :code:`looks_like_self(fpath: Path) -> bool`
    |    :code:`looks_empty(fpath: Path) -> bool`

    This class can also be used for other plot data such as 1d_ta_tables_check file and bc_check files.

    """

    def __init__(self, fpath: PathLike, *args, **kwargs) -> None:
        super().__init__()
        #: Path: The path to the result file.
        self.fpath = Path(fpath)
        #: str: The units of the result file, 'metric' or 'imperial'.
        self.units = ''
        #: str: The simulation ID.
        self.sim_id = ''
        #: :doc:`Channels<pytuflow.results.Channels>`: Channels result class object if available.
        self.channels = None
        #: :doc:`Nodes<pytuflow.results.Nodes>`: Nodes result class object if available.
        self.nodes = None
        #: :doc:`PO<pytuflow.results.PO>`: 2D PO result class object if available.
        self.po = None
        #: :doc:`RL<pytuflow.results.RL>`: RL result class object if available.
        self.rl = None
        #: LP_1D: Long plot class object if available.
        self.lp_1d = None
        #: datetime: Result reference time.
        self.reference_time = datetime(1990, 1, 1)
        if not self.fpath.exists():
            raise FileNotFoundError(f'File not found: {self.fpath}')
        if not self.looks_like_self(self.fpath):
            raise ValueError(f'File does not look like {self.__class__.__name__}')
        if self.looks_empty(self.fpath):
            raise ValueError(f'Empty results: {self.fpath}')
        self.load()

    @staticmethod
    @abstractmethod
    def looks_like_self(fpath: Path) -> bool:
        """Return True if the file looks like this class.

        Parameters
        ----------
        fpath : Path
            The file path to check.

        Returns
        -------
        bool
            True if the file looks like this class.
        """
        raise NotImplementedError

    @abstractmethod
    def looks_empty(self, fpath: Path) -> bool:
        """Return True if the file looks empty.

        Parameters
        ----------
        fpath : Path
            The file path to check.

        Returns
        -------
        bool
            True if the file looks empty.
        """
        raise NotImplementedError

    @abstractmethod
    def load(self, *args, **kwargs) -> None:
        """Loads the file. Automatically called on initialisation."""
        raise NotImplementedError

    def init_iterator(self, *args) -> Iterator:
        """Initialise the result iterator class. The iterator is used to extract results given a set of IDs,
        result types, and domain.

        Returns
        -------
        Iterator
            Generator class for extracting results.
        """
        if args:
            return Iterator(*args)
        return Iterator(self.channels, self.nodes, self.po, self.rl)

    def channel_count(self) -> int:
        """
        Return the number of channels in the result file.

        Returns
        -------
        int
        """
        if self.channels:
            return self.channels.count()
        return 0

    def node_count(self) -> int:
        """Return the number of nodes in the result file.

        Returns
        -------
        int
        """
        if self.nodes:
            return self.nodes.count()
        return 0

    def po_count(self) -> int:
        """Return the number of 2d PO objects in the result file.

        Returns
        -------
        int
        """
        if self.po:
            return self.po.count()
        return 0

    def rl_count(self) -> int:
        """Return the number of 0d RL objects in the result file.

        Returns
        -------
        int
        """
        if self.rl:
            return self.rl.count()
        return 0

    def ids(self, result_type: Union[str, list[str]] = '', domain: str = '') -> list[str]:
        """Return a list IDs for the given result type(s) and domain.

        Domain can be '1d', '2d', or '0d'. A secondary domain option can also be added to the domain string using a
        space delim to further limit the IDs. Secondary domain options are 'node', 'channel', 'po', 'rl', 'boundary', or
        'cross_section'. If no domain is provided, all domains will be searched.

        Parameters
        ----------
        result_type : Union[str, list[str]], optional
            The result type can be a single value or a list of values. The result type can be the full name as
            returned by :meth:`result_types() <pytuflow.results.TPC.result_types>` (not case sensitivte) or a
            well known short name e.g. 'q', 'v', 'h' etc.  If no result type is provided, all result types will be
            searched (within the provided domain).
        domain : str, optional
            Domain can be '1d', '2d', or '0d'. A secondary domain option can also be added to the domain string using a
            space to further limit the IDs. Secondary domain options are 'node', 'channel', 'po', 'rl', 'boundary', or
            'cross_section'. If no domain is provided, all domains will be searched.

        Returns
        -------
        list[str]
            list of IDs
        """
        iter = self.init_iterator()
        ids = []
        for item in iter.id_result_type([], result_type, domain, 'temporal'):
            for id_ in item.ids:
                if id_ not in ids:
                    ids.append(id_)
        return ids

    def channel_ids(self, result_type: Union[str, list[str]] = '') -> list[str]:
        """Returns the channel IDs for the given result type(s).

        channel_ids() is equivalent to using '1d channel' as the domain in
        :meth:`ids() <pytuflow.results.TPC.ids>`.

        Parameters
        ----------
        result_type : Union[str, list[str]], optional
            The result type can be a single value or a list of values. The result type can be the full name as
            returned by :meth:`result_types() <pytuflow.results.TPC.result_types>` (not case sensitivte) or a
            well known short name e.g. 'q', 'v', 'h' etc. If no result type is provided, all result types will be
            searched.

        Returns
        -------
        list[str]
            list of IDs
        """
        if self.channels:
            if not result_type:
                return self.channels.ids(None)
            return self.ids(result_type, '1d channel')
        return []

    def node_ids(self, result_type: Union[str, list[str]] = '') -> list[str]:
        """Returns the node IDs for the given result type(s).

        node_ids() is equivalent to using '1d node' as the domain in
        :meth:`ids() <pytuflow.results.TPC.ids>`.

        Parameters
        ----------
        result_type : Union[str, list[str]], optional
            The result type can be a single value or a list of values. The result type can be the full name as
            returned by :meth:`result_types() <pytuflow.results.TPC.result_types>` (not case sensitivte) or a
            well known short name e.g. 'q', 'v', 'h' etc. If no result type is provided, all result types will be
            searched.

        Returns
        -------
        list[str]
            list of IDs
        """
        if self.nodes:
            if not result_type:
                return self.nodes.ids(None)
            return self.ids(result_type, '1d node')
        return []

    def po_ids(self, result_type: Union[str, list[str]] = '') -> list[str]:
        """Returns the PO IDs for the given result type(s).

        po_ids() is equivalent to using '2d' as the domain in
        :meth:`ids() <pytuflow.results.TPC.ids>`.

        Parameters
        ----------
        result_type : Union[str, list[str]], optional
            The result type can be a single value or a list of values. The result type can be the full name as
            returned by :meth:`result_types() <pytuflow.results.TPC.result_types>` (not case sensitivte) or a
            well known short name e.g. 'q', 'v', 'h' etc. If no result type is provided, all result types will be
            searched.

        Returns
        -------
        list[str]
            list of IDs
        """
        if self.po:
            if not result_type:
                return self.po.ids(None)
            return self.ids(result_type, '2d')
        return []

    def rl_ids(self, result_type: Union[str, list[str]] = '') -> list[str]:
        """Returns the RL IDs for the given result type(s).

        rl_ids() is equivalent to using '0d' as the domain in
        :meth:`ids() <pytuflow.results.TPC.ids>`.

        Parameters
        ----------
        result_type : Union[str, list[str]], optional
            The result type can be a single value or a list of values. The result type can be the full name as
            returned by :meth:`result_types() <pytuflow.results.TPC.result_types>` (not case sensitivte) or a
            well known short name e.g. 'q', 'v', 'h' etc. If no result type is provided, all result types will be
            searched.

        Returns
        -------
        list[str]
            list of IDs
        """
        if self.rl:
            if not result_type:
                return self.rl.ids(None)
            return self.ids(result_type, '0d')
        return []

    def result_types(self, id: Union[str, list[str]] = '', domain: str = '') -> list[str]:
        """Returns a list of result types for the given ID(s) and domain.

        Domain can be '1d', '2d', or '0d'. A secondary domain option can also be added to the domain string using a
        space delim to further limit the IDs. Secondary domain options are 'node', 'channel', 'po', 'rl', 'boundary', or
        'cross_section'. If no domain is provided, all domains will be searched.

        Parameters
        ----------
        id : Union[str, list[str]], optional
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be searched (within the provided domain).
        domain : str, optional
            Domain can be '1d', '2d', or '0d'. A secondary domain option can also be added to the domain string using a
            space to further limit the IDs. Secondary domain options are 'node', 'channel', 'po', 'rl', 'boundary', or
            'cross_section'. If no domain is provided, all domains will be searched.

        Returns
        -------
        list[str]
            list of result types.
        """
        iter = self.init_iterator()
        result_types = []
        for item in iter.id_result_type(id, [], domain, 'temporal'):
            for rt in item.result_types:
                if rt not in result_types:
                    result_types.append(rt)
        return result_types

    def channel_result_types(self, id: Union[str, list[str]] = '') -> list[str]:
        """Returns a list of the result types for the given channel ID(s).

        channel_result_types() is equivalent to using '1d channel' as the domain in
        :meth:`result_types() <pytuflow.results.TPC.result_types>`.

        Parameters
        ----------
        id : Union[str, list[str]], optional
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.

        Returns
        -------
        list[str]
            list of result types.
        """
        if self.channels:
            if not id:
                return self.channels.result_types(None)
            return self.result_types(id, '1d channel')
        return []

    def node_result_types(self, id: Union[str, list[str]] = '') -> list[str]:
        """Returns a list of the result types for the given channel ID(s).

        node_result_types() is equivalent to using '1d node' as the domain in
        :meth:`result_types() <pytuflow.results.TPC.result_types>`.

        Parameters
        ----------
        id : Union[str, list[str]], optional
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.

        Returns
        -------
        list[str]
            list of result types.
        """
        if self.nodes:
            if not id:
                return self.nodes.result_types(None)
            return self.result_types(id, '1d node')
        return []

    def po_result_types(self, id: Union[str, list[str]] = '') -> list[str]:
        """Returns a list of the result types for the given channel ID(s).

        po_result_types() is equivalent to using '2d' as the domain in
        :meth:`result_types() <pytuflow.results.TPC.result_types>`.

        Parameters
        ----------
        id : Union[str, list[str]], optional
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.

        Returns
        -------
        list[str]
            list of result types.
        """
        if self.po:
            if not id:
                return self.po.result_types(None)
            return self.result_types(id, '2d')
        return []

    def rl_result_types(self, id: Union[str, list[str]] = '') -> list[str]:
        """Returns a list of the result types for the given channel ID(s).

        rl_result_types() is equivalent to using '0d' as the domain in
        :meth:`result_types() <pytuflow.results.TPC.result_types>`.

        Parameters
        ----------
        id : Union[str, list[str]], optional
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.

        Returns
        -------
        list[str]
            list of result types.
        """
        if self.rl:
            if not id:
                return self.rl.result_types(None)
            return self.result_types(id, '0d')
        return []

    def long_plot_result_types(self) -> list[str]:
        """Returns a list of result types available for long plotting.

        Returns
        -------
        list[str]
            list of result types.
        """
        if self.nodes:
            return self.nodes.long_plot_result_types()
        return []

    def maximum_result_types(self, id: Union[str, list[str]] = '', domain: str = '') -> list[str]:
        """Returns a list of result types available for maximum extraction.

        Domain can be '1d', '2d', or '0d'. A secondary domain option can also be added to the domain string using a
        space delim to further limit the IDs. Secondary domain options are 'node', 'channel', 'po', 'rl', 'boundary', or
        'cross_section'. If no domain is provided, all domains will be searched.

        Parameters
        ----------
        id : Union[str, list[str]], optional
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be searched (within the provided domain).
        domain : str, optional
            Domain can be '1d', '2d', or '0d'. A secondary domain option can also be added to the domain string using a
            space to further limit the IDs. Secondary domain options are 'node', 'channel', 'po', 'rl', 'boundary', or
            'cross_section'. If no domain is provided, all domains will be searched.

        Returns
        -------
        list[str]
            list of result types.
        """
        iter = self.init_iterator()
        result_types = []
        for item in iter.id_result_type(id, [], domain, 'max'):
            for rt in item.result_types:
                if 'TMax' in rt:
                    continue
                rt = rt.replace(' Max', '')
                if rt not in result_types:
                    result_types.append(rt)
        return result_types

    def timesteps(self, domain: str = '', dtype: str = 'relative') -> list[TimeLike]:
        """Returns a list of time-steps available for the given domain.

        Domain can be '1d', '2d', or '0d'. A secondary domain option can also be added to the domain string using a
        space delim to further limit the IDs. Secondary domain options are 'node', 'channel', 'po', 'rl', 'boundary', or
        'cross_section'. If no domain is provided, all domains will be searched.

        Parameters
        ----------
        domain : str, optional
            Domain can be '1d', '2d', or '0d'. A secondary domain option can also be added to the domain string using a
            space to further limit the IDs. Secondary domain options are 'node', 'channel', 'po', 'rl', 'boundary', or
            'cross_section'. If no domain is provided, all domains will be searched.
        dtype : str, optional
            Determines the return type which can be either 'relative' e.g. hours or 'absolute' e.g. datetime.

        Returns
        -------
        list[TimeLike]
            list of timesteps as either float or datetime.
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
        """Extract time series data for the given ID(s), result type(s), and domain and returned as a pd.DataFrame.

        Parameters
        ----------
        id : Union[str, list[str]]
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be searched (within the provided domain).
        result_type : Union[str, list[str]]
            The result type can be a single value or a list of values. The result type can be the full name as
            returned by :meth:`result_types() <pytuflow.results.TPC.result_types>` (not case sensitivte) or a
            well known short name e.g. 'q', 'v', 'h' etc.  If no result type is provided, all result types will be
            searched (within the provided domain).
        domain : str, optional
            Domain can be '1d', '2d', or '0d'. A secondary domain option can also be added to the domain string using a
            space to further limit the IDs. Secondary domain options are 'node', 'channel', 'po', 'rl', 'boundary', or
            'cross_section'. If no domain is provided, all domains will be searched.
        use_common_index : bool, optional
            If True, the DataFrame will be returned with a single index column for all the result types (if a
            common index exists). If set to False, each result type value will be returned with a preceding
            index column e.g. a time column will precede each result type value column.

        Returns
        -------
        pd.DataFrame
            The returned pd.DataFrame uses multi-index columns consisting of three or four levels
            depending on whether a common time key exists (:code:`use_common_index=True` and result types are able
            to share a common time key).

            | Column Levels:
            | :code:`Source/Result Type/ID` e.g. :code:`Channel/Flow/FC01.1_R`
            | or if a common index does not exist, a fourth level will denote whether the column represents the index or value.
            | e.g. :code:`Channel/Flow/FC01.1_R/Time`
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
        """Extract maximum, and time of max data for the given ID(s) and result type(s) and return as a pd.DataFrame.

        Parameters
        ----------
        id : Union[str, list[str]]
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be searched (within the provided domain).
        result_type : Union[str, list[str]]
            The result type can be a single value or a list of values. The result type can be the full name as
            returned by :meth:`result_types() <pytuflow.results.TPC.result_types>` (not case sensitivte) or a
            well known short name e.g. 'q', 'v', 'h' etc.  If no result type is provided, all result types will be
            searched (within the provided domain).
        domain : str, optional
            Domain can be '1d', '2d', or '0d'. A secondary domain option can also be added to the domain string using a
            space to further limit the IDs. Secondary domain options are 'node', 'channel', 'po', 'rl', 'boundary', or
            'cross_section'. If no domain is provided, all domains will be searched.

        Returns
        -------
        pd.DataFrame
            The returned DataFrame uses a multi-index column consisting of two levels:

            :code:`Source/Result Type` e.g. :code:`Node/Water Level Max`

            The row index will consist of the ID values.
        """
        df = pd.DataFrame()
        iter = self.init_iterator()
        for item in iter.id_result_type(id, result_type, domain, 'max'):
            df_ = item.result_item.get_maximum(item.ids, item.result_types)
            df = pd.concat([df, df_], axis=1) if not df.empty else df_
        return df

    def long_plot(self,
                  ids: Union[str, list[str]],
                  result_type: Union[str, list[str]],
                  time: TimeLike
                  ) -> pd.DataFrame:
        """Extract long plot data for the given channel ID(s), node result type(s), and time and return as a DataFrame.
        At least one ID must be provided.

        If one ID is provided, the long plot will start from that channel ID and proceed downstream
        to the outlet. If multiple IDs are provided, the long plot will connect the IDs. The IDs are
        required to be connected.
        e.g. if 2 IDs are provided one ID must be downstream of the other ID. If 3 IDs are provided, one ID must be
        downstream of the other 2.

        Parameters
        ----------
        id : Union[str, list[str]]
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be searched (within the provided domain).
        result_type : Union[str, list[str]]
            The result type can be a single value or a list of values. The result type can be the full name as
            returned by :meth:`result_types() <pytuflow.results.TPC.result_types>` (not case sensitivte) or a
            well known short name e.g. 'q', 'v', 'h' etc.  If no result type is provided, all result types will be
            searched (within the provided domain).
        time : TimeLike
            The time-step to extract the long plot data for. The format can be either as a relative time-step (float)
            or as an absolute time-step (datetime).
            The time-step has a tolerance of 0.001 hrs and if no time-step is found,
            the closest previous time-step will be used.

        Returns
        -------
        pd.DataFrame
            The returned DataFrame containing channel and node IDs, offsets, and result types. Offset will reset
            to zero at the start of each long plot branch.
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
        """Return the connectivity for the given channel ID(s) as a DataFrame with relevant information.
        At least one ID must be provided.

        If one ID is provided, the long plot will start from that channel ID and proceed downstream
        to the outlet.
        If multiple IDs are provided, the long plot will connect the IDs. The IDs are required to be connected.
        e.g. if 2 IDs are provided one ID must be downstream of the other ID. If 3 IDs are provided, on ID must be
        downstream of the other 2.

        Parameters
        ----------
        ids : Union[str, list[str]]
            The ID value can be a single value or a list of values. The ID value(s) are case in-sensitive.
            If no ID is provided, all IDs will be searched (within the provided domain).

        Returns
        -------
        pd.DataFrame
            Information on the connectivity of the given channel ID(s).
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
