import numpy as np
import pandas as pd

from .hyd_tables_time_series import HydTableTimeSeries
from ..abc.time_series_result_item import TimeSeriesResultItem
from pytuflow.util.misc_tools import flatten


class HydTableResultItem(TimeSeriesResultItem):

    def _expand_index_col(self,
                          df: pd.DataFrame,
                          result_type: str,
                          id: list[str],
                          levels: list[str]) -> pd.DataFrame:
        index_name = self.time_series[result_type].index_name
        ind_df = self.time_series[result_type].index[id].rename(columns={x: f'{x}::index' for x in id})
        df = pd.concat([ind_df, df], axis=1)
        df = df[flatten([[f'{x}::index', x] for x in id])]  # correct column order
        index_alias = [(self.name, result_type, x, 'Index', index_name) for x in id]
        col_alias = [(self.name, result_type, x, 'Value', '') for x in id]
        df.columns = pd.MultiIndex.from_tuples(flatten((zip(index_alias, col_alias))), names=levels)
        return df

    def _in_col_names(self, name: str, col_names: list[str]) -> str:
        """Correct for "K" result type which finds a column called "K (n=1.000)" or similar."""
        if name and name[0] == 'K':
            cols = [x for x in col_names if x.startswith('K')]
            if cols:
                name = cols[0]
        if name in col_names:
            return name

    def _load_time_series(self, dfs: list[pd.DataFrame], col_names: list[str], index_col: str) -> None:
        df = pd.concat(dfs, axis=1)
        multi_col_names = [(x, y) for x in self.database.keys() for y in col_names]
        df.columns = pd.MultiIndex.from_tuples(multi_col_names)
        for res_type in self._result_types:
            res_type = self._in_col_names(res_type, col_names)
            if res_type and res_type != index_col:
                time_series = HydTableTimeSeries(res_type, df, index_col)
                self.time_series[res_type] = time_series
