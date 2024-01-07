from typing import TYPE_CHECKING, Union, Generator

import pandas as pd

if TYPE_CHECKING:
    from .abc.channels import Channels

class LP_1D:

    def __init__(self, channels: 'Channels', ids: list[str] = ()) -> None:
        self.channels = channels
        self.ids = ids
        self.columns = ['US Node', 'DS Node', 'Length', 'US Invert', 'DS Invert']
        self.df = pd.DataFrame([], columns=['Channel'] + self.columns + ['Branch ID'])

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
