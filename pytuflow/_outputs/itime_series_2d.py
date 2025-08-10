from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd

from .._pytuflow_types import PathLike, AppendDict


class ITimeSeries2D(ABC):
    """Interface class for 2D and RL time series outputs.

    Parameters
    ----------
    fpath : PathLike
        The file path to the TUFLOW output file.
    """

    @abstractmethod
    def __init__(self, *fpath: PathLike) -> None:
        super().__init__()
        #: pd.DataFrame: PO/2D output objects. Column headers are :code:`[id, data_type, geometry, start, end, dt]`
        self.po_objs = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt'])
        #: pd.DataFrame: RL output objects. Column headers are :code:`[id, data_type, geometry, start, end, dt]`
        self.rl_objs = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt'])
        #: int: Number of 2d points
        self.po_point_count = 0
        #: int: Number of 2d lines
        self.po_line_count = 0
        #: int: Number of 2d polys
        self.po_poly_count = 0
        #: int: Number of reporting location points
        self.rl_point_count = 0
        #: int: Number of reporting location lines
        self.rl_line_count = 0
        #: int: Number of reporting location polys
        self.rl_poly_count = 0

        self._time_series_data_2d = AppendDict()
        self._time_series_data_rl = AppendDict()

    @staticmethod
    def _context_refine_by_geometry(context: list[str], df: pd.DataFrame) -> pd.DataFrame:
        df1 = df.copy()
        if context:
            for geom in ['point', 'line', 'poly']:
                if geom in context:
                    df1 = pd.concat([df1, df[df['geometry'] == geom]], axis=1, ignore_index=True)
        return df

    @staticmethod
    def _replace_1d_aliases(filter_by: str) -> str:
        def replace_alias(filter_by_: list[str], alias: str, values: list[str]):
            if alias in filter_by_:
                while alias in filter_by_:
                    filter_by_.remove(alias)
                for val in values:
                    if val not in filter_by_:
                        filter_by_.append(val)

        filter_by = [x.strip().lower() for x in filter_by.split('/')] if filter_by else []
        # replace channel with 1d/line and node with 1d/point
        replace_alias(filter_by, 'channel', ['1d', 'line'])
        replace_alias(filter_by, 'node', ['1d', 'point'])
        return '/'.join(filter_by)

    def _time_series_extractor(self, data_types: list[str], custom_names: list[str], time_series_data: dict,
                               ctx: pd.DataFrame, time_fmt: str, share_idx: bool,
                               reference_time: datetime) -> pd.DataFrame:
        pass

    def _maximum_extractor(self, data_types: list[str], custom_names: list[str], maximum_data: dict,
                           ctx: pd.DataFrame, time_fmt: str, reference_time: datetime) -> pd.DataFrame:
        pass

    def _append_time_series_2d(self,
                               domain: str,
                               time_series_data: dict,
                               df: pd.DataFrame,
                               ctx: pd.DataFrame,
                               data_types: list[str],
                               time_fmt: str,
                               share_idx: bool,
                               reference_time: datetime) -> pd.DataFrame:
        """Adds time-series data from the domain to the existing time-series data."""
        df1 = self._time_series_extractor(ctx[ctx['domain'] == domain].data_type.unique(), data_types,
                                          time_series_data, ctx, time_fmt, share_idx, reference_time)
        domain2name = {'1d': '1d', '2d': 'po', 'rl': 'rl'}
        df1.columns = ['{0}/{domain}/{1}/{2}'.format(*x.split('/'), domain=domain2name[domain]) if x.split('/')[0] == 'time' else f'{domain2name[domain]}/{x}' for x in df1.columns]
        if df.empty and not df1.empty:
            df = df1
        elif not df1.empty:
            if share_idx:
                df1.index = df.index
            df = pd.concat([df, df1], axis=1)
        return df

    def _append_maximum_2d(self,
                           domain: str,
                           maximum_data: dict,
                           df: pd.DataFrame,
                           ctx: pd.DataFrame,
                           data_types: list[str],
                           time_fmt: str,
                           reference_time: datetime) -> pd.DataFrame:
        domain2name = {'1d': '1d', '2d': 'po', 'rl': 'rl'}
        df1 = self._maximum_extractor(ctx[ctx['domain'] == domain].data_type.unique(), data_types,
                                      maximum_data, ctx, time_fmt, reference_time)
        df1.columns = [f'{domain2name[domain]}/{x}' for x in df1.columns]
        if df.empty and not df1.empty:
            df = df1
        elif not df1.empty:
            df = pd.concat([df, df1], axis=0)
        return df
