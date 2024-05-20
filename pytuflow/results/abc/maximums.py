from abc import ABC
from collections import OrderedDict

import pandas as pd


class Maximums(ABC):
    """Abstract base class for maximums."""

    def __init__(self, *args, **kwargs):
        #: pd.DataFrame: Dataframe containing maximum and time of maximum values.
        self.df = None

    def append(self, result_type: str, df: pd.DataFrame) -> None:
        d = OrderedDict({'ID': [], f'{result_type} Max': [], f'{result_type} TMax': []})
        for id_ in df.columns:
            d['ID'].append(id_)
            d[f'{result_type} Max'].append(df[id_].max())
            d[f'{result_type} TMax'].append(df[id_].idxmax())
        df_ = pd.DataFrame(d)
        df_.set_index('ID', inplace=True)
        if self.df is None or self.df.empty:
            self.df = df_
        else:
            self.df = pd.concat([self.df, df_], axis=1)
