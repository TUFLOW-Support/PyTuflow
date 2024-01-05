from .node_csv_parser import parse_node_csv
from ..abc.tpc_abc import TPCResultItem


class TPCNodes(TPCResultItem):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Nodes: {self.fpath.stem}>'
        return '<TPC Nodes>'

    def load(self) -> None:
        try:
            self._df = parse_node_csv(self.fpath)
        except Exception as e:
            raise f'Error loading TPC 1d_Nodes.csv file: {e}'
