import typing
from collections import OrderedDict

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd
import numpy as np

from .mat_db_entry import MatDBEntry
from .drivers.xstf import TuflowCrossSection
from .drivers.fm_unit_handler import Handler


class XSDBEntry(MatDBEntry):
    SOURCE_INDEX = 1

    def cross_section(self) -> pd.DataFrame:
        attrs = self.line.split(self.string)
        d = OrderedDict({
            'Source': attrs[1],
            'Type': attrs[2],
            'Flags': attrs[3] if attrs[3] not in [None, 'None', 'nan'] and not (isinstance(attrs[3], float) and np.isnan(attrs[3])) else '',
            'Column_1': attrs[4] if attrs[4] not in [None, 'None', 'nan'] and not (isinstance(attrs[4], float) and np.isnan(attrs[4])) else '',
            'Column_2': attrs[5] if attrs[5] not in [None, 'None', 'nan'] and not (isinstance(attrs[5], float) and np.isnan(attrs[5])) else '',
            'Column_3': attrs[6] if attrs[6] not in [None, 'None', 'nan'] and not (isinstance(attrs[6], float) and np.isnan(attrs[6])) else '',
            'Column_4': attrs[7] if attrs[7] not in [None, 'None', 'nan'] and not (isinstance(attrs[7], float) and np.isnan(attrs[7])) else '',
            'Column_5': attrs[8] if attrs[8] not in [None, 'None', 'nan'] and not (isinstance(attrs[8], float) and np.isnan(attrs[8])) else '',
            'Column_6': attrs[9] if attrs[9] not in [None, 'None', 'nan'] and not (isinstance(attrs[9], float) and np.isnan(attrs[9])) else '',
        })
        xs = TuflowCrossSection(self.parent.fpath.parent, d)
        xs.load()
        if xs.col1:
            index = [x for x in xs.df.columns if x.lower() == xs.col1.lower()]
        else:
            index = xs.df.columns[0]
        return xs.df.set_index(index)


class FMXSDBEntry:

    def __init__(self, index: str | typing.Hashable, unit: Handler):
        self._index = index
        self.unit = unit

    def __repr__(self):
        return f'<{self.__class__.__name__} index={self._index} values={self.unit}>'

    def cross_section(self) -> pd.DataFrame:
        return self.unit.df
