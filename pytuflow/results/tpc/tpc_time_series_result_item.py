import re
from datetime import datetime
from pytuflow.pytuflow_types import PathLike

from .tpc_time_series_csv import TPCTimeSeriesCSV
from .tpc_time_series_nc import TPCTimeSeriesNC
from ..abc.time_series_result_item import TimeSeriesResultItem


RESULT_SHORT_NAME = {'h': 'water level', 'q': 'flow', 'v': 'velocity', 'vel': 'velocity', 'e': 'energy', 'vol': 'volume',
                     'mb': 'mass balance error', 'qa': 'flow area', 'nf': 'node regime', 'cf': 'channel regime',
                     'entry loss': 'entry channel losses', 'entry losses': 'entry channel losses',
                     'exit loss': 'entry channel losses', 'exit losses': 'entry channel losses',
                     'additional loss': 'entry channel losses', 'additional losses': 'entry channel losses',
                     'level': 'water level'}


class TPCResultItem(TimeSeriesResultItem):
    """Base class for TPC result items Channels, Nodes, etc."""

    def __init__(self, fpath: PathLike) -> None:
        #: Path: Path to NetCDF TS result file.
        self.nc = None
        super().__init__(fpath)

    def load_time_series(self, name: str, fpath: PathLike, reference_time: datetime, index_col=None,
                         id: str = '', loss_type: str = '') -> None:
        """Load a time series result.
        A TimeSeries class holds information for all temporal results for a given result type (e.g. 'flow').

        The time series result should be stored in self.time_series['<result type name>'] = <TimeSeries class>
        e.g. self.time_series['Flow'] = <TimeSeries class> (e.g. loaded from M04_5m_001_1d_Q.csv)

        The result type name should not be converted to lowercase or anything like that.

        Parameters
        ----------
        name : str
            Name of the time series result e.g. 'Flow', 'Water Level'.
        fpath : PathLike
            Path to the file containing the time series result data.
        reference_time : datetime
            Reference time for the time series data.
        index_col : str, optional
            Column name to use as the index for the time series data.
        id : str, optional
            ID of the time series result in the NetCDF Time Series file.
        loss_type : str, optional
            Type of loss for the time series result if applicable.

        Returns
        -------
        None
        """
        if loss_type:
            name = f'{loss_type} {name}'
        if self.nc is not None:
            if TPCTimeSeriesNC.exists(self.nc, id):
                self.time_series[name] = TPCTimeSeriesNC(self.nc, id, loss_type)
        else:
            self.time_series[name] = TPCTimeSeriesCSV(fpath, reference_time, index_col, loss_type)

    def count(self) -> int:
        # docstring inherited
        if self.df is None:
            return 0
        return self.df.shape[0]

    def conv_result_type_name(self, result_type: str) -> str:
        """Convert a short result type name to a long name that uses the same naming convention as the TPC file.

        Parameters
        ----------
        result_type : str
            Short result type name.

        Returns
        -------
        str
            Long result type name.
        """
        return RESULT_SHORT_NAME.get(result_type.lower(), result_type.lower())
