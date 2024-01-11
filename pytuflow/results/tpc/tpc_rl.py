from .tpc_po import TPCPO_Base


class TPCRL(TPCPO_Base):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Rl: {self.fpath.stem}>'
        return '<TPC RL>'


