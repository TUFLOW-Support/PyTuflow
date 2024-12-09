import json
import re
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd
from netCDF4 import Dataset

from pytuflow.pytuflow_types import PathLike
from pytuflow.util import flatten

with (Path(__file__).parents[1] / 'data' / 'ts_labels.json').open() as f:
    TPC_INTERNAL_NAMES = json.load(f)


class NC_TS:
    """Class for interfacing with a TUFLOW NetCDF time series file."""

    def __init__(self, nc: Union[PathLike, Dataset]) -> None:
        """
        Parameters
        ----------
        nc : Union[PathLike, Dataset]
            Path to the NetCDF file or an open Dataset object.
        """
        # private
        self._responsible_for_close = False

        #: Dataset: NetCDF Dataset object.
        self.nc = None

        if isinstance(nc, Dataset):
            self.nc = nc
            self._responsible_for_close = False
        else:
            self.nc = Dataset(nc)
            self._responsible_for_close = True

    def __del__(self):
        if self._responsible_for_close and self.nc is not None:
            self.nc.close()

    @staticmethod
    def node_names(ncfpath: Union[PathLike, Dataset]) -> list[str]:
        """Returns a list of node names in the NetCDF file.

        Parameters
        ----------
        ncfpath : Union[PathLike, Dataset]
            Path to the NetCDF file or an open Dataset object.

        Returns
        -------
        list[str]
            List of node names.
        """
        cls = NC_TS(ncfpath)
        if 'node_names' not in cls.nc.variables:
            return []
        return [b''.join(x).decode().strip() for x in cls.nc.variables['node_names']]

    @staticmethod
    def channel_names(ncfpath: Union[PathLike, Dataset]):
        """Returns a list of channel names in the NetCDF file.

        Parameters
        ----------
        ncfpath : Union[PathLike, Dataset]
            Path to the NetCDF file or an open Dataset object.

        Returns
        -------
        list[str]
            List of channel names.
        """
        cls = NC_TS(ncfpath)
        if 'channel_names' not in cls.nc.variables:
            return []
        return [b''.join(x).decode().strip() for x in cls.nc.variables['channel_names']]

    @staticmethod
    def times(ncfpath: Union[PathLike, Dataset]) -> list[float]:
        """Returns a list of times in the NetCDF file.

        Parameters
        ----------
        ncfpath : Union[PathLike, Dataset]
            Path to the NetCDF file or an open Dataset object.

        Returns
        -------
        list[float]
            List of times.
        """
        cls = NC_TS(ncfpath)
        if 'time' not in cls.nc.variables:
            return []
        return cls.nc.variables['time'][:]

    @staticmethod
    def data_types_2d(ncfpath: Union[PathLike, Dataset]) -> list[str]:
        """Returns a list of 2D data types in the NetCDF file.

        Parameters
        ----------
        ncfpath : Union[PathLike, Dataset]
            Path to the NetCDF file or an open Dataset object.

        Returns
        -------
        list[str]
            List of data types.
        """
        cls = NC_TS(ncfpath)
        data_types = []
        for var in cls.nc.variables:
            if re.findall(r'_2d$', var) and not var.startswith('name_'):
                data_types.append(re.sub(r'_2d$', '', var))
        return data_types

    @staticmethod
    def extract_result(ncfpath: Union[PathLike, Dataset], data_type: str, domain: str) -> pd.DataFrame:
        """Returns a DataFrame with the extracted results based on the data_Type and domain.

        Parameters
        ----------
        ncfpath : Union[PathLike, Dataset]
            Path to the NetCDF file or an open Dataset object.
        data_type : str
            The data type to extract.
        domain : str
            The domain which the data type belongs in.

        Returns
        -------
        pd.DataFrame
            The extracted results.
        """
        cls = NC_TS(ncfpath)
        if domain.lower() == '1d':
            var = TPC_INTERNAL_NAMES['1d_labels'].get(data_type, None)
        elif domain.lower() == 'rl':
            var = TPC_INTERNAL_NAMES['rl_labels'].get(data_type, None)
        else:
            var = TPC_INTERNAL_NAMES['po_labels'].get(data_type, None)
        if not var or var['nc'] not in cls.nc.variables:
            return
        varname = var['nc']
        var = cls.nc.variables[varname]
        if domain.lower() == '1d' and 'losses_1d' not in varname:
            if 'channel' in var.dimensions[0]:
                columns = cls.channel_names(ncfpath)
            else:
                columns = cls.node_names(ncfpath)
        else:
            if 'losses_1d' in varname:
                names = f'names_{varname}'
            else:
                names = f'name_{varname}'
            if names not in cls.nc.variables:
                return
            columns = [b''.join(x).decode().strip() for x in cls.nc.variables[names]]

        a = np.transpose(var[:])
        if isinstance(a, np.ma.masked_array):
            a = a.filled(np.nan)

        if 'flow_regime' in varname:
            a = np.apply_along_axis(lambda x: b''.join(x).decode().strip(), 0, a)

        return pd.DataFrame(a, index=cls.times(ncfpath), columns=columns)
