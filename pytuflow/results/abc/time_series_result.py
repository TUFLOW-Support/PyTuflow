from pathlib import Path
from typing import Union


class TimeSeriesResult:

    def __init__(self, fpath: Union[str, Path]) -> None:
        self.fpath = Path(fpath)
        self.units = ''
        self.sim_id = ''
        self.channels = None
        self.nodes = None
        self.po = None
        self.rl = None
        self.load()

    def load(self) -> None:
        raise NotImplementedError

    def channel_count(self) -> int:
        if self.channels:
            return self.channels.count()
        return 0

    def node_count(self) -> int:
        if self.nodes:
            return self.nodes.count()
        return 0

    def po_count(self) -> int:
        if self.po:
            return self.po.count()
        return 0

    def rl_count(self) -> int:
        if self.rl:
            return self.rl.count()
        return 0

    def ids(self, result_type: str = '') -> list[str]:
        ids = self.channel_ids(result_type)
        for id in self.node_ids(result_type):
            if id not in ids:
                ids.append(id)
        for id in self.po_ids(result_type):
            if id not in ids:
                ids.append(id)
        for id in self.rl_ids(result_type):
            if id not in ids:
                ids.append(id)
        return ids

    def channel_ids(self, result_type: str = '') -> list[str]:
        if self.channels:
            return self.channels.ids(result_type)
        return []

    def node_ids(self, result_type: str = '') -> list[str]:
        if self.nodes:
            return self.nodes.ids(result_type)
        return []

    def po_ids(self, result_type: str = '') -> list[str]:
        if self.po:
            return self.po.ids(result_type)
        return []

    def rl_ids(self, result_type: str = '') -> list[str]:
        if self.rl:
            return self.rl.ids(result_type)
        return []

    def result_types(self, id: str = '') -> list[str]:
        result_types = self.channel_result_types(id)
        for result_type in self.node_result_types(id):
            if result_type not in result_types:
                result_types.append(result_type)
        for result_type in self.po_result_types(id):
            if result_type not in result_types:
                result_types.append(result_type)
        for result_type in self.rl_result_types(id):
            if result_type not in result_types:
                result_types.append(result_type)
        return result_types

    def channel_result_types(self, id: str = '') -> list[str]:
        if self.channels:
            return self.channels.result_types(id)
        return []

    def node_result_types(self, id: str = '') -> list[str]:
        if self.nodes:
            return self.nodes.result_types(id)
        return []

    def po_result_types(self, id: str = '') -> list[str]:
        if self.po:
            return self.po.result_types(id)
        return []

    def rl_result_types(self, id: str = '') -> list[str]:
        if self.rl:
            return self.rl.result_types(id)
        return []
