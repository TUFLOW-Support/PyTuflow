from typing import TYPE_CHECKING

import pandas as pd

from .fv_bc_tide_time_series import FVBCTideTimeSeries
from ..abc.time_series_result_item import TimeSeriesResultItem

if TYPE_CHECKING:
    from .fv_bc_tide_provider import FVBCTideProvider


RESULT_SHORT_NAME = {'h': 'water level'}


class FVBCTideNodes(TimeSeriesResultItem):
    """Class for holding FV BC Tide Node data."""

    def __init__(self, provider: 'FVBCTideProvider') -> None:
        """
        Parameters
        ----------
        provider : FVBCTideProvider
            FV BC Tide provider object.
        """
        #: FVBCTideProvider: FV BC Tide provider object.
        self.provider = provider
        super().__init__(provider.nc.path)
        self.name = 'Node'
        self.domain = '2d'
        self.domain_2 = 'node'

    def load(self, *args, **kwargs) -> None:
        # docstring inherited
        self.load_time_series()
        self.df = pd.DataFrame(index=self.time_series['Water Level'].df.columns.to_list())

    def load_time_series(self) -> None:
        # docstring inherited
        self.time_series['Water Level'] = FVBCTideTimeSeries(self.provider)

    def conv_result_type_name(self, result_type: str) -> str:
        # docstring inherited
        return RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())

    def ids(self, result_type: str) -> list[str]:
        # docstring inherited
        if not result_type or result_type.lower() not in self.time_series:
            return self.time_series['Water Level'].df.columns.to_list()
        return []
