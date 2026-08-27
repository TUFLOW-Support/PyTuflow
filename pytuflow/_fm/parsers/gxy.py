import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from ..fm_to_estry_types import PathLike
from ..helpers.prog_bar import ProgBar

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd


@dataclass
class _Node:
    uid: str
    type: str = field(default='', init=False)
    id: str = field(default='', init=False)

    def __post_init__(self):
        self.type = '_'.join(self.uid.split('_', 2)[:2]).strip('_')
        self.id = self.uid.split('_', 2)[2]


class GXY:
    """Class to handle Flood Modeller GXY files."""

    def __init__(self, fpath: PathLike, callback: typing.Callable = None, unit_count: int = -1) -> None:
        """
        Parameters
        ----------
        fpath : PathLike
            Path to the GXY file.
        callback : typing.Callable, optional
            Callback function to report progress, by default None
        unit_count : int, optional
            Number of units to process, by default -1. Only used if using the callback function.
        """
        #: Path: Path to the GXY file.
        self.fpath = Path(fpath)
        #: int: Number of units to process.
        self.UNIT_COUNT = unit_count
        #: pd.DataFrame: DataFrame containing node data.
        self.node_df = None
        #: pd.DataFrame: DataFrame containing link data.
        self.link_df = None
        #: int: Number of connections.
        self.connection_count = 0
        self._callback = callback
        self._prog_bar = ProgBar(self._callback)
        self._nodes_finished = False
        self._links_finished = False
        self.nodes = []
        self._size = 0
        self._cur_prog = 0
        if self._callback and self.UNIT_COUNT > 0:
            self._size = self.UNIT_COUNT * 2 - 1
        self._load()

    @property
    def callback(self) -> typing.Callable:
        #: typing.Callable: Callback function to report progress.
        return self._callback

    @callback.setter
    def callback(self, callback: typing.Callable) -> None:
        self._callback = callback
        self._prog_bar.callback = callback

    def _load(self) -> None:
        self._prog_bar.reset()
        if self._size:
            self.callback(0)
        with self.fpath.open() as f:
            self._nodes_finished, self._links_finished = False, False
            while not self._nodes_finished:
                self._load_node(f)
                if self._size:
                    self._cur_prog += 1
                    self._prog_bar.progress_callback(self._cur_prog, self._size)
            while not self._links_finished:
                self._load_link(f)
                if self._size:
                    self._cur_prog += 1
                    self._prog_bar.progress_callback(self._cur_prog, self._size)

    def _load_node(self, fo: TextIO) -> None:
        for line in fo:
            if '[Connections]' in line:
                self._nodes_finished = True
                break
            if line.startswith('['):
                id_ = line.strip('[]\n')
                id_ = id_.replace('\\', '').replace('/', '')
                self.nodes.append(_Node(id_))
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
            ups = ups.replace('\\', '').replace('/', '')
            dns = dns.replace('\\', '').replace('/', '')
            df = pd.DataFrame({'ups_node': ups, 'dns_node': dns}, index=[id_])
            if self.link_df is None:
                self.link_df = df
            else:
                self.link_df = pd.concat([self.link_df, df], axis=0)
            break
