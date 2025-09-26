from pathlib import Path

import pandas as pd

from ..._pytuflow_types import PathLike


class SuperFile:

    def __init__(self, fpath: PathLike):
        self.fpath = Path(fpath)
        self._data = None

    def __getitem__(self, item):
        self.load_data()
        val = self._data.loc[self._data['key'] == item].value.tolist()
        return val[0] if len(val) == 1 else val

    def load_data(self):
        if self._data is not None:
            return
        self._data = pd.read_csv(self.fpath, sep=' ', names=['key', 'value'],
                                 converters={'value': lambda x: x.strip(' "')})
