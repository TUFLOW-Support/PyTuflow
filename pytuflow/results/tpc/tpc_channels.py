import pandas as pd

from .tpc_time_series_result_item import TPCResultItem
from ..abc.channels import Channels


class TPCChannels(TPCResultItem, Channels):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<TPC Channels: {self.fpath.stem}>'
        return '<TPC Channels>'

    def load(self) -> None:
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
