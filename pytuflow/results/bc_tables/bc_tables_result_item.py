import re
from pathlib import Path
from typing import TextIO

import pandas as pd

from .bc_tables_time_series import BCTablesTimeSeries
from .boundary_type import BoundaryType
from ..abc.time_series_result_item import TimeSeriesResultItem
from pytuflow.util.misc_tools import flatten
from pytuflow.types import PathLike


class BCTablesResultItem(TimeSeriesResultItem):
    """Base class for BCTable result items Boundary, etc."""

    def __init__(self, fpath: PathLike) -> None:
        # docstring inherited
        self.tcf = None
        self.units = ''
        self._bndry = []
        super().__init__(fpath)
        self.name = 'Boundary'

    def load(self) -> None:
        # docstring inherited
        with self.fpath.open() as f:
            for line in f:
                if line.startswith('Generated by'):
                    self.tcf = self._extract_tcf(line)
                elif re.findall(r'^"?BC\d{6}:\s', line):
                    self.load_time_series(line, f)

        if re.findall(r'_1d_bc_tables_check', self.fpath.stem):
            self.domain = '1d'
        elif re.findall(r'_2d_bc_tables_check', self.fpath.stem):
            self.domain = '2d'
        self.domain_2 = 'boundary'

        a = [(x.id, x.name, x.type) for x in self._bndry]
        self.df = pd.DataFrame(a, columns=['ID', 'Name', 'Type'])
        self.df.set_index('ID', inplace=True)

    def load_time_series(self, line: str, fo: TextIO) -> None:
        """Load time series data from file.

        Parameters
        ----------
        line : str
            Line from file.
        fo : TextIO
            File object.
        """
        bndry = BoundaryType(line)
        if not bndry.valid:
            return
        bndry.read(fo)
        self._bndry.append(bndry)
        if bndry.type not in self.time_series:
            self.time_series[bndry.type] = BCTablesTimeSeries()
        self.time_series[bndry.type].append(bndry)
        if not self.units:
            self.units = bndry.units

    def conv_result_type_name(self, result_type: str) -> str:
        # docstring inherited
        return result_type

    def bcid2name(self, bcid: str) -> str:
        """Return boundary condition id to name.

        Parameters
        ----------
        bcid : str
            Boundary condition id.

        Returns
        -------
        str
            Boundary condition name.
        """
        if bcid not in self.df.index:
            return bcid
        return self.df.loc[bcid, 'Name']

    def name2bcid(self, name: str) -> str:
        """Return boundary condition ID from name.

        Parameters
        ----------
        name : str
            Boundary condition name.

        Returns
        -------
        str
            Boundary condition ID.
        """
        if name not in self.df['Name'].tolist():
            return name
        return self.df[self.df['Name'] == name].index[0]

    def ids(self, result_type: str) -> list[str]:
        # docstring inherited
        if self.df is None:
            return []
        if not result_type:
            return self.df['Name'].tolist()
        if result_type in self.time_series:
            return [self.bcid2name(x) for x in self.time_series[result_type].df.columns if x not in self.time_series[result_type].empty_results]
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
            if id not in self.df.index:
                ids = [self.bcid2name(x) for x in ts.df.columns.tolist()]
            if result_type not in result_types and id in ids:
                result_types.append(result_type)
        return result_types

    def _extract_tcf(self, line: str) -> PathLike:
        tcf = re.findall(r'".*"', line)
        if tcf:
            tcf = tcf[0].strip('"')
            return Path(tcf)

    def _expand_index_col(self,
                          df: pd.DataFrame,
                          result_type: str,
                          id: list[str],
                          levels: list[str]) -> pd.DataFrame:
        ids = [x.id for x in self._bndry]
        df_idx = pd.DataFrame()
        index_names = []
        for id_ in id:
            bndry = self._bndry[ids.index(id_)]
            index_names.append(bndry.index_name)
            df_ = pd.DataFrame(bndry.values[:,0], columns=[f'{id_}::index'])
            df_idx = pd.concat([df_idx, df_], axis=1)
        df = pd.concat([df_idx, df], axis=1)
        df = df[flatten([[f'{x}::index', x] for x in id])]  # correct column order
        index_alias = [(self.name, result_type, x, 'Index', idx) for x, idx in zip(id, index_names)]
        col_alias = [(self.name, result_type, x, 'Value', '') for x in id]
        df.columns = pd.MultiIndex.from_tuples(flatten((zip(index_alias, col_alias))), names=levels)
        return df
