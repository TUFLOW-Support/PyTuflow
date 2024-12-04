from abc import abstractmethod

import pandas as pd

from .tabular_output import TabularOutput
from ..pytuflow_types import PlotExtractionDataType, PlotExtractionLocation


class TimeSeries(TabularOutput):
    """Class for TUFLOW (tabular) time series outputs."""

    @abstractmethod
    def maximum(self, locations: PlotExtractionLocation, data_types: PlotExtractionDataType,
                time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a dataframe containing the maximum values for the given data types. The returned dataframe
        will include time of maximum results as well.

        It's possible to pass in a well known short-hand for the data type e.g. 'q' for flow.

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
