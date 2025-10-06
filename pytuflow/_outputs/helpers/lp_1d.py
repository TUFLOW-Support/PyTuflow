import typing
from typing import Union, Generator

import pandas as pd


class LP1D:
    """Class for generating long profiles for 1D channels."""

    def __init__(self, ids: list[str], node_info: pd.DataFrame, chan_info: pd.DataFrame) -> None:
        # private
        self._columns = ['us_node', 'ds_node', 'ispipe', 'length', 'us_invert', 'ds_invert', 'lbus_obvert', 'lbds_obvert']
        self._static_types = []
        self._temp_types = []

        # get the case-sensitive ID from the chan_info index
        ids = self._init_ids(ids, chan_info, node_info)

        #: list[str]: The IDs to trace for connectivity
        self.ids = ids
        #: pd.DataFrame: Node information. Column headers are 'id', 'bed_level', 'top_level', 'nchannel', 'channels'
        self.node_info = node_info
        #: pd.DataFrame: Channel information. Column headers are 'id', 'us_node', 'ds_node', 'us_chan', 'ds_chan', 'length', 'us_invert', 'ds_invert', 'lbus_obvert', 'rbus_obvert', 'lbds_obvert', 'rbds_obvert'
        self.chan_info = chan_info
        #: pd.DataFrame: The connectivity data.
        self.df = pd.DataFrame(columns=['channel'] + self._columns + ['branch_id'])
        #: pd.DataFrame: The static data.
        self.df_static = pd.DataFrame(columns=['offset'])
        #: pd.DataFrame: The temporal data.
        self.df_temp = pd.DataFrame()

    def __repr__(self) -> str:
        if hasattr(self, 'ids'):
            return f'<LongProfile 1D: {" ".join(self.ids)}>'
        return '<LongProfile 1D>'

    def __eq__(self, other: typing.Any) -> bool:
        """Override the equality operator so that it checks against the ids it's connecting."""
        return sorted([x.lower() for x in self.ids]) == sorted([x.lower() for x in other.ids])

    def _merge_branches(self, branches: list[list[str]]) -> pd.DataFrame:
        df = pd.DataFrame([], columns=['channel'] + self._columns + ['branch_id'])
        df['branch_id'] = df['branch_id'].astype(int)
        for i, branch in enumerate(branches):
            df_ = self.chan_info.loc[branch, self._columns]
            df_.index.name = 'channel'
            df_['branch_id'] = [i for _ in range(df_.shape[0])]
            df_.reset_index(inplace=True)
            df = pd.concat([df, df_], ignore_index=True, axis=0) if not df.empty else df_
        return df

    def connectivity(self) -> None:
        """Calculate connectivity between channels. More than one ID is allowed, but all channels
        must connect to a common downstream channel.
        """
        branches = []
        if len(self.ids) == 1:
            conn = Connectivity(self.chan_info, self.node_info, self.ids[0], None)
            branches.extend(conn.branches)
        else:
            # more than 1 id - find a connection
            ds_id = None
            for id1 in self.ids:
                for id2 in self.ids:
                    if id1 == id2:
                        continue
                    conn = Connectivity(self.chan_info, self.node_info, id1, id2)
                    if conn.connected:
                        ds_id = conn.id2
                        break
                if ds_id:
                    break

            if ds_id is None:
                raise ValueError(f'Could not find a connection between {self.ids}')

            # connect all ids
            branches = []
            for id_ in self.ids:
                if id_ == ds_id:
                    continue
                conn = Connectivity(self.chan_info, self.node_info, id_, ds_id)
                if conn.connected:
                    branches.extend(conn.branches)

        self.df = self._merge_branches(branches)

    def init_lp(self, conn_df: pd.DataFrame) -> pd.DataFrame:
        """Initialise the long plot DataFrame. The initialised DataFrame will contain data on
        the channels, connected nodes, and offsets.

        Parameters
        ----------
        conn_df : pd.DataFrame
            Connectivity DataFrame.

        Returns
        -------
        pd.DataFrame
            Initialised long plot DataFrame.
        """
        df = self.melt_2_columns(conn_df, ['us_node', 'ds_node'], 'node')

        # offsets
        offset = 0.
        offsets = []
        branch_id = 0
        for _, row in self.df[['length', 'branch_id']].iterrows():
            if row['branch_id'] != branch_id:
                offset = 0.
                branch_id = row['branch_id']
            offsets.append(offset)
            offset += row['length']
            offsets.append(offset)
        df['offset'] = offsets

        return df

    @staticmethod
    def melt_2_columns(conn_df: pd.DataFrame, value_vars: list[str], new_col_name: str) -> pd.DataFrame:
        df = pd.melt(
            conn_df.reset_index(),
            id_vars=['branch_id', 'channel', 'index'],
            value_vars=value_vars
        )
        df[['index']] = df[['index']] * 2
        df.loc[df['variable'] == value_vars[1], 'index'] = df[df['variable'] == value_vars[1]][['index']] + 1
        return df.sort_values('index')[['branch_id', 'channel', 'value']].rename(columns={'value': new_col_name})

    def _init_ids(self, ids: list[str], chan_info: pd.DataFrame, node_info: pd.DataFrame) -> list[str]:
        ids1 = []
        for id_ in ids:
            try:
                id1 = chan_info.index[chan_info.index.str.lower() == id_.lower()].values[0]
                ids1.append(id1)
            except IndexError:
                raise ValueError(f'Could not find ID: {id_}')
        return ids1


