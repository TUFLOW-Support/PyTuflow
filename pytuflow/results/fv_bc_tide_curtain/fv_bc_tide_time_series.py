from typing import TYPE_CHECKING
import pandas as pd

from ..abc.time_series import TimeSeries

if TYPE_CHECKING:
    from .fv_bc_tide_provider import FVBCTideProvider


class FVBCTideTimeSeries(TimeSeries):
    """Class for holding FV BC Tide time series data."""

    def __init__(self, provider: 'FVBCTideProvider') -> None:
        """
        Parameters
        ----------
        provider : FVBCTideProvider
            FV BC Tide provider object.
        """
        super().__init__()
        self.provider = provider
        self.load()

    def load(self) -> None:
        """Loads the time series data."""
        self.reference_time = self.provider.reference_time

        self.df = pd.DataFrame()
        for label in self.provider.get_labels():
            df = pd.DataFrame(
                self.provider.get_time_series_data_raw(label),
                index=self.provider.get_timesteps('relative'),
                columns=[f'{label}_pt_{x}' for x in range(self.provider.number_of_points(label))]
            )
            if self.df.empty:
                self.df = df
            else:
                self.df = pd.concat([self.df, df], axis=1)
