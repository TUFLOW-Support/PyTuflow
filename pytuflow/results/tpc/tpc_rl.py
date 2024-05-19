from .tpc_po import TPCPO_Base
from ..abc.rl import RL


class TPCRL(RL, TPCPO_Base):
    """TPC RL class."""

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Rl: {self.fpath.stem}>'
        return '<TPC RL>'


