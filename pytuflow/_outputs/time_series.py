from abc import abstractmethod
from datetime import timedelta, datetime
from typing import Union

import numpy as np
import pandas as pd

from .tabular_output import TabularOutput
from ..util import misc


class TimeSeries(TabularOutput):
    """Abstract base class for TUFLOW tabular, time series outputs."""

    @abstractmethod
    def maximum(self, locations: Union[str, list[str]], data_types: Union[str, list[str]],
                time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a dataframe containing the maximum values for the given data types. The returned dataframe
        will include time of maximum results as well.

        It's possible to pass in a well known short-hand for the data type e.g. 'q' for flow.

        The location can also be a contextual string, e.g. 'channel' to extract the maximum values for all channels.

        The returned DataFrame will have an index column corresponding to the location ids, and the columns
        will be in the format 'context/data_type/[max|tmax]',
        e.g. 'channel/flow/max', 'channel/flow/tmax'

        Parameters
        ----------
        locations : str | list[str]
            The location to extract the maximum values for.
        data_types : str | list[str]
            The data types to extract the maximum values for.
        time_fmt : str, optional
            The format for the time of max result. Options are 'relative' or 'absolute'

        Returns
        -------
        pd.DataFrame
            The maximum, and time of maximum values

        Examples
        --------
        Extracting the maximum flow for a given channel:

        >>> res = ... # Assume res is a time-series result instance
        >>> res.maximum('ds1', 'flow')
             channel/flow/max  channel/flow/tmax
        ds1            59.423           1.383333

        Extracting all the maximum results for a given channel:

        >>> res.maximum(['ds1'], None)
             channel/Flow/max  ...  channel/Velocity/tmax
        ds1            59.423  ...               0.716667

        Extracting the maximum flow for all channels:

        >>> res.maximum(None, 'flow')
                 channel/flow/max  channel/flow/tmax
        ds1                 59.423           1.383333
        ds2                 88.177           1.400000
        ...                  ...              ...
        FC04.1_C             9.530           1.316667
        FC_weir1            67.995           0.966667
        """
        pass

    def data_types(self, filter_by: str = None) -> list[str]:
        """Returns all the available data types (result types) for the given context.

        The context is an optional input that can be used to filter the return further. E.g. this can be used to
        return only data types that contain maximum results.

        Parameters
        ----------
        filter_by : str, optional
            The context to filter the data types by.

        Returns
        -------
        list[str]
            The available data types.
        """
        # generate a DataFrame with all a combination of result types that meet the context
        ctx = self._filter(filter_by)
        if ctx.empty:
            return []

        return ctx['data_type'].unique().tolist()

    def ids(self, filter_by: str = None) -> list[str]:
        """Returns all the available IDs for the given context.

        The context argument can be used to add a filter to the returned IDs. E.g. passing in a data type will return
        all the ids that contain that results for that data type.

        Parameters
        ----------
        filter_by : str, optional
            The context to filter the IDs by.

        Returns
        -------
        list[str]
            The available IDs.
        """
        # generate a DataFrame with all a combination of result types that meet the context
        ctx = self._filter(filter_by)
        if ctx.empty:
            return []

        return ctx['id'].unique().tolist()

    def _time_series_extractor(self, data_types: list[str], custom_names: list[str], time_series_data: dict,
                              ctx: pd.DataFrame, time_fmt: str, share_idx: bool,
                              reference_time: datetime) -> pd.DataFrame:
        """Extracts time-series data from a dictionary of time-series data. Helper method that can be accessed by all
        time-series output classes.

        Parameters
        ----------
        data_types : list[str]
            The list of data types to extract.
        custom_names : list[str]
            The list of custom names for the data types.
        time_series_data : dict
            The dictionary of time-series data.
        ctx : pd.DataFrame
            The context DataFrame.
        time_fmt : str
            The time format.
        share_idx : bool
            Whether to share the index.
        reference_time : datetime
            The reference time.

        Returns
        -------
        pd.DataFrame
            The extracted time-series data.
        """
        df = pd.DataFrame()
        for dtype2 in data_types:
            dtype = [x for x in custom_names if self._get_standard_data_type_name(x) == dtype2]
            dtype = dtype[0] if dtype else dtype2
            if dtype2 not in time_series_data:
                continue
            for res_df in time_series_data[dtype2]:
                idx = res_df.columns[res_df.columns.isin(ctx['id'])]
                if idx.empty:
                    continue
                df1 = res_df.loc[:, idx]
                if time_fmt == 'absolute':
                    # noinspection PyTypeChecker
                    df1.index = [reference_time + timedelta(hours=x) for x in df1.index]
                df1.index.name = 'time'
                index_name = df1.index.name
                if not share_idx:
                    col_names = misc.flatten([[index_name, x] for x in df1.columns])
                    df1.reset_index(inplace=True, drop=False)
                    df1 = df1[col_names]

                df1.columns = [f'{x}/{dtype}/{df1.columns[i + 1]}' if x == index_name else f'{dtype}/{x}' for i, x in
                               enumerate(df1.columns)]
                df = df1 if df.empty else pd.concat([df, df1], axis=1)

        # remove -99999 values as these are used to indicate dry for RL results
        mask = (df.select_dtypes(include=[np.number]) < -99998)
        df.loc[:, mask.columns] = df.loc[:, mask.columns].where(~mask, np.nan)

        return df

    def _maximum_extractor(self, data_types: list[str], custom_names: list[str], maximum_data: dict,
                          ctx: pd.DataFrame, time_fmt: str, reference_time: datetime) -> pd.DataFrame:
        """Extracts maximum data from a dictionary of maximum data. Helper method that can be accessed by all
        time-series output classes.

        Parameters
        ----------
        data_types : list[str]
            The list of data types to extract.
        custom_names : list[str]
            The list of custom names for the data types.
        maximum_data : dict
            The dictionary of maximum data.
        ctx : pd.DataFrame
            The context DataFrame.
        time_fmt : str
            The time format.
        reference_time : datetime
            The reference time.

        Returns
        -------
        pd.DataFrame
            The extracted maximum data.
        """
        df = pd.DataFrame()
        for dtype2 in data_types:
            dtype = [x for x in custom_names if self._get_standard_data_type_name(x) == dtype2]
            dtype = dtype[0] if dtype else dtype2
            if dtype2 not in maximum_data:
                continue
            for res_df in maximum_data[dtype2]:
                rows = res_df.index[res_df.index.isin(ctx['id'])]
                df1 = res_df.loc[rows]
                if time_fmt == 'absolute':
                    df1['tmax'] = df1['tmax'].apply(lambda x: reference_time + timedelta(hours=x))
                df1.columns = [f'{dtype}/{x}' for x in df1.columns]
                if df.empty:
                    df = df1
                else:
                    df = pd.concat([df, df1], axis=1)
        return df
