from datetime import datetime
from pathlib import Path
from typing import Union

from .fm_maximums import FMMaximums
from pytuflow.types import PathLike

import pandas as pd

from .fm_time_series import FMTimeSeries
from ..abc.time_series_result_item import TimeSeriesResultItem
from pytuflow.fm import DAT, GXY


RESULT_SHORT_NAME = {'h': 'stage', 'water level': 'stage', 'q': 'flow', 'v': 'velocity', 'vel': 'velocity',
                     'f': 'froude', 'fr': 'froude', 's': 'state', 'm': 'mode'}


class FMResultItem(TimeSeriesResultItem):
    """A class for FM result items."""

    def __init__(self, fpath: PathLike, id_list: list[str], gxy: GXY, dat: DAT, **kwargs) -> None:
        """
        Parameters
        ----------
        fpath: Union[PathLike, list[PathLike]]
            Flood modeller result file path(s). The file paths can be CSVs exported via the Flood Modeller GUI,
            the python flood modeller-api, or the raw ZZN files.
        gxy: PathLike
            Path to the GXY file.
        dat: PathLike
            Path to the DAT file.
        """
        self._ids = id_list
        self.gxy = gxy
        self.dat = dat
        self.maximums = FMMaximums()
        super().__init__(fpath)

    def count(self) -> int:
        # docstring inherited
        return len(self._ids)

    def ids(self, result_type: Union[str, None]) -> list[str]:
        # docstring inherited
        return self._ids

    def load_time_series(self, name: str, df: pd.DataFrame, reference_time: datetime, timesteps: list[float]) -> None:
        """Load a time series result.
        A TimeSeries class holds information for all temporal results for a given result type (e.g. 'flow').

        Parameters
        ----------
        name : str
            Name of the time series result e.g. 'Flow', 'Water Level'.
        df : pd.DataFrame
            DataFrame containing the time series result data.
        reference_time : datetime
            Reference time for the time series data.
        timesteps : list[float]
            List of timesteps for the time series data.

        """
        if name not in self.time_series or self.time_series[name].df.empty:
            self.time_series[name] = FMTimeSeries(name, df, reference_time, timesteps)
            self.maximums.append(name, self.time_series[name].df)

    def conv_result_type_name(self, result_type: str) -> str:
        # docstring inherited
        return RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())
