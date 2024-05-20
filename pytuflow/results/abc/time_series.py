from pytuflow.types import TimeLike


class TimeSeries:
    """Class to handle individual result time series data. e.g. Flow."""

    def __init__(self, *args, **kwargs) -> None:
        #: datetime.datetime: Reference time for the time series.
        self.reference_time = None
        #: pd.DataFrame: Dataframe containing time series data.
        self.df = None
        #: list[str]: List of empty results.
        self.empty_results = []

    def timesteps(self, dtype: str) -> list[TimeLike]:
        """Returns the time steps for the time series.

        Parameters
        ----------
        dtype : str
            Data type of the time steps. Can be 'absolute' or 'relative'.

        Returns
        -------
        list[TimeLike]
            List of time steps.
        """
        raise NotImplementedError
