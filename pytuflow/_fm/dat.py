from collections import OrderedDict
from pathlib import Path

import pandas as pd

from . import DAT, Handler


class FMDAT(DAT):

    def __init__(self, fpath: Path | str):
        self._loaded = False
        self.df = pd.DataFrame()
        super().__init__(fpath)

    def load(self, *args, **kwargs):
        if not self._loaded:
            super().load()
            self._loaded = True
            d = OrderedDict({
                'ID': [],
                'Name': [],
                'Type': []
            })
            for xs in self.find_units('River'):
                d['ID'].append(xs.uid)
                d['Name'].append(xs.id)
                d['Type'].append(xs.type)
                xs.df = xs.xs
                xs.name = xs.id
            self.df = pd.DataFrame(d)
            self.df.set_index('ID', inplace=True)
        return self.df

    def cross_sections(self) -> list[Handler]:
        return self.find_units('River')
