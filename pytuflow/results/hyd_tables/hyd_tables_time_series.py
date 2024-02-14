import pandas as pd

from ..abc.time_series import TimeSeries


class HydTableTimeSeries(TimeSeries):

    def __init__(self, result_type: str, database: pd.DataFrame, index_col: str) -> None:
        super().__init__()
        self.result_type = result_type
        self.df = database.loc[:,(slice(None),result_type)]
        self.df.columns = self.df.columns.droplevel(1)
        self.index_name = index_col
        self.index = database.loc[:,(slice(None),index_col)]
        self.index.columns = self.index.columns.droplevel(1)

    def __repr__(self) -> str:
        return f'<HydTableTimeSeries: {self.index_name}-{self.result_type}>'
