import re
from typing import Generator, Union
from dataclasses import dataclass, field

import pandas as pd

from .abc.channels import Channels
from .abc.nodes import Nodes
from .abc.time_series_result_item import TimeSeriesResultItem


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
    remove_invalid: bool
    ids: list[str] = field(init=False)
    result_types: list[str] = field(init=False)
    result_item: TimeSeriesResultItem = field(init=False)

    def __post_init__(self) -> None:
        if self.remove_invalid:
            self._remove_invalid()
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

    def _remove_invalid(self) -> None:
        for item in self.correct.copy():
            if not item.valid:
                self.correct.remove(item)

    @property
    def valid(self) -> bool:
        return bool(self.correct)


class Iterator:

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
    ) -> Generator[IDResultTypeItem, None, None]:
        """
        Given an ID or list of IDs and result types, as well as an optional domain argument - routine will yield
        an IDResultTypeItem for each result item type within the given domain
        (e.g. node, channel, po, rl) that contains valid
        ID and result type combinations with corrected IDs and result type
        (i.e. correct case, result type short name converted to full name etc.)
        """
        if not isinstance(ids, list):
            ids = [ids] if ids is not None else []
        if not isinstance(result_types, list):
            result_types = [result_types] if result_types is not None else []

        domain_2 = None
        if domain is not None:
            a = domain.split(' ', 1)
            if len(a) == 2:
                domain, domain_2 = a

        if domain is None or domain.lower() == '1d':
            if domain_2 is None or domain_2.lower() == 'node':
                corr_items = self.get_nodes(ids, result_types, type_)
                item = IDResultTypeItem('Node', corr_items, True)
                if item.valid:
                    yield item
            if domain_2 is None or domain_2.lower() == 'channel':
                corr_items = self.get_channels(ids, result_types, type_)
                item = IDResultTypeItem('Channel', corr_items, True)
                if item.valid:
                    yield item
        if domain is None or domain.lower() == '2d':
            corr_items = self.get_po(ids, result_types, type_)
            item = IDResultTypeItem('PO', corr_items, True)
            if item.valid:
                yield item
        if domain is None or domain.lower() == '0d':
            corr_items = self.get_rl(ids, result_types, type_)
            item = IDResultTypeItem('RL', corr_items, True)
            if item.valid:
                yield item

    def ids_result_types_lp(
            self,
            ids: Union[str, list[str]],
            result_types: Union[str, list[str]]
    ) -> Generator[IDResultTypeItem, None, None]:
        from .lp_1d import LP_1D

        if not isinstance(ids, list):
            ids = [ids] if ids is not None else []
        if not isinstance(result_types, list):
            result_types = [result_types] if result_types is not None else []

        # get corrected ids (from channels)
        ids_ = []
        for corr_item in self.get_channels(ids, [], 'temporal'):
            if corr_item.id is not None and corr_item.id_orig in ids and corr_item.id not in ids_:
                ids_.append(corr_item.id)

        # get corrected result types (from nodes)
        # separate static result types (not inc. max)
        static_result_types, static_result_types_corr_names = LP_1D.extract_static_results(result_types)
        static_result_types = {x: y for x, y in zip(static_result_types, static_result_types_corr_names)}
        result_types_ = []
        for corr_item in self.get_nodes([], result_types, 'temporal'):
            if corr_item.result_type_orig in static_result_types and static_result_types[corr_item.result_type_orig] not in result_types_:
                result_types_.append(static_result_types[corr_item.result_type_orig])
            elif corr_item.result_type is not None and corr_item.result_type not in result_types_:
                result_types_.append(corr_item.result_type)
        # deal with max
        max_result_types = [re.sub(r'max(imum)?', '', x, flags=re.IGNORECASE).strip() for x in result_types if 'max' in x.lower()]
        if max_result_types or not result_types:
            for corr_item in self.get_nodes([], max_result_types, 'max'):
                if corr_item.result_type is not None and corr_item.result_type not in result_types_:
                    result_types_.append(corr_item.result_type)

        corrected = []
        for id1, id2 in zip(ids_, ids_):
            for rt1, rt2 in zip(result_types_, result_types_):
                corr = Corrected(id1, rt1, self.nodes, id2, rt2)
                corrected.append(corr)
        yield IDResultTypeItem('Node', corrected, False)

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
                    result_types = sum([[self.nodes.result_type_to_max(x), self.nodes.result_type_to_tmax(x)] for x in result_types], [])
                    a = self.nodes.maximums.df.columns
            elif domain_2.lower() == 'channel':
                if self.channels:
                    result_types = [self.channels.conv_result_type_name(x) for x in result_types]
                    result_types = sum([[self.channels.result_type_to_max(x), self.channels.result_type_to_tmax(x)] for x in result_types], [])
                    a = self.channels.maximums.df.columns
            elif domain_2.lower() == 'po':
                if self.po:
                    result_types = [self.po.conv_result_type_name(x) for x in result_types]
                    result_types = sum([[self.po.result_type_to_max(x), self.po.result_type_to_tmax(x)] for x in result_types], [])
                    a = self.po.maximums.df.columns
            elif domain_2.lower() == 'rl':
                if self.rl:
                    result_types = [self.rl.conv_result_type_name(x) for x in result_types]
                    result_types = sum([[self.rl.result_type_to_max(x), self.rl.result_type_to_tmax(x)] for x in result_types], [])
                    a = self.rl.maximums.df.columns
        result_types_ = []
        for rt in result_types:
            if rt.lower() in [x.lower() for x in a]:
                result_types_.append(a[[x.lower() for x in a].index(rt.lower())])
            else:
                result_types_.append(None)
        return result_types_

    def get_nodes(self, ids: list[str], result_types: list[str], type_: str) -> list[Corrected]:
        return self._get_base(ids, result_types, '1d', 'Node', type_, self.nodes)

    def get_channels(self, ids: list[str], result_types: list[str], type_: str) -> list[Corrected]:
        return self._get_base(ids, result_types, '1d', 'Channel', type_, self.channels)

    def get_po(self, ids: list[str], result_types: list[str], type_: str) -> list[Corrected]:
        return self._get_base(ids, result_types, '2d', 'PO', type_, self.po)

    def get_rl(self, ids: list[str], result_types: list[str], type_: str) -> list[Corrected]:
        return self._get_base(ids, result_types, '0d', 'RL', type_, self.rl)

    def _get_base(
            self,
            ids: list[str],
            result_types: list[str],
            domain: str,
            domain_2: str,
            type_: str,
            cls: TimeSeriesResultItem
    ) -> list[Corrected]:
        ids_, result_types_ = [], []
        if ids and cls is not None:
            ids_ = self.correct_id(ids, cls.df)
        if result_types and cls is not None:
            result_types_ = self.correct_result_type(result_types, domain_2, type_)
            if type_.lower() == 'max':
                result_types = sum([[x, x] for x in result_types], [])
        if not ids and cls is not None:
            ids_ = cls.ids(result_types_)
            ids = ids_
        if not result_types and cls is not None:
            result_types_ = cls.result_types(ids_)
            result_types = sum([[x, x] for x in result_types_], [])
            if type_.lower() == 'max':
                result_types_ = sum([[cls.result_type_to_max(x), cls.result_type_to_tmax(x)] for x in result_types_], [])
        if cls is None:
            if ids:
                ids_ = [None for _ in ids]
            if result_types:
                result_types_ = [None for _ in result_types]
        corrected = []
        for id1, id2 in zip(ids, ids_):
            for rt1, rt2 in zip(result_types, result_types_):
                corr = Corrected(id1, rt1, cls, id2, rt2)
                corrected.append(corr)
        return corrected
