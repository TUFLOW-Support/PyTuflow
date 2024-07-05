from collections import OrderedDict

import numpy as np
import pandas as pd

from pytuflow.fm import GXY, DAT
from ..abc.channels import Channels
from .fm_time_series_result_item import FMResultItem
from pytuflow.pytuflow_types import PathLike


class FMChannels(FMResultItem, Channels):
    """Flood Modeller Channels class."""

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<FM Channels: {self.fpath.stem}>'
        return '<FM Channels>'

    def load(self) -> None:
        # docstring inherited
        d = OrderedDict({'Channel': [], 'Type': [], 'Flags': [], 'Length': [], 'US Node': [], 'DS Node': [],
                         'US Invert': [], 'DS Invert': [], 'LBUS Obvert': [], 'RBUS Obvert': [], 'LBDS Obvert': [],
                         'RBDS Obvert': []})
        if self.dat:
            for link in self.dat.links:
                d['Channel'].append(link.id)
                d['Type'].append(f'{link.ups_unit.type}_{link.ups_unit.sub_type}'.strip('_'))
                d['Flags'].append('')
                length = 0.
                if hasattr(link.ups_unit, 'dx') and not np.isnan(link.ups_unit.dx):
                    length = link.ups_unit.dx
                d['Length'].append(length)
                d['US Node'].append(link.ups_unit.uid)
                d['DS Node'].append(link.dns_unit.uid)
                d['US Invert'].append(link.ups_unit.bed_level)
                d['DS Invert'].append(link.dns_unit.bed_level)
                d['LBUS Obvert'].append(np.nan)
                d['RBUS Obvert'].append(np.nan)
                d['LBDS Obvert'].append(np.nan)
                d['RBDS Obvert'].append(np.nan)
        elif self.gxy:
            nodes = {node.uid: node for node in self.gxy._nodes}
            for index, row in self.gxy.link_df.iterrows():
                node = nodes[row['ups_node']]
                d['Channel'].append(index)
                if node:
                    d['Type'].append(node.type)
                else:
                    d['Type'].append('_'.join(row['ups_node'].split('_', 2)[:2]).strip('_'))
                d['Flags'].append('')
                d['Length'].append(0)
                d['US Node'].append(row['ups_node'])
                d['DS Node'].append(row['dns_node'])
                d['US Invert'].append(np.nan)
                d['DS Invert'].append(np.nan)
                d['LBUS Obvert'].append(np.nan)
                d['RBUS Obvert'].append(np.nan)
                d['LBDS Obvert'].append(np.nan)
                d['RBDS Obvert'].append(np.nan)

        self.df = pd.DataFrame(d)
        self.df.set_index('Channel', inplace=True)
        self._ids = self.df.index.tolist()
