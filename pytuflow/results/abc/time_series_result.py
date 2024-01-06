from collections import OrderedDict
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd


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

    def time_series(self,
            id: Union[str, list[str]],
            result_type: Union[str, list[str]],
            domain: str = None
    ) -> pd.DataFrame:
        if not isinstance(id, list):
            id = [id]
        if not isinstance(result_type, list):
            result_type = [result_type]
        id, result_type = self._req_id_and_result_type(id, result_type, domain)
        x, data = [], OrderedDict({})
        order = ['channel', 'node', 'po', 'rl']
        for rt in result_type:
            for id_ in id:
                df1, df2, df3, df4 = None, None, None, None
                if domain is None or domain.lower() == '1d':
                    if id_ in self.channel_ids(rt):
                        df1 = self.channels.get_time_series(id_, rt)
                    if id_ in self.node_ids(rt):
                        df2 = self.nodes.get_time_series(id_, rt)
                elif domain is None or domain.lower() == '2d':
                    if id_ in self.po_ids(rt):
                        df3 = self.po.get_time_series(id_, rt)
                elif domain is None or domain.lower() == 'rl':
                    if id_ in self.rl_ids(rt):
                        df4 = self.rl.get_time_series(id_, rt)

                c = [0 if x is None or x.empty else 1 for x in [df1, df2, df3, df4]].count(1)
                for i, df in enumerate([df1, df2, df3, df4]):
                    if df is None or df.empty:
                        continue
                    if c == 1:
                        h = f'{rt}::{id_}'
                    else:
                        h = f'{order[i]}::{rt}::{id_}'
                    if not x or not np.isclose(x, df.index.tolist(), atol=0.001).all():
                        x = df.index.tolist()
                        t = 'Time (h)'
                        n = 1
                        if t in data:
                            t = f'Time (h)_{n}'
                            while t in data:
                                n += 1
                        data[t] = x
                    n = 1
                    if h in data:
                        h_ = f'{h}_{n}'
                        while h_ in data:
                            n += 1
                        h = h_
                    data[h] = df.iloc[:,0].tolist()

        return pd.DataFrame(data)

    def _req_id_and_result_type(self,
            id: list[str],
            result_type: list[str],
            domain: Union[str, None]
    ) -> tuple[list[str], list[str]]:
        if not id:
            ids = self._req_id(result_type, domain)
        else:
            ids = id
        if not result_type:
            result_types = self._req_result_type(ids, domain)
        else:
            result_types = result_type
        return ids, result_types

    def _req_id(self, result_type: list[str], domain: Union[str, None]) -> list[str]:
        if domain is None and not result_type:
            return self.ids()
        elif domain is None:
            ids = []
            for rt in result_type:
                for id_ in self.ids(rt):
                    if id_ not in ids:
                        ids.append(id_)
            return ids
        elif domain.lower() == '1d' and not result_type:
            return self.channel_ids() + self.node_ids()
        elif domain.lower() == '1d':
            ids = []
            for rt in result_type:
                ids.extend(self.channel_ids(rt))
            for rt in result_type:
                ids.extend(self.node_ids(rt))
            return ids
        elif domain.lower() == '2d' and not result_type:
            return self.po_ids()
        elif domain.lower() == '2d':
            ids = []
            for rt in result_type:
                for id_ in self.po_ids(rt):
                    if id_ not in ids:
                        ids.append(id_)
            return ids
        elif domain.lower() == '0d' and not result_type:
            return self.rl_ids()
        elif domain.lower() == '0d':
            ids = []
            for rt in result_type:
                for id_ in self.rl_ids(rt):
                    if id_ not in ids:
                        ids.append(id_)
            return ids
        else:
            raise ValueError(f'Invalid domain: {domain}')

    def _req_result_type(self, id: list[str], domain: Union[str, None]) -> list[str]:
        if domain is None and not id:
            return self.result_types()
        elif domain is None:
            result_types = []
            for id_ in id:
                for rt in self.result_types(id_):
                    if rt not in result_types:
                        result_types.append(rt)
            return result_types
        elif domain.lower() == '1d' and not id:
            return self.channel_result_types() + self.node_result_types()
        elif domain.lower() == '1d':
            result_types = []
            for id_ in id:
                for rt in self.channel_result_types(id_):
                    if rt not in result_types:
                        result_types.append(rt)
            for id_ in id:
                for rt in self.node_result_types(id_):
                    if rt not in result_types:
                        result_types.append(rt)
            return result_types
        elif domain.lower() == '2d' and not id:
            return self.po_result_types()
        elif domain.lower() == '2d':
            result_types = []
            for id_ in id:
                for rt in self.po_result_types(id_):
                    if rt not in result_types:
                        result_types.append(rt)
            return result_types
        elif domain.lower() == '0d' and not id:
            return self.rl_result_types()
        elif domain.lower() == '0d':
            result_types = []
            for id_ in id:
                for rt in self.rl_result_types(id_):
                    if rt not in result_types:
                        result_types.append(rt)
            return result_types
        else:
            raise ValueError(f'Invalid domain: {domain}')
