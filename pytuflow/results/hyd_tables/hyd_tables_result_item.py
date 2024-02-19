import numpy as np
import pandas as pd

from .hyd_tables_time_series import HydTableTimeSeries
from ..abc.time_series_result_item import TimeSeriesResultItem


class HydTableResultItem(TimeSeriesResultItem):

    def get_time_series(self, id: list[str], result_type: list[str]) -> pd.DataFrame:
        df = super().get_time_series(id, result_type)

        # result types are not guaranteed to have the same index
        index, same_index = None, True
        column_names_in_order = []
        for i, rt in enumerate(result_type):
            if rt in self.time_series:
                rt_column_names = [f'{rt}::{x}' for x in id]
                alias_ids = [f'{self.time_series[rt].index_name}::{x}::Index::{rt}' for x in id]
                column_names_in_order.extend(list(zip(alias_ids, rt_column_names)))
                index_ = self.time_series[rt].index[id].rename(columns={x: y for x, y in zip(id, alias_ids)})
                alias_ids_ = []
                for id_ in alias_ids:
                    if id_ not in df.columns:
                        alias_ids_.append(id_)
                index_ = index_[alias_ids_]
                if index_.shape[1] == 1 and same_index:
                    if index is None:
                        index = index_
                    elif index.shape != index_.shape or not np.isclose(index, index_, equal_nan=True).all():
                        index = None
                        same_index = False
                else:
                    index = None
                    same_index = False
                if index is None or i == 0:
                    df = pd.concat([df, index_], axis=1)
        if index is not None and same_index:
            df.set_index(index.columns[0], inplace=True)
            df.index.name = self.time_series[rt].index_name
        else:
            column_names_in_order = sum([list(x) for x in column_names_in_order], [])
            df = df[column_names_in_order]

        df = df.dropna(how='all')

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
