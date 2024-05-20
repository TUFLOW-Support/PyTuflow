import itertools
import re
from typing import Generator, Union
from dataclasses import dataclass, field

import pandas as pd

from .abc.channels import Channels
from .abc.nodes import Nodes
from .abc.time_series_result_item import TimeSeriesResultItem
from pytuflow.tmf.tmf.tuflow_model_files.dataclasses.case_insensitive_dict import CaseInsDict


@dataclass
class Corrected:
    """Class for storing information on corrected IDs and result types returned as part of a collection from the
    :doc:`Iterator <pytuflow.results.Iterator>` class.

    | e.g.
    |    id_orig = 'case-insensitive' name
    |    id = 'Case Sensitive' name (corrected to match id case exactly)
    |    result_type_orig = 'short name' or 'case-insensitive' name
    |    result_type = 'Full Name' (corrected to match result type exactly)
    """
    #: str: Original ID (case-insensitive)
    id_orig: str
    #: str: Short name or case-insensitive result type name
    result_type_orig: str
    #: :doc:`TimeSeriesResultItem <pytuflow.results.TimeSeriesResultItem>`: Time series result item class (e.g. Nodes, Channels, PO, RL)
    result_item: TimeSeriesResultItem
    #: str: Corrected ID (case-sensitive)
    id: str
    #: str: Corrected result type (case-sensitive)
    result_type: str

    @property
    def valid(self) -> bool:
        """: bool: Class is valid if a correct ID and result type have been found."""
        return self.id is not None and self.result_type is not None


@dataclass
class IDResultTypeItem:
    """Class for storing information on a collection of corrected IDs and result types.

    The corrected items are grouped by the same time series result items e.g. IDs and result types
    contained in the Nodes class will be grouped into one IDResultTypeItem class.
    """
    #: str: Name of the time series result item class (e.g. Nodes)
    result_item_name: str
    #: list[Corrected]: List of Corrected items
    correct: list[Corrected]
    #: bool: If True, remove invalid Corrected items (i.e. Corrected items where valid is False)
    remove_invalid: bool
    #: list[str]: List of corrected IDs
    ids: list[str] = field(init=False)
    #: list[str]: List of corrected result types
    result_types: list[str] = field(init=False)
    #: :doc:`TimeSeriesResultItem <pytuflow.results.TimeSeriesResultItem>`: Time series result item class (e.g. Nodes)
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
        """: bool: Class is valid if there are any Corrected items."""
        return bool(self.correct)


class ErrorMessage:
    """Class to build error messages for the Iterator class. This class will check if the user has passed in something
    incorrect (e.g. a channel ID that doesn't exist) and give a useful message.

    TODO: check if this is slow for a dataset with a lot of channels/nodes
    """

    def __init__(self, corr_items: list[Corrected], domain_2: str, user_comb: bool) -> None:
        #: list[Corrected]: List of Corrected items
        self.corr_items = corr_items
        #: str: subdomain name (e.g. 'node', 'channel', 'po', 'rl')
        self.domain_2 = domain_2
        #: bool: If True, user has passed in a combination of both IDs and result types
        self.user_comb = user_comb
        #: :doc:`IDResultTypeItem<pytuflow.results.IDResultTypeItem>`: copy of corrected items argument
        self.item = IDResultTypeItem('dummy', corr_items.copy(), True)

        #: list[str]: original ids (maybe passed by user - could be wrong case)
        self.oids = set([x.id_orig for x in corr_items])
        #: list[str]: original result types (maybe passed by user - could be wrong case or short name e.g. 'h')
        self.orts = set([x.result_type_orig for x in corr_items])

        #: list[str]: valid original ids (they have been found and corrected, so the id does exist somewhere in the results)
        self.valid_oids = set([x.id_orig for x in corr_items if x.id])
        #: list[str]: valid original result types (they have been found and corrected, so the result type does exist somewhere in the results)
        self.valid_orts = set([x.result_type_orig for x in corr_items if x.result_type])

        #: list[str]: unique ids (corrected) - if 'None' is in this set, that means an ID passed by the user does not exist in the results
        self.uids = set([x.id for x in corr_items if x.id is not None or x.id_orig not in self.valid_oids])
        #: list[str]: unique result types (corrected) - if 'None' is in this set, that means a result type passed by the user does not exist in the results
        self.urts = set([x.result_type for x in corr_items if x.result_type is not None or x.result_type_orig not in self.valid_orts])

        #: bool: if there is a valid id somewhere in the results
        self.valid_id_somewhere = any([x.id for x in corr_items])
        #: bool: if there is a valid result type somewhere in the results
        self.valid_rt_somewhere = any([x.result_type for x in corr_items])

        #: Corrected: get the first corrected item that is not valid (or just return the first if nothing is found)
        self.corr_item = self.get_corr_item()

    def get_corr_item(self) -> Corrected:
        """Returns the first corrected item that is not valid.

        Returns
        -------
        Corrected
        """
        if not self.item.valid:
            if self.valid_id_somewhere and self.valid_rt_somewhere:
                return next(x for x in self.corr_items if x.result_type)
            elif self.corr_items:
                return self.corr_items[0]
        elif None in self.uids:
            return next(x for x in self.corr_items if x.id is None and x.id_orig not in self.valid_oids)
        elif None in self.urts:
            return next(x for x in self.corr_items if x.result_type is None and x.result_type_orig not in self.valid_orts)
        if self.corr_items:
            return self.corr_items[0]

    def is_err(self) -> bool:
        """Returns True if there is a user error in the corrected items.

        Returns
        -------
        bool
        """
        return self.corr_items and self.domain_2 and (not self.item.valid or None in self.uids or None in self.urts)

    def build_err_msg(self) -> str:
        """Builds an error message for the user. Should only be called if is_err() returns True.

        Returns
        -------
        str
        """
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
        """Returns the ID and result type that are not found in the results.

        Returns
        -------
        tuple[str, str]
            not_found_id, not_found_type
        """
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
        """Returns a string that describes the error.

        Returns
        -------
        str
        """
        if self.user_comb and self.corr_item.result_type and self.valid_id_somewhere:
            return f'does not have "{self.corr_item.result_type}" result type'
        if self.user_comb and self.valid_id_somewhere and not self.valid_rt_somewhere:
            return f'is not a valid result type'
        if self.domain_2 != 'nothing yielded':
            return f'is not a valid {self.corr_item.result_item.name}'


