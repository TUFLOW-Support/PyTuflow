from pathlib import Path
from typing import TextIO

import pandas as pd

from .hyd_tables_result_item import HydTableResultItem
from ..types import PathLike


class CrossSectionEntry:

    def __init__(self, xs_id: str, df_xs: pd.DataFrame, df_proc: pd.DataFrame) -> None:
        self.xs_id = xs_id
        self.df_xs = df_xs
        self.df_proc = df_proc

    def __repr__(self) -> str:
        return f'<CrossSectionEntry: {self.xs_id}>'


class HydTableCrossSection(HydTableResultItem):

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
        """
        Unlike abstract method which loads in individual time series results,
        use this method to load all time series data at once.
        """
        if not self.database:
            return

        # echoed cross-section data
        col_names = list(self.database.values())[0].df_xs.columns
        dfs = [x.df_xs for x in self.database.values()]
        self._load_time_series(dfs, col_names, col_names[1])

        # processed cross-section data
        col_names = list(self.database.values())[0].df_proc.columns
        dfs = [x.df_proc for x in self.database.values()]
        self._load_time_series(dfs, col_names, col_names[0])

    def append(self, fo: TextIO, xs_id: str, xs_name: str, xs_source: Path, xs_type: str) -> None:
        df = pd.read_csv(fo, index_col=False)
        if xs_type == 'XZ':
            df_xs = df[df.columns[:4]].dropna()
            df_proc = df[df.columns[5:]].dropna()
            df_proc.rename(columns={'Elevation.1': 'Elevation'}, inplace=True)
        else:
            df_xs = pd.DataFrame(columns=['Points', 'Distance', 'Elevation', 'Manning n'])
            df_proc = df.dropna()
        db_entry = CrossSectionEntry(xs_id, df_xs, df_proc)
        self.database[xs_id] = db_entry
        self.df = pd.concat([self.df, pd.DataFrame({'Name': [xs_name], 'Type': [xs_type], 'Source': [str(xs_source)]}, index=[xs_id])], axis=0)
        self.df.index.name = 'id'

    def conv_result_type_name(self, result_type: str) -> str:
        if self.database:
            col_names = list(self.database.values())[0].df_xs.columns
            if self._in_col_names(result_type, col_names):
                return self._in_col_names(result_type, col_names)
            col_names = list(self.database.values())[0].df_proc.columns
            if self._in_col_names(result_type, col_names):
                return self._in_col_names(result_type, col_names)
        return result_type

    def xsid2name(self, xs_id: str) -> str:
        if xs_id in self.df.index:
            return self.df.loc[xs_id, 'Name']
        return xs_id

    def name2xsid(self, xs_name: str) -> str:
        if xs_name in self.df['Name'].tolist():
            return self.df[self.df['Name'] == xs_name].index[0]
        return xs_name

    def ids(self, result_type: str) -> list[str]:
        if self.df is None:
            return []
        if not result_type:
            if self.has_unique_names():
                return self.df['Name'].tolist()
            else:
                return self.df.index.tolist()
        if result_type in self.time_series:
            if self.has_unique_names():
                return [self.xsid2name(x) for x in self.time_series[result_type].df.columns.tolist()]
            else:
                return self.time_series[result_type].df.columns.tolist()
        return []

    def result_types(self, id: str) -> list[str]:
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
        if self._has_unique_names is None:
            if self.df is None:
                return True
            names = self.df['Name'].tolist()
            self._has_unique_names = len(names) == len(set(names))
        return self._has_unique_names
