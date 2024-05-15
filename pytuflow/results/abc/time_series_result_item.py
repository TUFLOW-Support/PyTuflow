from datetime import datetime
from pathlib import Path
from typing import Union
from abc import ABC, abstractmethod

import numpy as np

from ..misc_tools import make_one_dim
from ..types import PathLike, TimeLike

import pandas as pd


class TimeSeriesResultItem(ABC):
    """
    Abstract base class for time series result items.

    Methods requiring implementation:
        load() -> None
        load_time_series() -> None
        count() -> int
        ids() -> list[str]
        result_types() -> list[str]
        timesteps() -> list[TimeLike]
        conv_result_type_name() -> str

    e.g. time series result items that subclass this are:
      - nodes
      - channels
      - po
      - rl

    This class would not typically be used directly, but rather the classes that subclass this would be used
    e.g. Nodes(TimeSeriesResultItem), Channels(TimeSeriesResultItem), etc.
    """

    def __init__(self, fpath: PathLike, *args, **kwargs) -> None:
        super().__init__()
        self.name = None
        self.domain = None
        self.domain_2 = None
        self.df = None
        if fpath is not None:
            self.fpath = Path(fpath)
        else:
            self.fpath = None
        if not hasattr(self, 'maximums'):
            self.maximums = None
        self.time_series = {}
        self.load()

    @abstractmethod
    def load(self, *args, **kwargs) -> None:
        """
        Load the result item. Load the metadat information, e.g. node names, result types, etc.

        Called by __init__.
        """
        raise NotImplementedError

    @abstractmethod
    def load_time_series(self, *args, **kwargs):
        """
        Load a time series result.
        A TimeSeries class holds information for all temporal results for a given result type (e.g. 'flow').

        The time series result should be stored in self.time_series['<result type name>'] = <TimeSeries class>
        e.g. self.time_series['Flow'] = <TimeSeries class> (e.g. loaded from M04_5m_001_1d_Q.csv)

        The result type name should not be converted to lowercase or anything like that.
        """
        raise NotImplementedError

    def count(self) -> int:
        """
        Returns the number of elements in the result item.
        e.g. if result item is storing channel information, then this would return channel count.
        """
        return len(self.ids(None))

    def ids(self, result_type: str) -> list[str]:
        """
        Return a list IDs for the given result type.

        :param result_type:
            If no result type is given, then return all IDs.
            The result_type must match exactly the result type name in the time_series dictionary.
            i.e. case correction, short name to long name conversion should be done before calling this method.
        """
        if self.df is None:
            return []
        if not result_type:
            return self.df.index.tolist()
        if result_type in self.time_series:
            return self.time_series[result_type].df.columns.tolist()
        return []

    def result_types(self, id: str) -> list[str]:
        """
        Returns a list of result_types for the given id.

        :param id:
            If no id is given, then return all result types.
            The id must be a valid id (case-sensitive).
            i.e. any case correction should be done before calling this method.
        """
        if not self.time_series:
            return []
        if not id:
            return list(self.time_series.keys())
        result_types = []
        for result_type, ts in self.time_series.items():
            if result_type not in result_types and id in [x for x in ts.df.columns] and id not in ts.empty_results:
                result_types.append(result_type)
        return result_types

    def maximum_types(self, id: str) -> list[str]:
        """
        Returns a list of maximum result_types for the given id.

        :param id:
            If no id is given, then return all result types.
            The id must be a valid id (case-sensitive).
            i.e. any case correction should be done before calling this method.
        """
        if not self.maximums:
            return []
        if not id:
            df = self.maximums.df
        else:
            df = self.maximums.df.loc[[id]]
        return [x.replace(' Max', '') for x in df.columns if 'TMax' not in x]

    def timesteps(self, dtype: str) -> list[TimeLike]:
        """
        Returns a list of time-steps for the given dtype.

        :param dtype:
            The return type can be either 'relative' e.g. hours or 'absolute' e.g. datetime.
        """
        if not self.time_series:
            return []

        for ts in self.time_series.values():
            return ts.timesteps(dtype)

    def get_time_series(self, id: list[str], result_type: list[str]) -> pd.DataFrame:
        """
        Returns the time series for the given id(s) and result type(s) and return as a DataFrame.

        The returned dataframe will return with an index column for each result type
        (i.e. will not be a single index column).
        The returned dataframe uses 5 levels of column indexes for the following:
            - Type (Node, Channel, PO, etc.)  - duplicate IDs can exist across different types, so this is needed
            - Result Type
            - ID
            - Type (Index or Value)
            - Index Name (if it is an index column e.g. Time (h))

        :param id:
            ID can be either a single value or list of values. The ID must be a valid ID (case-sensitive).
            i.e. case correction, short name to long name conversion should be done before calling this method.
        :param result_type:
            The result type can be a single value or a list of values and can be
            The result_type must match exactly the result type name in the time_series dictionary.
            i.e. case correction, short name to long name conversion should be done before calling this method.
        """
        df = pd.DataFrame()
        levels = ['Type', 'Result Type', 'ID', 'Index/Value', 'Index Name']
        for rt in result_type:
            if rt in self.time_series:
                # get the data values
                ids = [x for x in id if x in self.time_series[rt].df.columns]
                df_ = self.time_series[rt].df[ids].reset_index()
                df_ = self._expand_index_col(df_, rt, ids, levels)  # add the index col in-front of every value col
                df = pd.concat([df, df_], axis=1) if not df.empty else df_

        return df.dropna(how='all')

    def get_maximum(self, id: list[str], result_type: list[str]) -> pd.DataFrame:
        """
        Returns the maximum for the given id(s) and result type(s) and return as a DataFrame.

        :param id:
            ID can be either a single value or list of values. The ID must be a valid ID (case-sensitive).
            i.e. case correction, short name to long name conversion should be done before calling this method.
        :param result_type:
            The result type can be a single value or a list of values and can be
            The result_type must match exactly the result type name in the time_series dictionary.
            i.e. case correction, short name to long name conversion should be done before calling this method.
        """
        levels = ['Type', 'Result Type']
        col_names = [(self.name, x) for x in result_type]
        df = self.maximums.df.loc[id, result_type]
        df.columns = pd.MultiIndex.from_tuples(col_names, names=levels)
        return df

    def val(self, ids: list[str], result_type: str, timestep_index: int) -> pd.DataFrame:
        """
        Returns the result value for the given id(s), result type, and time-step index and return as a DataFrame.

        :param id:
            ID can be either a single value or list of values. The ID must be a valid ID (case-sensitive).
            i.e. case correction, short name to long name conversion should be done before calling this method.
        :param result_type:
            The result_type must match exactly the result type name in the time_series dictionary.
            i.e. case correction, short name to long name conversion should be done before calling this method.
        :param timestep_index:
            The time-step index must be a valid index.
        """
        if result_type in self.time_series:
            time = self.time_series[result_type].df.index[timestep_index]
            return self.time_series[result_type].df[ids].iloc[timestep_index].to_frame().rename(
                columns={time: result_type})
        return pd.DataFrame([], columns=[result_type])

    def _expand_index_col(self,
                          df: pd.DataFrame,
                          result_type: str,
                          id: list[str],
                          levels: list[str]) -> pd.DataFrame:
        index_name = self.time_series[result_type].df.index.name
        df = df[make_one_dim([[index_name, x] for x in id])]  # add the index col in-front of every value col
        index_alias = [(self.name, result_type, x, 'Index', index_name) for x in id]
        col_alias = [(self.name, result_type, x, 'Value', '') for x in id]
        df.columns = pd.MultiIndex.from_tuples(make_one_dim((zip(index_alias, col_alias))), names=levels)
        return df

    @abstractmethod
    def conv_result_type_name(self, result_type: str) -> str:
        """
        Returns a corrected result type name i.e. convert short-name to the correct name.

        :param result_type:
            Case-insensitive result type name or well known short name e.g. 'h' for 'Water Level'.
        """
        raise NotImplementedError

    @staticmethod
    def result_type_to_max(result_type: str) -> str:
        """
        Returns the maximum result type name given the result type name. The return name is the column name stored
        in the maximums DataFrame.

        :param result_type:
            The result_type must match exactly the result type name in the time_series dictionary.
            i.e. case correction, short name to long name conversion should be done before calling this method.
        """
        return f'{result_type} Max'

    @staticmethod
    def result_type_to_tmax(result_type: str) -> str:
        """
        Returns the time of maximum result type name given the result type name.
        The return name is the column name stored in the maximums DataFrame.

        :param result_type:
            The result_type must match exactly the result type name in the time_series dictionary.
            i.e. case correction, short name to long name conversion should be done before calling this method.
        """
        return f'{result_type} TMax'
