from typing import Generator, Union

import pandas as pd

from .lp_1d import LP1D, Connectivity


class LP1DFM(LP1D):
    """Override :class:`LP_1D<pytuflow.outputs.helpers.lp_1d.LP_1D>` for Flood Modeller
    long profiles because the start and end locations will be nodes and not channels.
    """

    def connectivity(self) -> None:
        # docstring inherited
        branches = []
        if len(self.ids) == 1:
            conn = ConnectivityFM(self.chan_info, self.node_info, self.ids[0], None)
            branches.extend(conn.branches)
        else:
            # more than 1 id - find a connection
            ds_id = None
            for id1 in self.ids:
                for id2 in self.ids:
                    if id1 == id2:
                        continue
                    conn = ConnectivityFM(self.chan_info, self.node_info, id1, id2)
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
                conn = ConnectivityFM(self.chan_info, self.node_info, id_, ds_id)
                if conn.connected:
                    branches.extend(conn.branches)

        # merge branches
        self.df = self._merge_branches(branches)

    def _init_ids(self, ids: list[str], chan_info: pd.DataFrame, node_info: pd.DataFrame) -> list[str]:
        ids1 = []
        for id_ in ids:
            try:
                id1 = node_info.index[node_info.index.str.lower() == id_.lower()].values[0]
                ids1.append(id1)
            except IndexError:
                raise ValueError(f'Could not find ID: {id_}')
        return ids


class ConnectivityFM(Connectivity):
    """Override :class:`LP_1D<pytuflow.outputs.helpers.lp_1d.Connectivity>` for Flood Modeller
    connectivity because the start and end locations will be nodes and not channels.
    """

    def _connect(self, id1: str, id2: Union[str, None], branch: list[str], chanid: str = '') -> bool:
        # docstring inherited
        finished = False
        if chanid and chanid not in branch:
            branch.append(chanid)
        one_connection = False
        for nd, id_ in self._downstream_channels(id1): # nd = channel downstream node
            one_connection = True
            finished = id_ in branch[:-1] or nd == id2
            if finished:
                if id_ not in branch:
                    branch.append(id_)
                self.branches.append(branch)
            if not finished:
                finished = self._connect(nd, id2, branch.copy(), id_)

        if not one_connection and id2 is None:
            finished = True
            self.branches.append(branch)

        return finished

    def _downstream_channels(self, id_: str) -> Generator[tuple[str, str], None, None]:
        """Yield downstream channels given a channel ID."""
        for chan in self.node_info.loc[id_].channels:
            if chan not in self.chan_info.index:
                continue
            us_node = self.chan_info.loc[chan, 'us_node']
            if us_node == id_:
                nd = self.chan_info.loc[chan, 'ds_node']
                yield nd, chan
