from datetime import datetime
from collections import OrderedDict

import numpy as np
import pandas as pd

from .fm_time_series_result_item import FMResultItem
from .dat import available_units
from ..abc.nodes import Nodes


class FMNodes(FMResultItem, Nodes):

    def __repr__(self) -> str:
        if hasattr(self, 'fpath'):
            return f'<FM Nodes: {self.fpath.stem}>'
        return '<FM Nodes>'

    def load(self) -> None:
        d = OrderedDict({'Unique ID': [], 'Node': [], 'Type': [], 'Bed Level': [], 'Length': [], 'nChannels': [], 'Ups Channels': [], 'Dns Channels': [], 'Ups Nodes': [], 'Dns Nodes': []})
        if self.dat:
            for unit in self.dat.units():
                d['Unique ID'].append(unit.uid)
                d['Node'].append(unit.id)
                d['Type'].append(f'{unit.keyword}_{unit.sub_name}'.strip('_'))
                d['Length'].append(unit.dx if hasattr(unit, 'dx') else 0.)
                d['nChannels'].append(len(unit.ups_units) + len(unit.dns_units))
                d['Ups Channels'].append(unit.ups_link_ids)
                d['Dns Channels'].append(unit.dns_link_ids)
                d['Bed Level'].append(unit.bed_level)
                d['Ups Nodes'].append([x.uid for x in unit.ups_units if x.valid])
                d['Dns Nodes'].append([x.uid for x in unit.dns_units if x.valid])
        elif self.gxy:
            for node in self.gxy.nodes():
                d['Unique ID'].append(node.uid)
                d['Node'].append(node.id)
                d['Type'].append(node.type)
                d['Length'].append(0.)
                ups_links = self.gxy.link_df[self.gxy.link_df['dns_node'] == node.uid]
                dns_links = self.gxy.link_df[self.gxy.link_df['ups_node'] == node.uid]
                d['nChannels'].append(len(ups_links) + len(dns_links))
                d['Ups Channels'].append(ups_links.index.tolist())
                d['Dns Channels'].append(dns_links.index.tolist())
                d['Bed Level'].append(np.nan)
                d['Ups Nodes'].append(ups_links['ups_node'].tolist())
                d['Dns Nodes'].append(dns_links['dns_node'].tolist())
        else:
            for id_ in self._ids:
                d['Unique ID'].append(id_)
                d['Node'].append(id_)
                d['Type'].append('Unknown')
                d['Length'].append(0.)
                d['nChannels'].append(0)
                d['Ups Channels'].append([])
                d['Dns Channels'].append([])
                d['Bed Level'].append(np.nan)
                d['Ups Nodes'].append([])
                d['Dns Nodes'].append([])

        self.df = pd.DataFrame(d)
        self.df.set_index('Node', inplace=True)

    def long_plot_result_types(self) -> list[str]:
        result_types = []
        if not self.gxy:
            return []
        if self.dat:
            result_types.append('Bed Level')
        if 'Stage' in self.result_types(None):
            result_types.append('Stage')
            if self.maximums is not None and self.maximums.df is not None:
                result_types.append('Stage Max')
        return result_types
