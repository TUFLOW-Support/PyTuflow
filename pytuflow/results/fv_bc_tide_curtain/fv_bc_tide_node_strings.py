from typing import TYPE_CHECKING

import pandas as pd

from ..abc.time_series_result_item import TimeSeriesResultItem

if TYPE_CHECKING:
    from .fv_bc_tide_provider import FVBCTideProvider


RESULT_SHORT_NAME = {'h': 'water level'}


class FVBCTideNodeStrings(TimeSeriesResultItem):
    """Class for holding FV BC tide node string data."""

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
        self.name = 'Node String'
        self.domain = '2d'
        self.domain_2 = 'node_string'

    def load(self, *args, **kwargs) -> None:
        # docstring inherited
        self.df = pd.DataFrame(index=self.provider.get_labels())

    def load_time_series(self) -> None:
        # docstring inherited
        pass

    def conv_result_type_name(self, result_type: str) -> str:
        # docstring inherited
        return RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())

    def ids(self, result_type: str) -> list[str]:
        # docstring inherited
        if not result_type:
            return self.provider.get_labels()
        return []
