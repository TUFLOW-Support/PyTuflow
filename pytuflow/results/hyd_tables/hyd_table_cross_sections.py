from pathlib import Path
from typing import TextIO

import pandas as pd

from ..abc.time_series_result_item import TimeSeriesResultItem
from ..types import PathLike


class CrossSectionEntry:

    def __init__(self, xs_id: str, df_xs: pd.DataFrame, df_proc: pd.DataFrame) -> None:
        self.xs_id = xs_id
        self.df_xs = df_xs
        self.df_proc = df_proc

    def __repr__(self) -> str:
        return f'<CrossSectionEntry: {self.xs_id}>'


class HydTableCrossSection(TimeSeriesResultItem):

    def __init__(self, fpath: PathLike = None) -> None:
        super().__init__(fpath)
        self.name = 'Cross Section'
        self.domain = '1d'
        self.domain_2 = 'cross_section'
        self.database = {}
        self.df = pd.DataFrame([], columns=['Name', 'Type', 'Source'])
        self.df.index.name = 'id'

    def __repr__(self) -> str:
        if hasattr(self, 'fpath') and self.fpath is not None:
            return f'<CrossSectionCheck: {self.fpath.stem}>'
        return '<CrossSectionCheck>'

    def load(self) -> None:
        pass

    def load_time_series(self, result_name: str, df: pd.DataFrame) -> None:
        pass

    def append(self, fo: TextIO, xs_id: str, xs_name: str, xs_source: Path, xs_type: str) -> None:
        df = pd.read_csv(fo, index_col=False)
        df_xs = df[df.columns[:4]].dropna()
        df_proc = df[df.columns[5:]].dropna()
        df_proc.rename(columns={'Elevation.1': 'Elevation'}, inplace=True)
        db_entry = CrossSectionEntry(xs_id, df_xs, df_proc)
        self.database[xs_id] = db_entry
        self.df = pd.concat([self.df, pd.DataFrame({'Name': [xs_name], 'Type': [xs_type], 'Source': [str(xs_source)]}, index=[xs_id])], axis=0)
        self.df.index.name = 'id'

    @staticmethod
    def conv_result_type_name(result_type: str) -> str:
        return result_type
