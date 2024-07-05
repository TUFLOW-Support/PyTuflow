from pathlib import Path
from typing import TextIO

import pandas as pd

from .hyd_tables_result_item import HydTableResultItem
from pytuflow.pytuflow_types import PathLike


class CrossSectionEntry:
    """Class for handling individual cross-section entries in HydTableCrossSection."""

    def __init__(self, xs_id: str, df_xs: pd.DataFrame, df_proc: pd.DataFrame) -> None:
        """
        Parameters
        ----------
        xs_id : str
            Cross-section ID (typically XS00001, XS00002, etc.).
        df_xs : pd.DataFrame
            Cross-section data.
        df_proc : pd.DataFrame
            Processed cross-section data.
        """
        self.xs_id = xs_id
        self.df_xs = df_xs
        self.df_xs_exists = True
        if self.df_xs.empty:  # HW tables for instance won't have a cross-section
            self.df_xs_exists = False
        self.df_proc = df_proc

    def __repr__(self) -> str:
        return f'<CrossSectionEntry: {self.xs_id}>'


class HydTableCrossSection(HydTableResultItem):
    """Hydraulic table Channels class."""

    def __init__(self, fpath: PathLike = None) -> None:
        super().__init__(fpath)
        self.name = 'Cross Section'
        self.domain = '1d'
        self.domain_2 = 'cross_section'
        self.database = {}
        self.df = pd.DataFrame([], columns=['Name', 'Type', 'Source'])
        self.df.index.name = 'id'
        self._result_types = ['Elevation', 'Manning n', 'Depth', 'Width', 'Eff Width', 'Eff Area', 'Eff Wet Per',
                             'Radius', 'Vert Res Factor','K']
        self._has_unique_names = None

    def __repr__(self) -> str:
        if hasattr(self, 'fpath') and self.fpath is not None:
            return f'<HydTableCrossSection: {self.fpath.stem}>'
        return '<HydTableCrossSection>'

    def load(self) -> None:
        pass

    def load_time_series(self) -> None:
        """Unlike abstract method which loads in individual time series results,
        use this method to load all time series data at once.
        """
        if not self.database:
            return

        # echoed cross-section data
        col_names = list(self.database.values())[0].df_xs.columns
        dfs = [x.df_xs for x in self.database.values()]
        self._load_time_series(dfs, col_names, col_names[1])
        missing_xs = [x for x in self.database if not self.database[x].df_xs_exists]
        if 'Elevation'in self.time_series:
            self.time_series['Elevation'].empty_results = missing_xs
        if 'Manning n' in self.time_series:
            self.time_series['Manning n'].empty_results = missing_xs

        # processed cross-section data
        col_names = list(self.database.values())[0].df_proc.columns
        dfs = [x.df_proc for x in self.database.values()]
        self._load_time_series(dfs, col_names, col_names[0])

    def append(self, fo: TextIO, xs_id: str, xs_name: str, xs_source: Path, xs_type: str) -> None:
        """Append a cross-section to the database.

        Parameters
        ----------
        fo : TextIO
            File object containing the channel data.
        xs_id : str
            Cross-Section ID (XS00001, XS00001, etc).
        xs_name : str
            Name of the cross-section - usually the source file name.
        xs_type : str
            Type attribute of the cross-section (XZ, HW, etc).
        """
        df = pd.read_csv(fo)
        if xs_type == 'XZ':
            df_xs = df[df.columns[:4]].dropna()
            df_proc = df[df.columns[5:-1]].dropna(how='all')
            df_proc.rename(columns={'Elevation.1': 'Elevation'}, inplace=True)
        else:
            df_xs = pd.DataFrame(columns=['Points', 'Distance', 'Elevation', 'Manning n'])
            df_proc = df[df.columns[:-1]].dropna(how='all')
        db_entry = CrossSectionEntry(xs_id, df_xs, df_proc)
        self.database[xs_id] = db_entry
        self.df = pd.concat([self.df, pd.DataFrame({'Name': [xs_name], 'Type': [xs_type], 'Source': [str(xs_source)]}, index=[xs_id])], axis=0)
        self.df.index.name = 'id'

    def conv_result_type_name(self, result_type: str) -> str:
        # docstring inherited
        if self.database:
            col_names = list(self.database.values())[0].df_xs.columns
            if self._in_col_names(result_type, col_names):
                return self._in_col_names(result_type, col_names)
            col_names = list(self.database.values())[0].df_proc.columns
            if self._in_col_names(result_type, col_names):
                return self._in_col_names(result_type, col_names)
        return result_type

    def xsid2name(self, xs_id: str) -> str:
        """Return the name of a cross-section given its ID.

        Parameters
        ----------
        xs_id : str
            Cross-section ID.

        Returns
        -------
        str
            Cross-section name.
        """
        if xs_id in self.df.index:
            return self.df.loc[xs_id, 'Name']
        return xs_id

    def name2xsid(self, xs_name: str) -> str:
        """Returns the ID of the cross-section given its name.

        Parameters
        ----------
        xs_name : str
            Cross-section name.

        Returns
        -------
        str
            Cross-section ID.
        """
        if xs_name in self.df['Name'].tolist():
            return self.df[self.df['Name'] == xs_name].index[0]
        return xs_name

    def ids(self, result_type: str) -> list[str]:
        # docstring inherited
        if self.df is None:
            return []
        if not result_type:
            if self.has_unique_names():
                return self.df['Name'].tolist()
            else:
                return self.df.index.tolist()
        if result_type in self.time_series:
            if self.has_unique_names():
                return [self.xsid2name(x) for x in self.time_series[result_type].df.columns if x not in self.time_series[result_type].empty_results]
            else:
                return self.time_series[result_type].df.columns.tolist()
        return []

    def result_types(self, id: str) -> list[str]:
        # docstring inherited
        if not self.time_series:
            return []
        if not id:
            return list(self.time_series.keys())
        result_types = []
        for result_type, ts in self.time_series.items():
            ids = ts.df.columns
            if self.has_unique_names() and id not in self.df.index:
                ids = [self.xsid2name(x) for x in ids if x in self.df.index]
            if result_type not in result_types and id in ids:
                result_types.append(result_type)
        return result_types

    def has_unique_names(self) -> bool:
        """Returns True if all the cross-sections have unique names. This is used to determine whether the ID or
        name is used in the return DataFrame of certain methods.

        Returns
        -------
        bool
            True if all cross-sections have unique names.
        """
        if self._has_unique_names is None:
            if self.df is None:
                return True
            names = self.df['Name'].tolist()
            self._has_unique_names = len(names) == len(set(names))
        return self._has_unique_names
