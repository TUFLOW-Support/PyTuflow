from ..abc.nodes import Nodes


class FMNodes(Nodes):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<FM Nodes: {self.fpath.stem}>'
        return '<FM Nodes>'
