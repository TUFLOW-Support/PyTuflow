import pandas as pd

from ..abc.time_series import TimeSeries


class HydTableTimeSeries(TimeSeries):
    """Class to handle individual HydTable result plottable data."""

    def __init__(self, result_type: str, database: pd.DataFrame, index_col: str) -> None:
        """
        Parameters
        ----------
        result_type : str
            Result type. e.g. 'Area'.
        database : pd.DataFrame
            DataFrame containing the result data.
        index_col : str
            Column name to use as the index.
        """
        super().__init__()
        self.result_type = result_type
        self.df = database.loc[:,(slice(None),result_type)]
        self.df.columns = self.df.columns.droplevel(1)
        self.index_name = index_col
        self.index = database.loc[:,(slice(None),index_col)]
        self.index.columns = self.index.columns.droplevel(1)

    def __repr__(self) -> str:
        return f'<HydTableTimeSeries: {self.index_name}-{self.result_type}>'
