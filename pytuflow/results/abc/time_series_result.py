import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from ..lp_1d import LP_1D
from ..time_util import closest_time_index


class TimeSeriesResult:

    def __init__(self, fpath: Union[str, Path]) -> None:
        self.fpath = Path(fpath)
        self.units = ''
        self.sim_id = ''
        self.channels = None
        self.nodes = None
        self.po = None
        self.rl = None
        self.lp_1d = None
        self.reference_time = datetime(1990, 1, 1)
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

    def long_plot_result_types(self) -> list[str]:
        if self.nodes:
            return self.nodes.long_plot_result_types()
        return []

    def timesteps(self, domain: str = '', dtype: str = 'relative') -> list[Union[float, datetime]]:
        if domain:
            return self._timesteps(domain, dtype)
        timesteps = []
        for domain in ['1d', '2d', '0d']:
            for timestep in self._timesteps(domain, dtype):
                if timestep not in timesteps:
                    timesteps.append(timestep)
        return sorted(timesteps)

    def time_series(self,
            id: Union[str, list[str]],
            result_type: Union[str, list[str]],
            domain: str = None
    ) -> pd.DataFrame:
        if not isinstance(id, list):
            id = [id] if id is not None else []

        if not isinstance(result_type, list):
            result_type = [result_type] if result_type is not None else []

        id, result_type = self._req_id_and_result_type(id, result_type, domain)

        order = ['channel', 'node', 'po', 'rl']  # order of the returned dataframes below
        x, data = [], OrderedDict({})
        for rt in result_type:
            for id_ in id:
                df1, df2, df3, df4 = None, None, None, None
                if domain is None or domain.lower() == '1d':
                    if id_ in self.channel_ids(rt):
                        df1 = self.channels.get_time_series(id_, rt)
                    if id_ in self.node_ids(rt):
                        df2 = self.nodes.get_time_series(id_, rt)
                if domain is None or domain.lower() == '2d':
                    if id_ in self.po_ids(rt):
                        df3 = self.po.get_time_series(id_, rt)
                if domain is None or domain.lower() == 'rl':
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

    def long_plot(self, ids: Union[str, list[str]], result_type: Union[str, list[str]], time: float) -> pd.DataFrame:
        if not isinstance(ids, list):
            ids = [ids] if ids is not None else []

        if not isinstance(result_type, list):
            result_type = [result_type] if result_type is not None else []

        if not ids:
            raise ValueError('No ids provided')

        ids, result_type = self._req_id_and_result_type(ids, result_type, '1d nodes')

        df = self.connectivity(ids)
        if df.empty:
            return pd.DataFrame([], columns=['Offset'] + result_type)

        timestep_index = closest_time_index(self.timesteps(domain='1d'), time)

        return self.lp_1d.long_plot(result_type, timestep_index)

    def connectivity(self, ids: Union[str, list[str]]) -> pd.DataFrame:
        if not isinstance(ids, list):
            ids = [ids] if ids is not None else []

        for id_ in ids:
            if id_ not in self.channel_ids():
                raise ValueError(f'Invalid channel id: {id_}')

        lp = LP_1D(self.channels, self.nodes, ids)
        if self.lp_1d is not None and lp == self.lp_1d:
            return self.lp_1d.df

        lp.connectivity()
        self.lp_1d = lp
        return lp.df

    def conv_result_type_name(self, result_type: str) -> str:
        raise NotImplementedError

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
            result_types = []
            flag = re.sub(r'\dd', '', domain, flags=re.IGNORECASE).lower().strip()
            if 'channel' in flag or not flag:
                result_types.extend(self.channel_result_types())
            if 'node' in flag or not flag:
                result_types.extend(self.node_result_types())
            return self.channel_result_types() + self.node_result_types()
        elif domain.lower() == '1d':
            result_types = []
            flag = re.sub(r'\dd', '', domain, flags=re.IGNORECASE).lower().strip()
            if 'channel' in flag or not flag:
                for id_ in id:
                    for rt in self.channel_result_types(id_):
                        if rt not in result_types:
                            result_types.append(rt)
            if 'node' in flag or not flag:
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

    def _timesteps(self, domain: str, dtype: str) -> list[Union[float, datetime]]:
        if domain.lower() == '1d':
            if self.channels:
                return self.channels.timesteps(dtype)
            elif self.nodes:
                return self.nodes.timesteps(dtype)
            else:
                return []
        elif domain.lower() == '2d':
            if self.po is not None:
                return self.po.timesteps(dtype)
            return []
        elif domain.lower() == '0d':
            if self.rl is not None:
                return self.rl.timesteps(dtype)
            return []
        else:
            raise ValueError(f'Invalid domain: {domain}')

