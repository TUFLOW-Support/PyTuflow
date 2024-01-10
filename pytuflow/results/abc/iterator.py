from typing import Generator, Union
from dataclasses import dataclass, field

import pandas as pd

from .channels import Channels
from .nodes import Nodes
from .time_series_result_item import TimeSeriesResultItem


@dataclass
class Corrected:
    id_orig: str
    result_type_orig: str
    result_item: TimeSeriesResultItem
    id: str
    result_type: str

    @property
    def valid(self) -> bool:
        return self.id is not None and self.result_type is not None


@dataclass
class IDResultTypeItem:
    result_item_name: str
    correct: list[Corrected]
    ids: list[str] = field(init=False)
    result_types: list[str] = field(init=False)
    result_item: TimeSeriesResultItem = field(init=False)

    def __post_init__(self):
        self.ids = []
        for item in self.correct:
            if item.id not in self.ids:
                self.ids.append(item.id)
        self.result_types = []
        for item in self.correct:
            if item.result_type not in self.result_types:
                self.result_types.append(item.result_type)
        if self.correct:
            self.result_item = self.correct[0].result_item

    @property
    def valid(self) -> bool:
        return bool(self.correct)


class Iterator:

    def __new__(cls, channels: Channels, nodes: Nodes, po: TimeSeriesResultItem, rl: TimeSeriesResultItem):
        from ..tpc.tpc_channels import TPCChannels
        from ..gpkg_ts.gpkg_channels import GPKGChannels
        if isinstance(channels, TPCChannels):
            from ..tpc.tpc_iterator import TPCIterator
            cls = TPCIterator
        elif isinstance(channels, GPKGChannels):
            from ..gpkg_ts.gpkg_iterator import GPKGIterator
            cls = GPKGIterator
        return super().__new__(cls)

    def __init__(self, channels: Channels, nodes: Nodes, po: TimeSeriesResultItem, rl: TimeSeriesResultItem):
        self.channels = channels
        self.nodes = nodes
        self.po = po
        self.rl = rl

    def ids_result_types_domain(self,
            ids: Union[str, list[str]],
            result_types: Union[str, list[str]],
            domain: str,
            type_: str,
    ) -> Generator[Loc, None, None]:
        if not isinstance(ids, list):
            ids = [ids] if ids is not None else []
        if not isinstance(result_types, list):
            result_types = [result_types] if result_types is not None else []

        if domain is None or domain.lower() == '1d':
            item = self.get_nodes(ids, result_types, type_)
            if item.valid:
                yield item
            item = self.get_channels(ids, result_types, type_)
            if item.valid:
                yield item
        if domain is None or domain.lower() == '2d':
            item = self.get_po(ids, result_types, type_)
            if item.valid:
                yield item
        if domain is None or domain.lower() == '0d':
            item = self.get_rl(ids, result_types, type_)
            if item.valid:
                yield item

    def correct_id(self, ids: list[str], df: pd.DataFrame) -> list[str]:
        ids_ = []
        for id_ in ids:
            if id_.lower() in [x.lower() for x in df.index]:
                ids_.append(df.index[[x.lower() for x in df.index].index(id_.lower())])
            else:
                ids_.append(None)
        return ids_

    def correct_result_type(self, result_types, domain_2: str, type_: str) -> list[str]:
        a = []
        if type_.lower() == 'temporal':
            if domain_2.lower() == 'node':
                if self.nodes:
                    result_types = [self.nodes.conv_result_type_name(x) for x in result_types]
                    a = self.nodes.result_types(None)
            elif domain_2.lower() == 'channel':
                if self.channels:
                    result_types = [self.channels.conv_result_type_name(x) for x in result_types]
                    a = self.channels.result_types(None)
            elif domain_2.lower() == 'po':
                if self.po:
                    result_types = [self.po.conv_result_type_name(x) for x in result_types]
                    a = self.po.result_types(None)
            elif domain_2.lower() == 'rl':
                if self.rl:
                    result_types = [self.rl.conv_result_type_name(x) for x in result_types]
                    a = self.rl.result_types(None)
        elif type_.lower() == 'max':
            if domain_2.lower() == 'node':
                if self.nodes:
                    result_types = [self.nodes.conv_result_type_name(x) for x in result_types]
                    result_types = [self.nodes.result_type_to_max(x) for x in result_types]
                    a = self.nodes.maximums.df.columns
            elif domain_2.lower() == 'channel':
                if self.channels:
                    result_types = [self.channels.conv_result_type_name(x) for x in result_types]
                    result_types = [self.channels.result_type_to_max(x) for x in result_types]
                    a = self.channels.maximums.df.columns
            elif domain_2.lower() == 'po':
                if self.po:
                    result_types = [self.po.conv_result_type_name(x) for x in result_types]
                    result_types = [self.po.result_type_to_max(x) for x in result_types]
                    a = self.po.maximums.df.columns
            elif domain_2.lower() == 'rl':
                if self.rl:
                    result_types = [self.rl.conv_result_type_name(x) for x in result_types]
                    result_types = [self.rl.result_type_to_max(x) for x in result_types]
                    a = self.rl.maximums.df.columns
        result_types_ = []
        for rt in result_types:
            if rt.lower() in [x.lower() for x in a]:
                result_types_.append(a[[x.lower() for x in a].index(rt.lower())])
            else:
                result_types_.append(None)
        return result_types_

    def get_nodes(self, ids: list[str], result_types: list[str], type_: str) -> IDResultTypeItem:
        return self._get_base(ids, result_types, '1d', 'Node', type_, self.nodes)

    def get_channels(self, ids: list[str], result_types: list[str], type_: str) -> IDResultTypeItem:
        return self._get_base(ids, result_types, '1d', 'Channel', type_, self.channels)

    def get_po(self, ids: list[str], result_types: list[str], type_: str) -> IDResultTypeItem:
        return self._get_base(ids, result_types, '2d', 'PO', type_, self.po)

    def get_rl(self, ids: list[str], result_types: list[str], type_: str) -> IDResultTypeItem:
        return self._get_base(ids, result_types, '0d', 'RL', type_, self.rl)

    def _get_base(
            self,
            ids: list[str],
            result_types: list[str],
            domain: str,
            domain_2: str,
            type_: str,
            cls: TimeSeriesResultItem
    ) -> IDResultTypeItem:
        ids_, result_types_ = [], []
        if ids and cls is not None:
            ids_ = self.correct_id(ids, cls.df)
        if result_types and cls is not None:
            result_types_ = self.correct_result_type(result_types, domain_2, type_)
        if not ids and cls is not None:
            ids_ = cls.ids(result_types_)
            ids = ids_
        if not result_types and cls is not None:
            result_types_ = cls.result_types(ids_)
            result_types = result_types_
        if cls is None:
            if ids:
                ids_ = [None for _ in ids]
            if result_types:
                result_types_ = [None for _ in result_types]
        corrected = []
        for id1, id2 in zip(ids, ids_):
            for rt1, rt2 in zip(result_types, result_types_):
                corr = Corrected(id1, rt1, cls, id2, rt2)
                if corr.valid:
                    corrected.append(corr)
        return IDResultTypeItem(domain_2, corrected)