class Connectivity:
    """Class to help calculate connectivity between channels."""

    def __init__(self, chan_info: pd.DataFrame, node_info: pd.DataFrame, id1: str, id2: Union[str, None]) -> None:
        #: :pd.DataFrame: chan_info
        self.chan_info = chan_info
        #: :pd.DataFrame: node_info
        self.node_info = node_info
        #: str: Upstream channel ID
        self.id1 = id1
        #: str: Downstream channel ID
        self.id2 = id2
        #: list[list[str]]: List of branches
        self.branches = []
        #: bool: True if connected
        self.connected = False
        self.connect()

    def connect(self) -> None:
        """Calculate connectivity between channels given two IDS.
        If id2 is None, then connectivity will be calculated all the way to the outlet.
        """
        connected = self._connect(self.id1, self.id2, [])
        if connected:
            self.connected = True
            return
        if self.id2 is None:
            return
        id1, id2 = self.id2, self.id1
        connected = self._connect(id1, id2, [])
        if connected:
            self.connected = True
            self.id1, self.id2 = id1, id2

    def _connect(self, id1: str, id2: Union[str, None], branch: list[str]) -> bool:
        """Private routine to calculate connectivity between 2 channels. Uses binary tree type search so that
        multiple branches can be found/searched.
        Returns True/False depending on whether a connection was found.

        :param id1:
            Upstream channel ID
        :param id2:
            Downstream channel ID
        :param branch:
            List of channel IDs that form a branch
            This will be added to as the routine searches for a connection.
        """
        finished = False
        if id1 not in branch:
            branch.append(id1)
        one_connection = False
        for id_ in self._downstream_channels(id1):
            one_connection = True
            finished = id_ in branch[:-1] or id_ == id2
            if finished:
                if id_ not in branch:
                    branch.append(id_)
                self.branches.append(branch)
            if not finished:
                finished = self._connect(id_, id2, branch.copy())

        if not one_connection and id2 is None:
            finished = True
            self.branches.append(branch)

        return finished

    def _downstream_channels(self, id_: str) -> Generator[str, None, None]:
        """Yield downstream channels given a channel ID."""
        nd = self.chan_info.loc[id_, 'ds_node']
        channels = list(self.node_info.loc[nd, 'channels']) if self.node_info.loc[nd, 'nchannel'] > 1 else [self.node_info.loc[nd, 'channels']]
        for chan in sorted(channels, key=lambda x: {True: 0, False: 1}[self.chan_info.loc[id_, 'ds_channel'] == x if 'ds_channel' in self.chan_info else 0]):
            us_node = self.chan_info.loc[chan, 'us_node']
            if us_node == nd:
                yield chan
