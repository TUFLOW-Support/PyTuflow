import re
from collections import OrderedDict

import numpy as np
import pandas as pd

from .gpkg_time_series_result_item import GPKGResultItem
from ..abc.channels import Channels


RESULT_SHORT_NAME = {'h': 'water level', 'q': 'flow', 'v': 'velocity', 'e': 'energy', 'vol': 'channel volume',
                     'channel vol': 'channel volume', 'chan vol': 'channel volume',
                     'qa': 'flow area', 'd': 'channel depth',
                     'total q': 'total flow'}


class GPKGChannels(GPKGResultItem, Channels):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<GPKG TS Channel: {self.fpath.stem}>'
        return '<GPKG TS Channel>'

    def load(self) -> None:
        pass

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            try:
                COLUMNS = ['Channel', 'Type', 'Flags', 'Length', 'US Node', 'DS Node', 'US Invert', 'DS Invert',
                           'LBUS Obvert', 'RBUS Obvert', 'LBDS Obvert', 'RBDS Obvert']
                TYPE_MAP = [str, str, str, float, str, str, float, float, float, float, float, float]
                self._open_db()
                self._cur.execute(
                    'SELECT '
                      'l.ID as Channel, '
                      'l.Type, '
                      'l.Shape as Flags, '
                      'l.Length, '
                      'p1.ID as "US Node", '
                      'p2.ID as "DS Node", '
                      'l.US_Invert as "US Invert", '
                      'l.DS_Invert as "DS Invert", '
                      'l.US_Obvert as "LBUS Obvert", '
                      'l.US_Obvert as "RBUS Obvert", '
                      'l.DS_Obvert as "LBDS Obvert", '
                      'l.DS_Obvert as "RBDS Obvert" '
                    'FROM Lines_L AS l '
                    'LEFT JOIN Points_P as p1 ON l.US_Node = p1.fid '
                    'LEFT JOIN Points_P as p2 ON l.DS_Node = p2.fid;'
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
                self._df.set_index('Channel', inplace=True)
            except Exception as e:
                raise Exception(f'Error loading GPKG channel data: {e}')
            finally:
                self._close_db()
        return self._df

    @df.setter
    def df(self, value: pd.DataFrame) -> None:
        return

    @staticmethod
    def conv_result_type_name(result_type: str) -> str:
        return RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())
