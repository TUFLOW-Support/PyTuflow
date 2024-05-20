from ..tpc.tpc_nodes import TPCNodes
from .info_time_series_result_item import InfoResultItem


class InfoNodes(TPCNodes, InfoResultItem):
    """Info Nodes class."""

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<Info Nodes: {self.fpath.stem}>'
        return '<Info Nodes>'
