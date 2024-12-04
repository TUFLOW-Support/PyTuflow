from abc import ABC, abstractmethod

import pandas as pd

from pytuflow.pytuflow_types import PathLike, LongPlotExtractionLocation


class ITimeSeries2D(ABC):
    """Interface class for 1D time series outputs."""

    @abstractmethod
    def __init__(self, *fpath: PathLike) -> None:
        super().__init__()
        self.po_info = pd.DataFrame(index=['id'], columns=['data_types'])
        self.rl_info = pd.DataFrame(index=['id'], columns=['data_types'])
