from abc import ABC, abstractmethod
from datetime import datetime, timezone

import pandas as pd

from pytuflow.pytuflow_types import PathLike, TimeLike, PlotExtractionLocation, PlotExtractionDataType


class Output(ABC):
    """Base class for all TUFLOW output classes. This class should not be initialised directly."""

    _PLOTTING_CAPABILITY = []

    @abstractmethod
    def __init__(self, *fpath: PathLike) -> None:
        super().__init__()
        self._fpath = fpath

        #: str: The result name
        self.name = ''
        #: datetime: The reference time for the output
        self.reference_time = datetime(2000, 1, 1, tzinfo=timezone.utc)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} ({self.name})"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @abstractmethod
    def close(self) -> None:
        """Close the results."""
        pass

    @staticmethod
    @abstractmethod
    def looks_like_this(*fpath: PathLike) -> bool:
        """Check if the given file(s) look like this output type.

        Parameters
        ----------
        fpath : :class:`PathLike <pytuflow.pytuflow_types.PathLike>`
            The path to the output file(s).

        Returns
        -------
        bool
            True if the file(s) look like this output type.
        """
        pass

    @staticmethod
    @abstractmethod
    def looks_empty(*fpath: PathLike) -> bool:
        """Check if the given file(s) look empty or incomplete.

        Parameters
        ----------
        fpath : :class:`PathLike <pytuflow.pytuflow_types.PathLike>`
            The path to the output file(s).

        Returns
        -------
        bool
            True if the file(s) look empty.
        """
        pass

    @abstractmethod
    def times(self, context: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns all the available times for the output.

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
        pass

    @abstractmethod
    def data_types(self, context: str = None) -> list[str]:
        """Returns all the available data types (result types) for the output given the context.

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
        pass

    @abstractmethod
    def time_series(self, locations: PlotExtractionLocation, data_types: PlotExtractionDataType,
                    time_fmt: str = 'relative') -> pd.DataFrame:
        """Returns a time series dataframe for the given location and data type. The return DataFrame may have multiple
        time columns if the output time series data do not share a common time key.

        Parameters
        ----------
        locations : :doc:`pytuflow.pytuflow_types.PlotExtractionLocation`
            The location to extract the time series data for.
        data_types : :doc:`pytuflow.pytuflow_types.PlotExtractionDataType`
            The data type to extract the time series data for.
        time_fmt : str, optional
            The format for the time column. Options are 'relative' or 'absolute'.

        Returns
        -------
        pd.DataFrame
            The time series data.
        """
        pass

    @abstractmethod
    def section(self, locations: PlotExtractionLocation, data_types: PlotExtractionDataType,
                time: TimeLike) -> pd.DataFrame:
        """Returns a section dataframe for the given location and data type.

        Parameters
        ----------
        locations : :doc:`pytuflow.pytuflow_types.PlotExtractionLocation`
            The location to extract the section data for.
        data_types : :doc:`pytuflow.pytuflow_types.PlotExtractionDataType`
            The data type to extract the section data for.
        time : TimeLike
            The time to extract the section data for.

        Returns
        -------
        pd.DataFrame
            The section data.
        """
        pass

    @abstractmethod
    def curtain(self, locations: PlotExtractionLocation, data_types: PlotExtractionDataType,
                time: TimeLike) -> pd.DataFrame:
        """Returns a dataframe containing curtain plot data for the given location and data type.

        Parameters
        ----------
        locations : :doc:`pytuflow.pytuflow_types.PlotExtractionLocation`
            The location to extract the curtain data for.
        data_types : :doc:`pytuflow.pytuflow_types.PlotExtractionDataType`
            The data type to extract the curtain data for.
        time : TimeLike
            The time to extract the curtain data for.

        Returns
        -------
        pd.DataFrame
            The curtain data.
        """
        pass

    @abstractmethod
    def profile(self, locations: PlotExtractionLocation, data_types: PlotExtractionDataType,
                time: TimeLike) -> pd.DataFrame:
        """Returns a dataframe containing vertical profile data for the given location and data type.

        Parameters
        ----------
        locations : :doc:`pytuflow.pytuflow_types.PlotExtractionLocation`
            The location to extract the profile data for.
        data_types : :doc:`pytuflow.pytuflow_types.PlotExtractionDataType`
            The data type to extract the profile data for.
        time : TimeLike
            The time to extract the profile data for.

        Returns
        -------
        pd.DataFrame
            The profile data.
        """
        pass

    def has_plotting_capability(self, capability: str) -> bool:
        """Check if the output has a given plotting capability.

        The capability options are:

        * :code:`timeseries`
        * :code:`section`
        * :code:`curtain`
        * :code:`profile`

        Parameters
        ----------
        capability : str
            The capability to check for

        Returns
        -------
        bool
            True if the capability is present.
        """
        return capability.lower() in [x.lower() for x in self._PLOTTING_CAPABILITY]
