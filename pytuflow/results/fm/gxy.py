from dataclasses import dataclass, field
from pathlib import Path
from typing import Union, TextIO

import pandas as pd


@dataclass
class _Node:
    uid: str
    type: str = field(default='', init=False)
    id: str = field(default='', init=False)

    def __post_init__(self):
        self.type = '_'.join(self.uid.split('_', 2)[:2])
        self.id = self.uid.split('_', 2)[2]


class GXY:

    def __init__(self, fpath: Union[str, Path]) -> None:
        self.fpath = Path(fpath)
        self.node_df = None
        self.link_df = None
        self.connection_count = 0
        self._nodes_finished = False
        self._links_finished = False
        self._nodes = []
        self._load()

    def gxy_id(self, id_: str, types: list[str]) -> str:
        for node in self._nodes:
            if node.id == id_ and node.type in types:
                return node.uid
        return ''


    def _load(self) -> None:
        with self.fpath.open() as f:
            self._nodes_finished, self._links_finished = False, False
            while not self._nodes_finished:
                self._load_node(f)
            while not self._links_finished:
                self._load_link(f)

    def _load_node(self, fo: TextIO) -> None:
        for line in fo:
            if '[Connections]' in line:
                self._nodes_finished = True
                break
            if line.startswith('['):
                id_ = line.strip('[]\n')
                self._nodes.append(_Node(id_))
                try:
                    x = float(fo.readline().replace('X=', '').strip())
                except ValueError:
                    x = -1
                try:
                    y = float(fo.readline().replace('Y=', '').strip())
                except ValueError:
                    y = -1
                df = pd.DataFrame({'x': x, 'y': y}, index=[id_])
                if self.node_df is None:
                    self.node_df = df
                else:
                    self.node_df = pd.concat([self.node_df, df], axis=0)
                break

    def _load_link(self, fo: TextIO) -> None:
        for line in fo:
            if line.startswith('[') or not line.strip():
                self._links_finished = True
                break
            id_, conn = line.strip().split('=')
            if id_ == 'ConnectionCount':
                self.connection_count = int(conn)
                continue
            try:
                id_ = int(id_)
            except ValueError:
                self._links_finished = True
                break
            ups, dns = conn.split(',')
            df = pd.DataFrame({'ups_node': ups, 'dns_node': dns}, index=[id_])
            if self.link_df is None:
                self.link_df = df
            else:
                self.link_df = pd.concat([self.link_df, df], axis=0)
            break
