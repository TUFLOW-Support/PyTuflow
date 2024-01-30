from collections import OrderedDict

import numpy as np
import pandas as pd

from ..abc.channels import Channels
from .fm_time_series_result_item import FMResultItem
from .dat import available_units


class FMChannels(FMResultItem, Channels):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<FM Channels: {self.fpath.stem}>'
        return '<FM Channels>'

    def load(self) -> None:
        d = OrderedDict({'Channel': [], 'Type': [], 'Flags': [], 'Length': [], 'US Node': [], 'DS Node': [],
                         'US Invert': [], 'DS Invert': [], 'LBUS Obvert': [], 'RBUS Obvert': [], 'LBDS Obvert': [],
                         'RBDS Obvert': []})
        for id_ in self._ids:
            ups_node_uid = self.gxy.link_df.loc[id_, 'ups_node']
            dns_node_uid = self.gxy.link_df.loc[id_, 'dns_node']
            ups_node_id = self.gxy.id(ups_node_uid, available_units)
            dns_node_id = self.gxy.id(dns_node_uid, available_units)
            if not ups_node_id or not dns_node_id:
                continue
            d['Channel'].append(id_)
            d['US Node'].append(ups_node_id)
            d['DS Node'].append(dns_node_id)
            if self.dat and self.dat.unit(ups_node_id):
                unit = self.dat.unit(ups_node_id)
                d['US Invert'].append(unit.ds_invert(self.dat, self.gxy))
                d['Length'].append(unit.dx)
                d['Type'].append(unit.type)
            else:
                d['US Invert'].append(np.nan)
                d['Length'].append(np.nan)
                d['Type'].append('FM Unit')
            if self.dat and self.dat.unit(dns_node_id):
                unit = self.dat.unit(dns_node_id)
                d['DS Invert'].append(unit.us_invert(self.dat, self.gxy))
            else:
                d['DS Invert'].append(np.nan)
            d['Flags'].append('')
            d['LBUS Obvert'].append(np.nan)
            d['RBUS Obvert'].append(np.nan)
            d['LBDS Obvert'].append(np.nan)
            d['RBDS Obvert'].append(np.nan)
        self.df = pd.DataFrame(d)
        self.df.set_index('Channel', inplace=True)
