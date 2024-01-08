from .node_csv_parser import parse_node_csv
from .tpc_time_series_result_item import TPCResultItem
from ..abc.nodes import Nodes


class TPCNodes(TPCResultItem, Nodes):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Nodes: {self.fpath.stem}>'
        return '<TPC Nodes>'

    def load(self) -> None:
        try:
            self._df = parse_node_csv(self.fpath)
        except Exception as e:
            raise Exception(f'Error loading TPC 1d_Nodes.csv file: {e}')

    def long_plot_result_types(self) -> list[str]:
        return ['Bed Level', 'Pit Level', 'Pipes'] + self.result_types(None)
