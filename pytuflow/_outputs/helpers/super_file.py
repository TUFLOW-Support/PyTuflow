from pathlib import Path

import pandas as pd

from pytuflow._pytuflow_types import PathLike


class SuperFile:

    def __init__(self, fpath: PathLike):
        self.fpath = Path(fpath)
        self._data = None

    def __getitem__(self, item):
        self.load_data()
        return self._data.loc[item].value

    def load_data(self):
        if self._data is not None:
            return
        self._data = pd.read_csv(self.fpath, sep=' ', names=['key', 'value'], index_col='key',
                                 converters={'value': lambda x: x.strip(' "')})
