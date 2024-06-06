from typing import TYPE_CHECKING, Union

import pandas as pd

from pytuflow.results.result_util import ResultUtil

if TYPE_CHECKING:
    from .abc.channels import Channels
    from .abc.nodes import Nodes

class LP_1D:
    """Class for generating long profiles for 1D channels."""

    def __init__(self, channels: 'Channels', nodes: 'Nodes', ids: list[str] = ()) -> None:
        """
        Parameters
        ----------
        channels : Channels
            Channels object
        nodes : Nodes
            Nodes object
        ids : list[str], optional
            List of channel IDs, by default []
        """
        self._static_types = []
        self._temp_types = []
        self._utils = ResultUtil(channels, nodes)
        self._columns = ['US Node', 'DS Node', 'Flags', 'Length', 'US Invert', 'DS Invert', 'LBUS Obvert',
                         'LBDS Obvert']
        #: :doc:`Channels <pytuflow.results.Channels>`: Channels object
        self.channels = channels
        #: :doc:`Nodes <pytuflow.results.Nodes>`: Nodes object
        self.nodes = nodes
        #: list[str]: List of channel IDs
        self.ids = ids
        #: pd.DataFrame: DataFrame to store the long profile data
        self.df = pd.DataFrame([], columns=['Channel'] + self._columns + ['Branch ID'])
        #: pd.DataFrame: DataFrame to store the static data
        self.df_static = pd.DataFrame([], columns=['Offset'])
        #: pd.DataFrame: DataFrame to store the temporal data
        self.df_temp = pd.DataFrame([])

    def __repr__(self) -> str:
        if hasattr(self, 'ids'):
            return f'<LongProfile 1D: {" ".join(self.ids)}>'
        return '<LongProfile 1D>'

    def __eq__(self, other: any) -> bool:
        return sorted([x.lower() for x in self.ids]) == sorted([x.lower() for x in other.ids])

    def connectivity(self) -> None:
        """Calculate connectivity between channels. More than one ID is allowed, but all channels
        must connect to a common downstream channel.
        """
        branches = []
        if len(self.ids) == 1:
            conn = Connectivity(self.channels, self.ids[0], None)
            branches.extend(conn.branches)
        else:
            # more than 1 id - find a connection
            ds_id = None
            for id1 in self.ids:
                for id2 in self.ids:
                    if id1 == id2:
                        continue
                    conn = Connectivity(self.channels, id1, id2)
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
                conn = Connectivity(self.channels, id_, ds_id)
                if conn.connected:
                    branches.extend(conn.branches)

        # merge branches
        df = pd.DataFrame([], columns=['Channel'] + self._columns + ['Branch ID'])
        df['Branch ID'] = df['Branch ID'].astype(int)
        for i, branch in enumerate(branches):
            df_ = self.channels.df.loc[branch, self._columns]
            df_['Branch ID'] = [i for _ in range(df_.shape[0])]
            df_.reset_index(inplace=True)
            df = pd.concat([df, df_], ignore_index=True, axis=0) if not df.empty else df_

        self.df = df

    def long_plot(self, result_type: list[str], timestep_index: int) -> pd.DataFrame:
        """Generate a long plot for the given result types and timestep index.
        Returns a DataFrame with the connected channel IDs, node IDs, offsets and requested result types.

        The returned DataFrame uses a 4 level multi-level row index:

        :code:`Branch ID / Node ID / Channel ID / Offset`

        Parameters
        ----------
        result_type : list[str]
            List of result types to plot
            Result types can be static, temporal or maximum values
        timestep_index : int
            Time-step index to plot. Must be valid.

        Returns
        -------
        pd.DataFrame
            Long plot results.
        """
        # work out different result types
        _, static_types = self.extract_static_results(result_type)
        max_types = [x for x in result_type if x not in static_types and 'max' in x.lower()]
        temp_types = [x for x in result_type if x not in static_types and x not in max_types]

        # extract data for each result type group
        df = self.static_data(static_types)
        df = pd.concat([df, self.temporal_data(temp_types, timestep_index)], axis=1)
        return pd.concat([df, self.max_data(max_types)], axis=1)

    def static_data(self, result_types: list[str] = ()) -> pd.DataFrame:
        """Routine to extract static data (excluding maximums).
        Returns a DataFrame with the connected channel IDs, node IDs, offsets and requested result types.
        Can be called with an empty result_type list to return the channel IDs, node IDs and offsets only.

        Parameters
        ----------
        result_types : list[str], optional
            Static result types (excluding maximums) that should be returned. By default []

        Returns
        -------
        pd.DataFrame
            Static long plot data.
        """
        if self.df.empty:
            raise ValueError('Connectivity must be calculated before static data, or connection between ids not found')

        if not self.df_static.empty and result_types == self._static_types:
            return self.df_static

        self._static_types = result_types

        # initialise df with channel and node ids
        df = pd.melt(
            self.df.reset_index(),
            id_vars=[ 'Branch ID', 'Channel', 'index'],
            value_vars=['US Node', 'DS Node']
        )
        df[['index']] = df[['index']] * 2
        df.loc[df['variable'] == 'DS Node', 'index'] = df[df['variable'] == 'DS Node'][['index']] + 1
        df = df.sort_values('index')[['Branch ID', 'Channel', 'value']].rename(columns={'value': 'Node'})

        # offsets - always required
        if self.df_static.empty:
            offset = 0.
            offsets = []
            branch_id = 0
            for _, row in self.df[['Length', 'Branch ID']].iterrows():
                if row['Branch ID'] != branch_id:
                    offset = 0.
                    branch_id = row['Branch ID']
                offsets.append(offset)
                offset += row['Length']
                offsets.append(offset)
            df['Offset'] = offsets
        else:
            df['Offset'] = self.df_static[['Offset']]

        # other static result types
        for result_type in result_types:
            if result_type in self.df_static.columns:
                df[result_type] = self.df_static[result_type]
            elif 'bed' in result_type.lower():
                y = []
                for row in self.df.iterrows():
                    y.append(row[1]['US Invert'])
                    y.append(row[1]['DS Invert'])
                df[result_type] = y
            elif 'pit' in result_type.lower():
                df[result_type] = self._utils.extract_pit_levels(self.df)
            elif 'culvert' in result_type.lower() or 'pipe' in result_type.lower():
                df[result_type] = self._utils.extract_culvert_obvert(self.df)

        self.df_static = df.set_index('Branch ID')
        return self.df_static

    def temporal_data(self, result_types: list[str], timestep_index: int) -> pd.DataFrame:
        """Routine to extract temporal data at the given timestep index.
        Returns a DataFrame with the extracted data, however does not include static data such as offsets or channel ID.

        Parameters
        ----------
        result_types : list[str]
            List of temporal result types to extract
        timestep_index : int
            Time-step index to extract. Must be valid.

        Returns
        -------
        pd.DataFrame
            Temporal long plot data.
        """
        if self.df.empty:
            raise ValueError('Connectivity must be calculated before static data, or connection between ids not found')

        if not self.df_temp.empty and result_types == self._temp_types:
            return self.df_temp

        self._temp_types = result_types

        # convert connected channels into a node list
        nodes = pd.melt(
            self.df.reset_index(),
            id_vars=['Branch ID', 'index'],
            value_vars=['US Node', 'DS Node']
        )
        nodes[['index']] = nodes[['index']] * 2
        nodes.loc[nodes['variable'] == 'DS Node', 'index'] = nodes[nodes['variable'] == 'DS Node'][['index']] + 1
        nodes = nodes.sort_values('index')[['Branch ID', 'value']].rename(columns={'value': 'Node'})

        nodes.reset_index(drop=True, inplace=True)
        for result_type in result_types:
            if result_type.lower() in [x.lower() for x in self.df_static.columns]:
                i = [x.lower() for x in self.df_static.columns].index(result_type.lower())
                nodes[result_type] = self.df_temp.iloc[:, i]
            else:
                y = self.nodes.val(nodes['Node'], result_type, timestep_index)
                if not y.empty:
                    nodes[result_type] = y[result_type].tolist()

        nodes.set_index(['Branch ID'], inplace=True)
        nodes.drop(columns=['Node'], inplace=True)
        return nodes

    def max_data(self, result_types: list[str]) -> pd.DataFrame:
        """Routine to extract maximum data.
        Returns a DataFrame with the extracted data, however does not include static data such as offsets or channel ID.

        Parameters
        ----------
        result_types : list[str]
            List of maximum result types to extract

        Returns
        -------
        pd.DataFrame
            Maximum long plot data.
        """
        if self.df.empty:
            raise ValueError('Connectivity must be calculated before static data, or connection between ids not found')

        # convert connected channels into a node list
        nodes = pd.melt(
            self.df.reset_index(),
            id_vars=['Branch ID', 'index'],
            value_vars=['US Node', 'DS Node']
        )
        nodes[['index']] = nodes[['index']] * 2
        nodes.loc[nodes['variable'] == 'DS Node', 'index'] = nodes[nodes['variable'] == 'DS Node'][['index']] + 1
        nodes = nodes.sort_values('index')[['Branch ID', 'value']].rename(columns={'value': 'Node'})

        nodes.reset_index(drop=True, inplace=True)
        if result_types:
            df = self.nodes.get_maximum(nodes['Node'], result_types)
            df.columns = df.columns.get_level_values('Result Type')
            df.reset_index(drop=True, inplace=True)
            nodes = pd.concat([nodes, df], axis=1)

        nodes.set_index(['Branch ID'], inplace=True)
        nodes.drop(columns=['Node'], inplace=True)
        return nodes

    @staticmethod
    def extract_static_results(result_types: list[str]) -> tuple[list[str], list[str]]:
        """Extract static result types from the given list.
        Returns two lists, one with the original list of result types (but only the static types), and the
        other is a list of the static types but with corrected names.

        Parameters
        ----------
        result_types : list[str]
            List of result types to extract static types from

        Returns
        -------
        tuple[list[str], list[str]]
            static result types - original names, corrected names
        """
        STATIC_TYPE_KEYWORDS = ['bed', 'pit', 'pipe']
        STATIC_TYPES = ['Bed Level', 'Pit Ground Elevation', 'Pipe Obvert']
        static_result_types = [x for x in result_types if [y for y in STATIC_TYPE_KEYWORDS if y in x.lower()]]
        correct_names = sum([[x for i, x in enumerate(STATIC_TYPES) if STATIC_TYPE_KEYWORDS[i] in y.lower()] for y in result_types], [])
        return static_result_types, correct_names


class Connectivity:
    """Class to help calculate connectivity between channels."""

    def __init__(self, channels: 'Channels', id1: str, id2: Union[str, None]) -> None:
        #: :doc:`Channels <pytuflow.results.Channels>`: Channels object
        self.channels = channels
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
        for id_ in self.channels.downstream_channels(id1):
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
