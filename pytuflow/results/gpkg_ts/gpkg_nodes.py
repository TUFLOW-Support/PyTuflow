from collections import OrderedDict

import numpy as np
import pandas as pd

from .gpkg_time_series_result_item import GPKGResultItem
from ..abc.nodes import Nodes


RESULT_SHORT_NAME = {'h': 'water level', 'q': 'total inflow', 'v': 'velocity', 'e': 'energy', 'vol': 'storage volume',
                     'mb': 'mass balance error', 'qa': 'flow area', 'd': 'depth', 'flow': 'total inflow',
                     'total q': 'total inflow', 'total flow': 'total inflow'}


class GPKGNodes(GPKGResultItem, Nodes):
    """Class for handling GeoPackage time series node results."""

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<GPKG TS Node: {self.fpath.stem}>'
        return '<GPKG TS Node>'

    def load(self) -> None:
        # docstring inherited
        pass

    def long_plot_result_types(self) -> list[str]:
        # docstring inherited
        result_types = ['Bed Level', 'Pit Level', 'Pipes'] + self.result_types(None)
        if self.maximums is not None and self.maximums.df is not None:
            maxes = [x for x in self.maximums.df.columns if 'TMax' not in x]
            result_types.extend(maxes)
        return result_types

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            try:
                COLUMNS = ['Node', 'Bed Level', 'Top Level', 'Inlet Level']
                TYPE_MAP = [str, float, float, float]
                self._open_db()
                self._cur.execute(
                    'SELECT '
                      'ID as Node, '
                      'Invert_elevation as "Bed Level", '
                      'Top_elevation as "Top Level", '
                      'Inlet_elevation as "Inlet Level" '
                    'FROM Points_P;'
                )
                ret = self._cur.fetchall()
                if ret:
                    d = OrderedDict({x: [] for x in COLUMNS})
                    for row in ret:
                        for i, col in enumerate(COLUMNS):
                            try:
                                d[col].append(TYPE_MAP[i](row[i]))
                            except (TypeError, ValueError):
                                d[col].append(np.nan)
                    self._df = pd.DataFrame(d)
                else:
                    self._df = pd.DataFrame([], columns=COLUMNS)
                self._df.set_index('Node', inplace=True)
            except Exception as e:
                raise Exception(f'Error getting nodes: {e}')
            finally:
                self._close_db()
        return self._df

    @df.setter
    def df(self, df: pd.DataFrame):
        return

    def conv_result_type_name(self, result_type: str) -> str:
        # docstring inherited
        return RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())
