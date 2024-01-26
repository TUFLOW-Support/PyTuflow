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
        d = OrderedDict({'Node': [], 'Bed Level': [], 'nChannels': [], 'Ups Channels': [], 'Dns Channels': []})
        for id_ in self._ids:
            if self.gxy and self.gxy.gxy_id(id_, available_units):
                gxy_id = self.gxy.gxy_id(id_, available_units)
                d['Node'].append(id_)
                ups_links = self.gxy.link_df[self.gxy.link_df['ups_node'] == gxy_id]
                dns_links = self.gxy.link_df[self.gxy.link_df['dns_node'] == gxy_id]
                d['nChannels'].append(len(ups_links) + len(dns_links))
                d['Ups Channels'].append(ups_links.index.tolist())
                d['Dns Channels'].append(dns_links.index.tolist())
            else:
                d['Node'].append(id_)
                d['nChannels'].append(0)
                d['Ups Channels'].append([])
                d['Dns Channels'].append([])

            if self.dat and self.dat.unit(id_):
                unit = self.dat.unit(id_)
                d['Bed Level'].append(unit.bed_level(self.dat, self.gxy))
            else:
                d['Bed Level'].append(np.nan)

        self.df = pd.DataFrame(d)
        self.df.set_index('Node', inplace=True)

    def load_time_series(self, name: str) -> None:
        pass
