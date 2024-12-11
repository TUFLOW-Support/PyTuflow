import os
import re
import typing
from pathlib import Path

import pandas as pd

from pytuflow.pytuflow_types import PathLike


class TPCReader:
    """Class for reading and interacting with the TUFLOW TPC format. This class does not load results, what it
    does do is provide an interface to the TPC file. For example, it allows quickly finding a given property within
    the files, or iterating over all properties or a subset of properties (refined using a filter).

    Parameters
    ----------
    fpath : :class:`PathLike <pytuflow.pytuflow_types.PathLike>`
        The path to the TPC output file.
    """

    def __init__(self, fpath: PathLike) -> None:
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

    def find_property_name(self, name: str, regex_flags: int = 0) -> str:
        """Returns the property name from a regex search string.

        Parameters
        ----------
        name : str
            The regex search string.
        regex_flags : int, optional
            The flags to apply to the regular expression.

        Returns
        -------
        str
            The property name.
        """
        for idx, row in self._df.iterrows():
            if re.match(name, row[0], flags=regex_flags):
                return row[0]

    def get_property(self, name: str, default: typing.Any = None, regex: bool = False, value: str = None) -> typing.Any:
        """Returns a property value from the property name. The return data type will be inferred from the data.
        Path data will be returned as a string and will have the backslashes replaced with forward
        slashes on non-Windows.

        Parameters
        ----------
        name : str
            The property name.
        default : Any, optional
            The default value to return if the property is not found.
        regex : bool, optional
            If True, the name will be treated as a regular expression.
        value : str, optional
            The property value. If provided, this value will be used instead of searching for the value. This still
            can be useful, as the returned property will be in the correct data type (e.g. float, datetime, etc).

        Returns
        -------
        Any
            The property value.
        """
        if regex and not value:
            name = self.find_property_name(name)

        try:
            prop = self._df[self._df.iloc[:,0] == name].iloc[0,1] if value is None else value
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

    def iter_properties(self, filter: str = None, start_after: str = None,
                        end_before: str = None, regex: bool = False,
                        regex_flags: int = 0) -> typing.Generator[tuple[str, typing.Any], None, None]:
        """Iterate over the properties in the file.

        Parameters
        ----------
        filter : str, optional
            A search filter to apply to the property names.
        start_after : str, optional
            The property name to start after.
        end_before : str, optional
            The property name to end before.
        regex : bool, optional
            If True, the filter will be treated as a regular expression.
        regex_flags : int, optional
            The flags to apply to the regular expression.

        Yields
        ------
        tuple[str, Any]
            The property name and value.
        """
        start_idx = self.get_property_index(start_after) if start_after else -1
        end_idx = self.get_property_index(end_before) if end_before else 99
        for i in range(self._df.shape[0]):
            if i <= start_idx:
                continue
            if i >= end_idx:
                break
            if filter and not regex and filter in self._df.iloc[i,0]:
                yield self._df.iloc[i,0], self.get_property(self._df.iloc[i,0], value=self._df.iloc[i,1])
            elif filter and regex and re.findall(filter, self._df.iloc[i,0], regex_flags):
                yield self._df.iloc[i,0], self.get_property(self._df.iloc[i,0], value=self._df.iloc[i,1])
            elif not filter:
                yield self._df.iloc[i,0], self.get_property(self._df.iloc[i,0], value=self._df.iloc[i,1])
