import pandas as pd

from ..abc.maximums import Maximums
from ..abc.time_series_result_item import TimeSeriesResultItem


class TPCMaximumsPO(Maximums):

    def __init__(self, result_item: TimeSeriesResultItem) -> None:
        self._df = None
        self._result_item = result_item
        super().__init__()

    def __repr__(self) -> str:
        return f'<TPC Maximums PO>'

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            df = pd.DataFrame()
            for rt, ts in self._result_item.time_series.items():
                df_ = ts.df.max().to_frame().rename(columns={0: f'{rt} Max'})
                mask = (ts.df == df_.iloc[0,0]).iloc[:,0].tolist()
                tmax = ts.df[mask].index[0]
                df_[f'{rt} TMax'] = [tmax]
                self._df = pd.concat([self._df, df_], axis=1)
        return self._df

    @df.setter
    def df(self, value: pd.DataFrame) -> None:
        return
