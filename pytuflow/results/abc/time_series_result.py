import re
from datetime import datetime
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from ..lp_1d import LP_1D
from ..time_util import closest_time_index
from pytuflow.results.iterator_util import Iterator


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

    def ids(self, result_type: str = '', domain: str = '') -> list[str]:
        iter = Iterator(self.channels, self.nodes, self.po, self.rl)
        ids = []
        for item in iter.ids_result_types_domain([], result_type, domain, 'temporal'):
            for id_ in item.ids:
                if id_ not in ids:
                    ids.append(id_)
        return ids

    def channel_ids(self, result_type: str = '') -> list[str]:
        if self.channels:
            return self.ids(result_type, '1d channel')
        return []

    def node_ids(self, result_type: str = '') -> list[str]:
        if self.nodes:
            return self.ids(result_type, '1d node')
        return []

    def po_ids(self, result_type: str = '') -> list[str]:
        if self.po:
            return self.ids(result_type, '2d')
        return []

    def rl_ids(self, result_type: str = '') -> list[str]:
        if self.rl:
            return self.ids(result_type, '0d')
        return []

    def result_types(self, id: Union[str, list[str]] = '') -> list[str]:
        iter = Iterator(self.channels, self.nodes, self.po, self.rl)
        result_types = []
        for item in iter.ids_result_types_domain(id, [], None, 'temporal'):
            for rt in item.result_types:
                if rt not in result_types:
                    result_types.append(rt)
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
        """Extract time series data for the given id(s) and result type(s)."""
        df = pd.DataFrame()
        x = []
        dropped_index = False
        iter = Iterator(self.channels, self.nodes, self.po, self.rl)
        for item in iter.ids_result_types_domain(id, result_type, domain, 'temporal'):
            df_ = item.result_item.get_time_series(item.ids, item.result_types)
            df_.rename(columns={x: f'{item.result_item_name}::{x}' for x in df_.columns}, inplace=True)
            if x and not np.isclose(x, df_.index.tolist(), atol=0.001).all():
                x = df_.index.tolist()
                if not dropped_index:
                    df = df.reset_index().rename()
                    dropped_index = True
                df[f'{item.result_item_name}::Time (h)'] = x
            if df.empty:
                df = df_
                x = df_.index.tolist()
            else:
                if dropped_index:
                    df = pd.concat([df, df_.reset_index(drop=True)], axis=1)
                else:
                    # join on integer index as when time column is read from different CSV files, time index maybe don't match exactly
                    index_name = df.index.name
                    df = pd.concat([df.reset_index(), df_.reset_index(drop=True)], axis=1)
                    df.set_index(index_name, inplace=True)
        return df

    def maximum(self,
            id: Union[str, list[str]],
            result_type: Union[str, list[str]],
            domain: str = None
    ) -> pd.DataFrame:
        """Extract maximum data for the given id(s) and result type(s)."""
        df = pd.DataFrame()
        iter = Iterator(self.channels, self.nodes, self.po, self.rl)
        for item in iter.ids_result_types_domain(id, result_type, domain, 'max'):
            df_ = item.result_item.get_maximum(item.ids, item.result_types)
            df_.rename(columns={x: f'{item.result_item_name}::{x}' for x in df_.columns}, inplace=True)
            if df.empty:
                df = df_
            else:
                df = pd.concat([df, df_], axis=1)
        return df

    def long_plot(self, ids: Union[str, list[str]], result_type: Union[str, list[str]], time: float) -> pd.DataFrame:
        if not ids:
            raise ValueError('No ids provided')

        iter = Iterator(self.channels, self.nodes, self.po, self.rl)
        for item in iter.ids_result_types_lp(ids, result_type):
            df = self.connectivity(item.ids)
            if df.empty:
                return pd.DataFrame([], columns=['Offset'] + result_type)

            timestep_index = closest_time_index(self.timesteps(domain='1d'), time)

            return self.lp_1d.long_plot(item.result_types, timestep_index)

    def connectivity(self, ids: Union[str, list[str]]) -> pd.DataFrame:
        if not isinstance(ids, list):
            ids = [ids] if ids is not None else []

        ids_lower = [x.lower() for x in self.channel_ids()]
        ids_ = []
        for id_ in ids:
            if id_.lower() not in ids_lower:
                raise ValueError(f'Invalid channel id: {id_}')
            else:
                i = ids_lower.index(id_.lower())
                ids_.append(self.channel_ids()[i])
        ids = ids_

        lp = LP_1D(self.channels, self.nodes, ids)
        if self.lp_1d is not None and lp == self.lp_1d:
            return self.lp_1d.df

        lp.connectivity()
        self.lp_1d = lp
        return lp.df

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

