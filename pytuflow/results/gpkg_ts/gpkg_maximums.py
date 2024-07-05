from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING
from pytuflow.pytuflow_types import PathLike

import numpy as np
import pandas as pd

from ..abc.maximums import Maximums
from .gpkg_ts_base import GPKGBase

if TYPE_CHECKING:
    from .gpkg_time_series_result_item import GPKGResultItem


class GPKGMaximums(GPKGBase, Maximums):
    """Class for handling GeoPackage time series Maximums."""

    def __init__(self, fpath: PathLike, layer_name: str, result_item: 'GPKGResultItem') -> None:
        """
        Parameters
        ----------
        fpath : PathLike
            Path to the GeoPackage file.
        layer_name : str
            Name of the layer in the GeoPackage.
        result_item : GPKGResultItem
            Result item to get maximums from.
        """
        super(GPKGMaximums, self).__init__(fpath)
        self.fpath = Path(fpath)
        self.result_items = OrderedDict({})
        self._df_result_items = []
        if layer_name:
            self.append(layer_name, result_item)

        # properties
        self._df = None

    def append(self, layer_name: str, result_item: 'GPKGResultItem') -> None:
        # docstring inherited
        self.result_items[layer_name] = result_item

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None or sorted(self.result_items.keys()) != sorted(self._df_result_items):
            res_items = OrderedDict({k: v for k, v in self.result_items.items() if k not in self._df_result_items})
            try:
                self._open_db()
                for lyr, res_item in res_items.items():
                    RESULT_TYPES = res_item.result_types(None)

                    # maximums
                    columns = [f'{x} Max' for x in RESULT_TYPES]
                    max_res_types = [f'MAX("{x}") AS "{x} Max"' for x in RESULT_TYPES]
                    max_res_types = ', '.join(max_res_types)
                    self._cur.execute(f'SELECT ID, {max_res_types} FROM "{lyr}" GROUP BY ID;')
                    ret = self._cur.fetchall()
                    if ret:
                        d = {'ID': []}
                        d.update({x: [] for x in columns})
                        for row in ret:
                            d['ID'].append(row[0])
                            for i, col in enumerate(columns):
                                try:
                                    d[col].append(float(row[i + 1]))
                                except (ValueError, TypeError):
                                    d[col].append(np.nan)
                        df = pd.DataFrame(d)
                    else:
                        df = pd.DataFrame([], columns=['ID'] + columns)
                    df.set_index('ID', inplace=True)
                    self._df_result_items.append(lyr)
                    if self._df is None:
                        self._df = df
                    else:
                        self._df = pd.concat([self._df, df], join='outer')

                    # time of max
                    columns = [f'{x} TMax' for x in RESULT_TYPES]
                    d = OrderedDict({"ID": res_item.ids(None)})
                    d.update(OrderedDict({x: [] for x in columns}))
                    for id_ in res_item.ids(None):
                        for result_type in RESULT_TYPES:
                            self._cur.execute(
                                f'SELECT Time_relative FROM "{lyr}" WHERE ID = "{id_}" ORDER BY "{result_type}" DESC LIMIT 1;'
                            )
                            if ret:
                                ret = self._cur.fetchone()
                                try:
                                    d[f'{result_type} TMax'].append(float(ret[0]))
                                except (ValueError, TypeError):
                                    d[f'{result_type} TMax'].append(np.nan)
                            else:
                                d[f'{result_type} TMax'].append(np.nan)
                    df = pd.DataFrame(d)
                    df.set_index('ID', inplace=True)
                    self._df = pd.concat([self._df, df], axis=1)
            except Exception as e:
                raise Exception(f'Error getting maximums: {e}')
            finally:
                self._close_db()

        return self._df

    @df.setter
    def df(self, value: pd.DataFrame) -> None:
        return
