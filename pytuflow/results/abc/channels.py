from pathlib import Path
from typing import Union

from .time_series_result_item import TimeSeriesResultItem


class Channels(TimeSeriesResultItem):
    """Abstract base class for channel result item."""

    def __init__(self, fpath: Union[str, Path], *args, **kwargs) -> None:
        super().__init__(fpath)
        self.name = 'Channel'
        self.domain = '1d'
        self.domain_2 = 'channel'

    def ds_node(self, id: str) -> str:
        return self.df.loc[id, 'DS Node']

    def us_node(self, id: str) -> str:
        return self.df.loc[id, 'US Node']

    def downstream_channels(self, id: str) -> list[str]:
        nd = self.ds_node(id)
        return self.df[self.df['US Node'] == nd].index.tolist()

    def upstream_channels(self, id: str) -> list[str]:
        nd = self.us_node(id)
        return self.df[self.df['DS Node'] == nd].index.tolist()
