from abc import abstractmethod
from datetime import timedelta

import numpy as np
import pandas as pd

from .tabular_output import TabularOutput
from ..pytuflow_types import PlotExtractionDataType, PlotExtractionLocation, TimeLike


class TimeSeries(TabularOutput):
    """Class for TUFLOW (tabular) time series outputs."""

    @abstractmethod
    def maximum(self, locations: PlotExtractionLocation, data_types: PlotExtractionDataType,
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

    def context_combinations(self, context: str) -> pd.DataFrame:
        """Returns a DataFrame with the output combinations for the given context string.

        Parameters
        ----------
        context : str
            The context to extract the combinations for.

        Returns
        -------
        pd.DataFrame
            The context combinations.
        """
        return pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt', 'domain'])

    def times(self, context: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns all the available times for the given context.

       The context is an optional input that can be used to filter the return further. E.g. this can be used to
       get the times only for a given 1D channel.

       Parameters
       ----------
       context : str, optional
           The context to filter the times by.
       fmt : str, optional
           The format for the times. Options are 'relative' or 'absolute'.

       Returns
       -------
       list[TimeLike]
           The available times in the requested format.
       """
        def generate_times(row):
            return np.arange(row['start'], row['end'] + row['dt'] / 3600., row['dt'] / 3600.)

        # generate a DataFrame with all a combination of result types that meet the context
        ctx = self.context_combinations(context)
        if ctx.empty:
            return []

        # generate a lit of times based on the unique start, end and dt values
        time_prop = ctx[['start', 'end', 'dt']].drop_duplicates()
        time_prop['times'] = time_prop.apply(generate_times, axis=1)
        combined_times = pd.Series([time for times_list in time_prop['times'] for time in times_list])
        unique_sorted_times = pd.Series(combined_times.unique()).sort_values().reset_index(drop=True)

        if fmt == 'absolute':
            return [self.reference_time + timedelta(hours=x) for x in unique_sorted_times.tolist()]
        return unique_sorted_times.tolist()

    def data_types(self, context: str = None) -> list[str]:
        """Returns all the available data types (result types) for the given context.

        The context is an optional input that can be used to filter the return further. E.g. this can be used to
        return only data types that contain maximum results.

        Parameters
        ----------
        context : str, optional
            The context to filter the data types by.

        Returns
        -------
        list[str]
            The available data types.
        """
        # generate a DataFrame with all a combination of result types that meet the context
        ctx = self.context_combinations(context)
        if ctx.empty:
            return []

        return ctx['data_type'].unique().tolist()

    def ids(self, context: str = None) -> list[str]:
        """Returns all the available IDs for the given context.

        The context argument can be used to add a filter to the returned IDs. E.g. passing in a data type will return
        all the ids that contain that results for that data type.

        Parameters
        ----------
        context : str, optional
            The context to filter the IDs by.

        Returns
        -------
        list[str]
            The available IDs.
        """
        # generate a DataFrame with all a combination of result types that meet the context
        ctx = self.context_combinations(context)
        if ctx.empty:
            return []

        return ctx['id'].unique().tolist()
