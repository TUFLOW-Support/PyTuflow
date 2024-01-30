from ..tpc.tpc_nodes import TPCNodes
from .info_time_series_result_item import InfoResultItem


class InfoNodes(TPCNodes, InfoResultItem):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<Info Nodes: {self.fpath.stem}>'
        return '<Info Nodes>'

    def long_plot_result_types(self) -> list[str]:
        result_types = ['Bed Level']
        if self.maximums is not None and self.maximums.df is not None:
            maxes = [x for x in self.maximums.df.columns if 'TMax' not in x]
            result_types.extend(maxes)
        return result_types
