import re
from typing import Generator, Union
from dataclasses import dataclass, field

import pandas as pd

from .abc.channels import Channels
from .abc.nodes import Nodes
from .abc.time_series_result_item import TimeSeriesResultItem


@dataclass
class Corrected:
    """
    Class for storing information on corrected IDs and result types.

    e.g.
        id_orig = 'case-insensitive' name
        id = 'Case Sensitive' name (corrected to match id case exactly)
        result_type_orig = 'short name' or 'case-insensitive' name
        result_type = 'Full Name' (corrected to match result type exactly)

    :param id_orig: Original ID (case-insensitive)
    :param result_type_orig: Original result type (case-insensitive)
    :param result_item: Time series result item class (e.g. Nodes, Channels, PO, RL)
    :param id: Corrected ID (case-sensitive)
    :param result_type: Corrected result type (case-sensitive)
    """
    id_orig: str
    result_type_orig: str
    result_item: TimeSeriesResultItem
    id: str
    result_type: str

    @property
    def valid(self) -> bool:
        """Class is valid if a correct ID and result type have been found."""
        return self.id is not None and self.result_type is not None


@dataclass
class IDResultTypeItem:
    """
    Class for storing information on a collection of corrected IDs and result types.

    The corrected items should be grouped by the same time series result items e.g.  ids and result types
    contained in the Nodes class will be grouped into one IDResultTypeItem class.

    :param: result_item_name: Name of the time series result item class (e.g. Nodes, Channels, PO, RL)
    :param: correct: List of Corrected items
    :param: remove_invalid: If True, remove invalid Corrected items (i.e. Corrected items where valid is False)
    """
    result_item_name: str
    correct: list[Corrected]
    remove_invalid: bool
    ids: list[str] = field(init=False)
    result_types: list[str] = field(init=False)
    result_item: TimeSeriesResultItem = field(init=False)

    def __post_init__(self) -> None:
        """Post init routine - sets ids, result_types and result_item attributes."""
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
        """Removes invalid Corrected items (i.e. Corrected items where valid is False)"""
        for item in self.correct.copy():
            if not item.valid:
                self.correct.remove(item)

    @property
    def valid(self) -> bool:
        """Class is valid if there are any Corrected items."""
        return bool(self.correct)


class ErrorMessage:

    def __init__(self, corr_items: list[Corrected], domain_2: str, user_comb: bool) -> None:
        self.corr_items = corr_items
        self.corr_item = None
        self.valid_id_somewhere = any([x.id for x in corr_items])
        self.valid_rt_somewhere = any([x.result_type for x in corr_items])
        if self.valid_id_somewhere and self.valid_rt_somewhere:
            self.corr_item = next(x for x in corr_items if x.result_type)
        elif self.corr_items:
            self.corr_item = corr_items[0]
        self.domain_2 = domain_2
        self.user_comb = user_comb

    def build_err_msg(self) -> str:
        if self.corr_item is None:
            return 'No valid returns found in the given combination of IDs and result types.'  # shouldn't get here
        not_found_id, not_found_type = self.not_found()
        if not not_found_id:
            return 'No valid returns found in the given combination of IDs and result types.'  # shouldn't get here
        against_type = self.against_type()
        if not against_type:
            return f'{not_found_id} is not a valid {not_found_type}.'
        elif self.user_comb:
            return f'{not_found_id} {against_type}.'
        return f'{not_found_id} {against_type} {not_found_type}.'

    def not_found(self) -> tuple[str, str]:
        if self.user_comb:
            if not self.valid_id_somewhere:
                return f'"{self.corr_item.id_orig}"', 'ID'
            elif not self.valid_rt_somewhere:
                return f'"{self.corr_item.result_type_orig}"', 'result type'
        if self.corr_item.id is None:
            return f'"{self.corr_item.id_orig}"', 'ID'
        elif self.corr_item.result_type is None:
            return f'"{self.corr_item.result_type_orig}"', 'result type'
        return None, None

    def against_type(self) -> str:
        if self.user_comb and self.corr_item.result_type and self.valid_id_somewhere:
            return f'does not have "{self.corr_item.result_type}" result type'
        if self.user_comb and self.valid_id_somewhere and not self.valid_rt_somewhere:
            return f'is not a valid result type'
        if self.domain_2 != 'nothing yielded':
            return f'is not a valid {self.corr_item.result_item.name}'



