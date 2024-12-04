import os
import re
import typing
from pathlib import Path

import pandas as pd

from pytuflow.pytuflow_types import PathLike


class TPCReader:
    """Class for reading and interacting with the TUFLOW TPC format. This class does not load results, but provides
    and interface to the TPC file.
    """

    def __init__(self, fpath: PathLike) -> None:
        """
        Parameters
        ----------
        fpath : PathLike
            The path to the TPC output file.
        """
        #: Path: The path to the TPC output file.
        self.fpath = Path(fpath)
        if not self.fpath.exists():
            raise FileNotFoundError(f'File not found: {self.fpath}')

        try:
            self._df = pd.read_csv(self.fpath, sep=' == ', engine='python', header=None)
        except Exception as e:
            raise Exception(f'Error loading file: {e}')

    def property_count(self) -> int:
        """Returns the number of properties defined in the file.

        Returns
        -------
        int
            The number of properties.
        """
        return self._df.shape[0]

    def get_property(self, name: str, default: typing.Any = None) -> typing.Any:
        """Returns a property value from the property name. The return data type will be inferred from the data.
        Path data will be returned as a string and will have the backslashes replaced with forward
        slashes on non-Windows.

        Parameters
        ----------
        name : str
            The property name.
        default : Any, optional
            The default value to return if the property is not found.

        Returns
        -------
        Any
            The property value.
        """
        try:
            prop = self._df[self._df.iloc[:,0] == name].iloc[0,1]
            if os.name != 'nt' and '\\' in prop:
                prop = prop.replace('\\', '/')
            if '\\' in prop or '/' in prop:
                return prop
            # check if value is datetime
            if re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', prop):
                return pd.to_datetime(prop)
            # check if value is an int
            if re.match(r'^[+-]?\d+$', prop):
                try:
                    return int(prop)
                except ValueError:
                    pass
            # check if value is a float
            if re.match(r'^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$', prop):
                try:
                    return float(prop)
                except ValueError:
                    pass
            return prop
        except Exception as e:
            return default

    def get_property_index(self, name: str) -> int:
        """Returns the index of the property from the property name. The index is the order of the property
        within the file.

        Negative one is returned if the property is not found.

        Parameters
        ----------
        name : str
            The property name.

        Returns
        -------
        int
            The index of the property.
        """
        try:
            ind = self._df[self._df.iloc[:,0] == name].index[0]
        except Exception as e:
            ind = -1
        return ind

    def iter_properties(self, filter: str) -> typing.Generator[tuple[str, typing.Any], None, None]:
        """Iterate over the properties in the file.

        Parameters
        ----------
        filter : str
            A search filter to apply to the property names.

        Yields
        ------
        tuple[str, Any]
            The property name and value.
        """
        for i in range(self._df.shape[0]):
            if filter in self._df.iloc[i,0]:
                yield self._df.iloc[i,0], self.get_property(self._df.iloc[i,0])
