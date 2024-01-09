from .time_series_result_item import TimeSeriesResultItem


class Channels(TimeSeriesResultItem):

    def ds_node(self, id: str) -> str:
        return self.df.loc[id, 'DS Node']

    def us_node(self, id: str) -> str:
        return self.df.loc[id, 'US Node']

    def downstream_channels(self, id: str) -> list[str]:
        nd = self.ds_node(id)
        return [x for x in self.ids(None) if self.us_node(x) == nd]

    def upstream_channels(self, id: str) -> list[str]:
        nd = self.us_node(id)
        return [x for x in self.ids(None) if self.ds_node(x) == nd]
