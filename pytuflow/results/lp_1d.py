from typing import TYPE_CHECKING, Union, Generator

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from .abc.channels import Channels
    from .abc.nodes import Nodes

class LP_1D:

    def __init__(self, channels: 'Channels', nodes: 'Nodes', ids: list[str] = ()) -> None:
        self._static_types = []
        self.channels = channels
        self.nodes = nodes
        self.ids = ids
        self.columns = ['US Node', 'DS Node', 'Flags', 'Length', 'US Invert', 'DS Invert', 'LBUS Obvert', 'LBDS Obvert']
        self.df = pd.DataFrame([], columns=['Channel'] + self.columns + ['Branch ID'])
        self.df_static = pd.DataFrame([], columns=['Offset'])

    def __repr__(self) -> str:
        if hasattr(self, 'ids'):
            return f'<LongProfile 1D: {" ".join(self.ids)}>'
        return '<LongProfile 1D>'

    def __eq__(self, other: any) -> bool:
        return sorted([x.lower() for x in self.ids]) == sorted([x.lower() for x in other.ids])

    def connectivity(self) -> None:
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
        df = pd.DataFrame([], columns=['Channel'] + self.columns + ['Branch ID'])
        df['Branch ID'] = df['Branch ID'].astype(int)
        for i, branch in enumerate(branches):
            df_ = self.channels._df.loc[branch, self.columns]
            df_['Branch ID'] = [i for _ in range(df_.shape[0])]
            df_.reset_index(inplace=True)
            df = pd.concat([df, df_], ignore_index=True, axis=0)

        self.df = df

    def static_data(self, result_types: list[str] = ()) -> pd.DataFrame:
        if self.df.empty:
            raise ValueError('Connectivity must be calculated before static data, or connection between ids not found')

        if not self.df_static.empty and result_types == self._static_types:
            return self.df_static

        # offsets - always required
        if self.df_static.empty:
            offset = 0.
            offsets = []
            for i, length in enumerate(self.df['Length']):
                offsets.append(offset)
                offset += length
                offsets.append(offset)
            df = pd.DataFrame(offsets, columns=['Offset'])
        else:
            df = self.df_static[['Offset']]

        # other static result types
        for result_type in result_types:
            if result_type.lower() in [x.lower() for x in self.df_static.columns]:
                i = [x.lower() for x in self.df_static.columns].index(result_type.lower())
                df[result_type] = self.df_static.iloc[:,i]
            elif result_type.lower() == 'bed elevation':
                y = []
                for row in self.df.iterrows():
                    y.append(row[1]['US Invert'])
                    y.append(row[1]['DS Invert'])
                df['Bed Elevation'] = y
            elif 'pit' in result_type.lower():
                y = []
                for row in self.df.iterrows():
                    if row[1]['US Channel'] == '------' and row[1]['DS Channel'] == '------':
                        y.append(row[1]['US Invert'])
                    else:
                        y.append(np.nan)
                    y.append(np.nan)
                df['Pit'] = y
            elif 'culvert' in result_type.lower() or 'pipe' in result_type.lower():
                y = []
                for row in self.df.iterrows():
                    us_inv = row[1]['US Invert']
                    ds_inv = row[1]['DS Invert']
                    us_obv = row[1]['LBUS Obvert']
                    ds_obv = row[1]['LBDS Obvert']
                    if row[1]['Flags'] in ['R', 'C'] and not np.isclose(us_inv, ds_inv):
                        y.append(us_obv)
                        y.append(ds_obv)
                    else:
                        y.append(np.nan)
                        y.append(np.nan)
                df['Pipe Obvert'] = y

        self.df_static = df
        return self.df_static

    def temporal_data(self, result_types: list[str], timestep_index: int) -> pd.DataFrame:
        pass

class Connectivity:

    def __init__(self, channels: 'Channels', id1: str, id2: Union[str, None]) -> None:
        self.channels = channels
        self.id1 = id1
        self.id2 = id2
        self.branches = []
        self.connected = False
        self.connect()

    def connect(self):
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
        finished = False
        if id1 not in branch:
            branch.append(id1)
        one_connection = False
        for id_ in self.channels.downstream_channels(id1):
            one_connection = True
            if id_ not in branch:
                branch.append(id_)
            finished = id_ in branch[:-1] or id_ == id2
            if finished:
                self.branches.append(branch)
            if not finished:
                finished = self._connect(id_, id2, branch.copy())
            if finished:
                return finished

        if not one_connection and id2 is None:
            finished = True

        if finished:
            self.branches.append(branch)

        return finished
