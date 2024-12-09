from abc import ABC, abstractmethod

import pandas as pd

from pytuflow.outputs.helpers.get_standard_data_type_name import get_standard_data_type_name
from pytuflow.pytuflow_types import PathLike, LongPlotExtractionLocation


class ITimeSeries2D(ABC):
    """Interface class for 1D time series outputs."""

    @abstractmethod
    def __init__(self, *fpath: PathLike) -> None:
        super().__init__()
        #: pd.DataFrame: 2D information - this is typically PO data from TUFLOW Classic/HPC however can also be 2D data from TUFLOW FV.
        self.po_objs = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt'])
        #: pd.DataFrame: RL information.
        self.rl_objs = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt'])
        #: int: Number of 2d points - named po however refers to 2d points.
        self.po_point_count = 0
        #: int: Number of 2d lines - named po however refers to 2d lines.
        self.po_line_count = 0
        #: int: Number of 2d polys - named po however refers to 2d polys.
        self.po_poly_count = 0
        #: int: Number of reporting location points
        self.rl_point_count = 0
        #: int: Number of reporting location lines
        self.rl_line_count = 0
        #: int: Number of reporting location polys
        self.rl_poly_count = 0

    def context_combinations_2d(self, context: list[str]) -> pd.DataFrame:
        ctx = context.copy() if context else []
        df = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt', 'domain'])

        # domain
        po, rl = False, False
        if not context or '2d' in ctx or 'po' in ctx:
            po = True
            df = self.po_objs.copy()
            df['domain'] = '2d'
            df = self._context_refine_by_geometry(ctx, df)
            ctx = [x for x in ctx if x not in ['po', '2d']]
        if not context or '0d' in ctx or 'rl' in ctx:
            rl = True
            df1 = self.rl_objs.copy()
            df1['domain'] = 'rl'
            df1 = self._context_refine_by_geometry(ctx, df1)
            df = df1 if df.empty else pd.concat([df, df1], axis=0, ignore_index=True)
            ctx = [x for x in ctx if x not in ['rl', '0d']]

        # if no domain (including 1d) specified then get everything and let other filters do the work
        if not po and not rl and '1d' not in context and 'node' not in context and 'channel' not in context:
            df = self.po_objs.copy()
            df['domain'] = '2d'
            df1 = self.rl_objs.copy()
            df1['domain'] = 'rl'
            df = pd.concat([df, df1], axis=0, ignore_index=True)

        # geometry
        ctx1 = [x for x in ctx if x in ['point', 'line', 'polygon', 'region']]
        if ctx1:
            ctx1 = [x if x != 'region' else 'polygon' for x in ctx1]
            df = df[df['geometry'].isin(ctx1)]
            for i in range(len(ctx1) - 1, -1, -1):
                ctx.pop(i)

        # data types
        ctx1 = [get_standard_data_type_name(x) for x in ctx]
        ctx1 = [x for x in ctx1 if x in df['data_type'].unique()]
        if ctx1:
            df = df[df['data_type'].isin(ctx1)]
            for i in range(len(ctx1) - 1, -1, -1):
                ctx.pop(i)

        # ids
        if ctx:
            df = df[df['id'].isin(ctx)]

        return df if not df.empty else pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt', 'domain'])

    def _context_refine_by_geometry(self, context: list[str], df: pd.DataFrame) -> pd.DataFrame:
        df1 = df.copy()
        if context:
            for geom in ['point', 'line', 'poly']:
                if geom in context:
                    df1 = pd.concat([df1, df[df['geometry'] == geom]], axis=1, ignore_index=True)
        return df
