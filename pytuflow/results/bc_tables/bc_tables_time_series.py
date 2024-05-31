import pandas as pd

from .boundary_type import BoundaryType
from ..abc.time_series import TimeSeries
from pytuflow.types import TimeLike


class BCTablesTimeSeries(TimeSeries):
    """Class to handle individual BCTable result plottable data."""

    def __init__(self) -> None:
        super().__init__()
        self.df = pd.DataFrame()
        self.df_index = pd.DataFrame()

    def __repr__(self) -> str:
        return '<BCTablesTimeSeries>'

    def append(self, bndry: BoundaryType) -> None:
        # docstring inherited
        if bndry.valid:
            df = pd.DataFrame(bndry.values[:,1], columns=[bndry.id])
            df_index = pd.DataFrame(bndry.values[:,0], columns=[bndry.id])
            self.df = pd.concat([self.df, df], axis=1)
            self.df_index = pd.concat([self.df_index, df_index], axis=1)

    def timesteps(self, dtype: str) -> list[TimeLike]:
        # docstring inherited
        pass