class Iterator:
    """Class for helping iterate over valid IDs and result type combinations. This class will correct IDs and
    result type names so that they match the expected case correctly and convert result type short names to full names.

    In a lot of instances in the TimeSeriesResult class, the arguments are IDs, result types, and domain. This class
    offers a single location to iterate over valid combinations of these inputs while correcting the IDs and
    result types.
    """

    def __init__(self, *result_items: TimeSeriesResultItem) -> None:
        """Initialise with all available result items. e.g. Nodes, Channels, PO, RL
        List should only contain one instance of each type of result item class
        (e.g. shouldn't have 2 Node classes even if they contain unique data).

        Parameters
        ----------
        *result_items : TimeSeriesResultItem
            All available result items (e.g. Nodes, Channels, PO, RL)
        """
        self._result_items = [x for x in result_items if x]

    def raise_exception(self, corr_items: list[Corrected], domain_2: str, user_comb: bool = False) -> None:
        """Raises an exception with useful info if something is wrong
        e.g. wrong result type for a given  domain_2 ('level' for a 'channel')

        Parameters
        ----------
        corr_items : list[Corrected]
            List of Corrected items
        domain_2 : str
            subdomain name (e.g. 'node', 'channel', 'po', 'rl')
        user_comb : bool, optional
            If True, user has passed in a combination of both IDs and result types
        """
        err_msg = ErrorMessage(corr_items, domain_2, user_comb)
        if err_msg.is_err():
            raise ValueError(err_msg.build_err_msg())

    def id_result_type(self,
                       ids: Union[str, list[str]],
                       result_types: Union[str, list[str]],
                       domain: str,
                       type_: str,
                       ) -> Generator[IDResultTypeItem, None, None]:
        """Yields valid IDResultTypeItem class that contains valid ID and result type combinations for the given domain.

        Parameters
        ----------
        ids : Union[str, list[str]]
            Single ID value or list of IDs. IDs do not need to be case-sensitive.
            If no IDs are given, all available IDs will be used.
        result_types : Union[str, list[str]]
            Single result type name or list of result types. Result types do not need to be case-sensitive
            and can be short names.
            If no result types are given, all available result types will be used.
        domain : str
            Can be '1d', '2d', '0d', or None. Can also include a space and a second domain e.g. '1d node'.
            If None, all domains will be used.
        type_ : str
            Can be 'temporal', 'max'. If 'max' then the maximum result name and time of max name will be provided.

        Yields
        ------
        IDResultTypeItem
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
                        yield item

        self.raise_exception(all_corr_items, 'nothing yielded', bool(ids) and bool(result_types))

    def lp_id_result_type(self,
                          ids: Union[str, list[str]],
                          result_types: Union[str, list[str]]
                          ) -> Generator[IDResultTypeItem, None, None]:
        """Yields valid IDResultTypeItem class that contains valid ID and result type combinations for the given domain.
        Similar to id_result_type(), but for long profile results where the ids are channels and the result types
        are from node results.

        Parameters
        ----------
        ids : Union[str, list[str]]
            Single ID value or list of IDs. IDs do not need to be case-sensitive.
            Require at least one ID.
        result_types : Union[str, list[str]]
            Single result type name or list of result types. Result types do not need to be case-sensitive
            and can be short names.
            If no result types are given, all available result types will be used.

        Yields
        ------
        IDResultTypeItem
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
        corr_items = self._corrected_items(ids, [], 'channel', 'temporal', channels)

        # check if user has passed in something wrong (e.g. a channel ID that doesn't exist)
        # try and catch this and give a useful message
        self.raise_exception(corr_items, 'channel')  # only raises exception if something is wrong

        for corr_item in self._corrected_items(ids, [], 'channel', 'temporal', channels):
            if corr_item.id is not None and corr_item.id_orig in ids and corr_item.id not in ids_:
                ids_.append(corr_item.id)
        if not ids_ and ids and not channels.result_types(None):  # if channels has no result types (FM result)
            ids_ = self._correct_id(ids, channels.df)

        # separate static result types (not including maximums)
        static_result_types, static_result_types_corr_names = LP_1D.extract_static_results(result_types)
        static_result_types = {x: y for x, y in zip(static_result_types, static_result_types_corr_names)}

        # deal with maximums - initially remove them
        max_result_types = {x: re.sub(r'max(imum)?', '', x, flags=re.IGNORECASE).strip() for x in result_types if 'max' in x.lower()}
        for rt in result_types.copy():
            if rt in max_result_types:
                result_types.remove(rt)

        # get corrected result types - temporal
        result_types_ = []
        corr_items = self._corrected_items([], result_types, 'node', 'temporal', nodes, valid_rts=static_result_types)

        # check if user has passed in something wrong (e.g. a channel ID that doesn't exist)
        # try and catch this and give a useful message
        self.raise_exception(corr_items, 'node')  # only raises exception if something is wrong

        for corr_item in self._corrected_items([], result_types, 'node', 'temporal', nodes):
            if corr_item.result_type_orig in static_result_types and static_result_types[corr_item.result_type_orig] not in result_types_:
                result_types_.append(static_result_types[corr_item.result_type_orig])
            elif corr_item.result_type is not None and corr_item.result_type not in result_types_:
                result_types_.append(corr_item.result_type)

        # finish dealing with maximums
        corr_items = self._corrected_items([], list(max_result_types.values()), 'node', 'max', nodes)
        self.raise_exception(corr_items, 'node')  # only raises exception if something is wrong
        if max_result_types:
            for corr_item in corr_items:
                if corr_item.result_type is not None and corr_item.result_type not in result_types_:
                    result_types_.append(corr_item.result_type)

        # combine ids and result types and yield IDResultTypeItem
        corrected = []
        for id1, id2 in zip(ids_, ids_):
            for rt1, rt2 in zip(result_types_, result_types_):
                corr = Corrected(id1, rt1, nodes, id2, rt2)
                corrected.append(corr)

        yield IDResultTypeItem('Node', corrected, False)

    def _correct_id(self, ids: list[str], df: pd.DataFrame, valid_ids: dict = None) -> list[str]:
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
            elif valid_ids and id_ in valid_ids:
                ids_.append(valid_ids[id_])
            else:
                ids_.append(None)
        return ids_

    def _correct_result_type(self, result_types: list[str], domain_2: str, type_: str, valid_rts: dict = None) -> list[str]:
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
        if valid_rts:
            valid_rts = CaseInsDict(valid_rts)
        result_types_ = []
        for rt in result_types:
            if rt.lower() in [x.lower() for x in a]:
                result_types_.append(a[[x.lower() for x in a].index(rt.lower())])
            elif valid_rts and rt in valid_rts:
                result_types_.append(valid_rts[rt])
            else:
                result_types_.append(None)

        return result_types_

    def _corrected_items(self,
                         ids: list[str],
                         result_types: list[str],
                         domain_2: str,
                         type_: str,
                         cls: TimeSeriesResultItem,
                         valid_ids: dict = None,
                         valid_rts: dict = None
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
            ids_ = self._correct_id(ids, cls.df, valid_ids)
        if result_types and cls is not None:
            result_types_ = self._correct_result_type(result_types, domain_2, type_, valid_rts)
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
