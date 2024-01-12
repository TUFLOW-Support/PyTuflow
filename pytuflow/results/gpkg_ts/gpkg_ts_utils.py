import numpy as np
import pandas as pd

from ..result_util import ResultUtil


class GPKG_TSResultUtil(ResultUtil):

    def extract_culvert_obvert(self, inp_df: pd.DataFrame) -> list[float]:
        y = []
        for row in inp_df.iterrows():
            y.append(row[1]['LBUS Obvert'])
            y.append(row[1]['LBDS Obvert'])
        return y

    def extract_pit_levels(self, inp_df: pd.DataFrame) -> list[float]:
        y = []
        for i, row in enumerate(inp_df.iterrows()):
            us_node = row[1]['US Node']
            y.append(self.nodes.df.loc[us_node, 'Inlet Level'])
            if i + 1 == inp_df.shape[0]:
                ds_node = row[1]['DS Node']
                y.append(self.nodes.df.loc[ds_node, 'Inlet Level'])
            else:
                y.append(np.nan)
        return y
