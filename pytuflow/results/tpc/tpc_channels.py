import pandas as pd

from .tpc_time_series_result_item import TPCResultItem
from ..abc.channels import Channels


class TPCChannels(TPCResultItem, Channels):
    """TPC Channels class."""

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Channels: {self.fpath.stem}>'
        return '<TPC Channels>'

    def load(self) -> None:
        """Load TPC channels.csv file.

        Returns
        -------
        None
        """
        try:
            self.df = pd.read_csv(
                self.fpath,
                index_col='Channel',
                delimiter=',',
                header=0,
                na_values=['**********'],
                converters={
                    'No': int,
                    'Length': float,
                    'Form Loss': float,
                    'n or Cd': float,
                    'pSlope': float,
                    'US Invert': float,
                    'DS Invert': float,
                    'LBUS Obvert': float,
                    'RBUS Obvert': float,
                    'LBDS Obvert': float,
                    'RBDS Obvert': float,
                    'pBlockage': float,
                }
            )
        except Exception as e:
            raise Exception(f'Error loading TPC 1d_channels.csv file: {e}')

    def connected_pit_channels(self, node_id: str) -> list[str]:
        """Return connected pit channels to node with ID.

        Parameters
        ----------
        node_id : str
            Node ID.

        Returns
        -------
        list[str]
            List of connected pit channels.
        """
        return self.df[
            (self.df['DS Node'] == node_id) & (self.df['US Channel'] == '------') & (self.df['DS Channel'] == '------')
            ].index.tolist()
