from typing import TextIO

import numpy as np
import pandas as pd

from ..abc.channels import Channels
from ..types import PathLike


class HydTableChannels(Channels):

    def __init__(self, fpath: PathLike = None) -> None:
        super().__init__(fpath)
        self.name = 'Channel'
        self.domain = '1d'
        self.domain_2 = 'channel'
        self.database = {}
        self.df = pd.DataFrame([], columns=['Type', 'Flags', 'Length', 'US Node', 'DS Node', 'US Invert', 'DS Invert',
                                                 'LBUS Obvert', 'RBUS Obvert', 'LBDS Obvert', 'RBDS Obvert',
                                                 'Cross Section 1', 'Cross Section 2'])
        self.df.index.name = 'Channel'
        self.database = {}

    def __repr__(self) -> str:
        if hasattr(self, 'fpath') and self.fpath is not None:
            return f'<HydTableChannels: {self.fpath.stem}>'
        return '<HydTableChannels>'

    def load(self) -> None:
        pass

    def load_time_series(self, *args, **kwargs):
        pass

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

    @staticmethod
    def conv_result_type_name(result_type: str) -> str:
        return result_type
