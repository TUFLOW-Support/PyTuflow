from typing import TextIO

import numpy as np
import pandas as pd

from .hyd_tables_result_item import HydTableResultItem
from ..abc.channels import Channels
from ..types import PathLike


class HydTableChannels(HydTableResultItem, Channels):

    def __init__(self, fpath: PathLike = None) -> None:
        super(HydTableChannels, self).__init__(fpath)
        self.name = 'Channel'
        self.domain = '1d'
        self.domain_2 = 'channel'
        self.database = {}
        self.df = pd.DataFrame([], columns=['Type', 'Flags', 'Length', 'US Node', 'DS Node', 'US Invert', 'DS Invert',
                                                 'LBUS Obvert', 'RBUS Obvert', 'LBDS Obvert', 'RBDS Obvert',
                                                 'Cross Section 1', 'Cross Section 2'])
        self.df.index.name = 'Channel'
        self.database = {}
        self._result_types = ['Depth', 'Storage Width', 'Flow Width', 'Area', 'P', 'Radius',
                              'Vert Res Factor', 'K']

    def __repr__(self) -> str:
        if hasattr(self, 'fpath') and self.fpath is not None:
            return f'<HydTableChannels: {self.fpath.stem}>'
        return '<HydTableChannels>'

    def load(self) -> None:
        pass

    def load_time_series(self) -> None:
        """
        Unlike abstract method which loads in individual time series results,
        use this method to load all time series data at once.
        """
        if not self.database:
            return

        col_names = list(self.database.values())[0].columns
        dfs = list(self.database.values())
        self._load_time_series(dfs, col_names, col_names[0])

    def append(self, fo: TextIO, channel_id: str, xs1: str, xs2: str) -> None:
        df = pd.read_csv(fo, index_col=False)
        self.database[channel_id] = df
        df = pd.DataFrame({
            'Type': None,
            'Flags': None,
            'Length': np.nan,
            'US Node': None,
            'DS Node': None,
            'US Invert': np.nan,
            'DS Invert': np.nan,
            'LBUS Obvert': np.nan,
            'RBUS Obvert': np.nan,
            'LBDS Obvert': np.nan,
            'RBDS Obvert': np.nan,
            'Cross Section 1': xs1,
            'Cross Section 2': xs2
        }, index=[channel_id])
        self.df = pd.concat([self.df, df], axis=0)
        self.df.index.name = 'Channel'

    def conv_result_type_name(self, result_type: str) -> str:
        if self.database:
            col_names = list(self.database.values())[0].columns
            if self._in_col_names(result_type, col_names):
                return self._in_col_names(result_type, col_names)
        return result_type
