from ..po.po_tpc import TPCPO


class TPCRL(TPCPO):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Rl: {self.fpath.stem}>'
        return '<TPC RL>'
