from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from ..result_util import ResultUtil

if TYPE_CHECKING:
    pass


class TPCResultUtil(ResultUtil):
    """TPC Result Utility class for helping extract data from TPC results."""

    def extract_culvert_obvert(self, inp_df: pd.DataFrame) -> list[float]:
        # inherited docstring
        y = []
        for row in inp_df.iterrows():
            us_inv = row[1]['US Invert']
            ds_inv = row[1]['DS Invert']
            us_obv = row[1]['LBUS Obvert']
            ds_obv = row[1]['LBDS Obvert']
            if row[1]['Flags'] and row[1]['Flags'][0] in ['R', 'C'] and not np.isclose(us_inv, ds_inv):
                y.append(us_obv)
                y.append(ds_obv)
            else:
                y.append(np.nan)
                y.append(np.nan)
        return y

    def extract_pit_levels(self, inp_df: pd.DataFrame) -> list[float]:
        # inherited docstring
        y = []
        for i, row in enumerate(inp_df.iterrows()):
            pits = self.channels.connected_pit_channels(row[1]['US Node'])
            if pits:
                y.append(self.channels.df.loc[pits[0], 'LBUS Obvert'])
            else:
                y.append(np.nan)
            if i + 1 == inp_df.shape[0]:
                pits = self.channels.connected_pit_channels(row[1]['DS Node'])
                if pits:
                    y.append(self.channels.df.loc[pits[0], 'LBUS Obvert'])
                else:
                    y.append(np.nan)
            else:
                y.append(np.nan)
        return y