class Iterator:
    """
    Class for helping iterate over valid IDs and result type combinations. This class will also correct IDs and
    result type names so that they match the expected case correctly and convert result type short names to full names.

    In a lot of instances in the TimeSeriesResult class, the arguments are IDs, result types, and domain. This class
    offers a single location to iterate over valid combinations of these inputs while correcting the IDs and
    result types.
    """

    def __init__(self, *result_items: TimeSeriesResultItem) -> None:
        """
        Initialise with all available result items. e.g. Nodes, Channels, PO, RL
        List should only contain one instance of each type of result item class
        (e.g. shouldn't have 2 Node classes even if they contain unique data).
        """
        self._result_items = [x for x in result_items if x]

    def raise_exception(self, corr_items: list[Corrected], domain_2: str, user_comb: bool = False) -> None:
        """
        Raises an exception with useful info if something is wrong
        e.g. wrong result type for a given  domain_2 ('level' for a 'channel')
        """
        item = IDResultTypeItem('dummy', corr_items.copy(), True)
        if domain_2 and corr_items and not item.valid:  # something is wrong
            err_msg = ErrorMessage(corr_items, domain_2, user_comb).build_err_msg()
            raise ValueError(err_msg)


    def id_result_type(self,
                       ids: Union[str, list[str]],
                       result_types: Union[str, list[str]],
                       domain: str,
                       type_: str,
                       ) -> Generator[IDResultTypeItem, None, None]:
        """
        Yields valid IDResultTypeItem class that contains valid ID and result type combinations for the given domain.

        e.g.
            input ids: ['node1', 'node2']
            result_types = ['h']
            domain = '1d'
            type_ = 'temporal'

            This will yield one IDResultTypeItem class that contains corrected IDs and result types contained within
            the Node class (since all ids are nodes).
            i.e.
            yield IDResultTypeItem(
                       result_item_name='Node', ids=['Node1', 'Node2'], result_types=['Water Level'], result_item=Nodes
            )

        :param ids:
            Single ID value or list of IDs. IDs do not need to be case-sensitive.
            If no IDs are given, all available IDs will be used.
        :param result_types:
            Single result type name or list of result types. Result types do not need to be case-sensitive
            and can be short names.
            If no result types are given, all available result types will be used.
        :param domain:
            Can be '1d', '2d', '0d', or None. Can also include a space and a second domain e.g. '1d node'.
            If None, all domains will be used.
        :param type_:
            Can be 'temporal', 'max'. If 'max' then the maximum result name and time of max name will be provided.
        """
        # convert to lists
        if not isinstance(ids, list):
            ids = [ids] if ids else []
        if not isinstance(result_types, list):
            result_types = [result_types] if result_types else []

        # separate domain and domain_2
        domain_2 = None
        if domain is not None:
            s = domain.split(' ', 1)
            if len(s) == 2:
                domain, domain_2 = s

        # yield valid IDResultTypeItem classes
        something_yielded = False
        all_corr_items = []
        for result_item in self._result_items:
            if not domain or result_item.domain.lower() == domain.lower():
                if not domain_2 or result_item.domain_2.lower() == domain_2.lower():
                    corr_items = self._corrected_items(ids, result_types, result_item.domain_2, type_, result_item)
                    all_corr_items.extend(corr_items)

                    # check if user has passed in something wrong (e.g. a channel ID that doesn't exist)
                    # try and catch this and give a useful message
                    self.raise_exception(corr_items, domain_2)  # only raises exception if something is wrong

                    item = IDResultTypeItem(result_item.name, corr_items, True)
                    if item.valid:
                        something_yielded = True
                        yield item

        if not something_yielded:
            self.raise_exception(all_corr_items, 'nothing yielded', bool(ids) and bool(result_types))

    def lp_id_result_type(self,
                          ids: Union[str, list[str]],
                          result_types: Union[str, list[str]]
                          ) -> Generator[IDResultTypeItem, None, None]:
        """
        Yields valid IDResultTypeItem class that contains valid ID and result type combinations for the given domain.
        Similar to id_result_type_comb(), but for long profile results where the ids are channels and the result types
        are from node results.

        Domain is not required as it is always '1d channel' for ids and '1d node' for result types.
        type_ is also not required since it will deal with both temporal and max within this routine.
        This class always only yields 1 IDResultTypeItem class since it is only extracting results from one domain.

        :param ids:
            Single ID value or list of IDs. IDs do not need to be case-sensitive.
            Require at least one ID.
        :param result_types:
            Single result type name or list of result types. Result types do not need to be case-sensitive
            and can be short names.
            If no result types are given, all available result types will be used.
        """
        from .lp_1d import LP_1D  # import here to prevent circular import

        if not isinstance(ids, list):
            ids = [ids] if ids is not None else []
        if not isinstance(result_types, list):
            result_types = [result_types] if result_types is not None else []

        # find node and channel result items
        result_items = [x for x in self._result_items if x.name == 'Node' or x.name == 'Channel']
        if len(result_items) != 2:
            raise Exception('Need exactly 2 result items (Nodes and Channels) to extract LP results.')
        if result_items[0].name == 'Node':
            nodes, channels = result_items
        else:
            channels, nodes = result_items

        # get corrected ids (from channels)
        ids_ = []
        for corr_item in self._corrected_items(ids, [], 'channel', 'temporal', channels):
            if corr_item.id is not None and corr_item.id_orig in ids and corr_item.id not in ids_:
                ids_.append(corr_item.id)
        if not ids_ and ids and not channels.result_types(None):  # if channels has not result types (FM result)
            ids_ = self._correct_id(ids, channels.df)

        # separate static result types (not including maximums)
        static_result_types, static_result_types_corr_names = LP_1D.extract_static_results(result_types)
        static_result_types = {x: y for x, y in zip(static_result_types, static_result_types_corr_names)}

        # get corrected result types
        result_types_ = []
        for corr_item in self._corrected_items([], result_types, 'node', 'temporal', nodes):
            if corr_item.result_type_orig in static_result_types and static_result_types[corr_item.result_type_orig] not in result_types_:
                result_types_.append(static_result_types[corr_item.result_type_orig])
            elif corr_item.result_type is not None and corr_item.result_type not in result_types_:
                result_types_.append(corr_item.result_type)

        # deal with maximums
        max_result_types = [re.sub(r'max(imum)?', '', x, flags=re.IGNORECASE).strip() for x in result_types if 'max' in x.lower()]
        if max_result_types:
            for corr_item in self._corrected_items([], max_result_types, 'node', 'max', nodes):
                if corr_item.result_type is not None and corr_item.result_type not in result_types_:
                    result_types_.append(corr_item.result_type)

        # combine ids and result types and yield IDResultTypeItem
        corrected = []
        for id1, id2 in zip(ids_, ids_):
            for rt1, rt2 in zip(result_types_, result_types_):
                corr = Corrected(id1, rt1, nodes, id2, rt2)
                corrected.append(corr)
        yield IDResultTypeItem('Node', corrected, False)

    def _correct_id(self, ids: list[str], df: pd.DataFrame) -> list[str]:
        """
        Returns a list of corrected IDs (correct case) else None if ID is not found.

        :param ids:
            list of IDs to correct
        :param df:
            DataFrame containing IDs in the index
        """
        ids_ = []
        for id_ in ids:
            if str(id_).lower() in [str(x).lower() for x in df.index]:
                ids_.append(df.index[[str(x).lower() for x in df.index].index(str(id_).lower())])
            else:
                ids_.append(None)
        return ids_

    def _correct_result_type(self, result_types: list[str], domain_2: str, type_: str) -> list[str]:
        """
        Returns a list of corrected result types (correct case and convert short names to full names) else None if
        result type is not found.

        :param result_types:
            list of result types to correct
        :param domain_2:
            usually one of 'node', 'channel', 'po', 'rl'
        :param type_:
            either 'temporal' or 'max'
        """
        # convert result type short names to full names and collect available result types
        a = []
        for result_item in self._result_items:
            if result_item.domain_2.lower() == domain_2.lower():
                result_types = [result_item.conv_result_type_name(x) for x in result_types]
                if type_.lower() == 'max':
                    if result_item.maximums is not None and result_item.maximums.df is not None:
                        result_types = sum([[result_item.result_type_to_max(x), result_item.result_type_to_tmax(x)] for x in result_types],[])
                        a = result_item.maximums.df.columns
                    else:
                        a = []
                else:
                    a = result_item.result_types(None)

        # correct result type case if available else return None
        result_types_ = []
        for rt in result_types:
            if rt.lower() in [x.lower() for x in a]:
                result_types_.append(a[[x.lower() for x in a].index(rt.lower())])
            else:
                result_types_.append(None)

        return result_types_

    def _corrected_items(self,
                         ids: list[str],
                         result_types: list[str],
                         domain_2: str,
                         type_: str,
                         cls: TimeSeriesResultItem
                         ) -> list[Corrected]:
        """
        Returns a list of Corrected items for the given IDs, result types, and domain_2.

        :param ids:
            list of IDs to correct
        :param result_types:
            list of result types to correct
        :param domain_2:
            usually one of 'node', 'channel', 'po', 'rl'
        :param type_:
            either 'temporal' or 'max'
        :param cls:
            result item class (e.g. Nodes, Channels, PO, RL)
        """
        ids_, result_types_, result_types_temp, = [], [], []
        if ids and cls is not None:
            ids_ = self._correct_id(ids, cls.df)
        if result_types and cls is not None:
            result_types_ = self._correct_result_type(result_types, domain_2, type_)
            if type_.lower() == 'max':
                result_types = sum([[x, x] for x in result_types], [])
                result_types_temp = self._correct_result_type(result_types, domain_2, 'temporal')
                result_types_temp = sum([[x, x] for x in result_types_temp], [])
        if not ids and cls is not None:
            ids_ = []
            rts = result_types_
            if type_.lower() == 'max':
                rts = result_types_temp
            if rts:
                for rt in rts:
                    for id_ in cls.ids(rt):
                        if id_ not in ids_:
                            ids_.append(id_)
            else:
                ids_ = cls.ids(None)
            ids = ids_
        if not result_types and cls is not None:
            result_types_ = []
            for id_ in ids_:
                if type_.lower() == 'max':
                    for rt in cls.maximum_types(id_):
                        if rt not in result_types_:
                            result_types_.append(rt)
                else:
                    for rt in cls.result_types(id_):
                        if rt not in result_types_:
                            result_types_.append(rt)
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
