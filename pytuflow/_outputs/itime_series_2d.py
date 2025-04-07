from abc import ABC, abstractmethod

import pandas as pd

from pytuflow._pytuflow_types import PathLike


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
        self._po_objs = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt'])
        #: pd.DataFrame: RL output objects. Column headers are :code:`[id, data_type, geometry, start, end, dt]`
        self._rl_objs = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt'])
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

    def _combinations_2d(self, filter_by: list[str]) -> pd.DataFrame:
        """Returns a DataFrame of all the 2D and RL output objects that match the filter.

        For example, the context may be :code:`['po']` or :code:`['po', 'flow']`. The return DataFrame
        is a filtered version of the :code:`po_objs` + :code:`rl_objs` DataFrame that matches the context.

        Parameters
        ----------
        filter_by : list[str]
            The string to filter the 1D objects by.

        Returns
        -------
        pd.DataFrame
            The filtered 1D objects
        """
        from .map_output import MapOutput

        ctx = filter_by.copy() if filter_by else []
        df = pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt', 'domain'])

        # domain
        filtered_something = False
        if not filter_by or '2d' in ctx or 'po' in ctx:
            filtered_something = True
            df = self._po_objs.copy()
            df['domain'] = '2d'
            df = self._context_refine_by_geometry(ctx, df)
            ctx = [x for x in ctx if x not in ['po', '2d']]
        if not filter_by or '0d' in ctx or 'rl' in ctx:
            filtered_something = True
            df1 = self._rl_objs.copy()
            df1['domain'] = 'rl'
            df1 = self._context_refine_by_geometry(ctx, df1)
            if not df1.empty:
                df = df1 if df.empty else pd.concat([df, df1], axis=0, ignore_index=True)
            ctx = [x for x in ctx if x not in ['rl', '0d']]

        # if no domain (including 1d) specified then get everything and let other filters do the work
        if not filtered_something and '1d' not in filter_by and 'node' not in filter_by and 'channel' not in filter_by:
            df_ = None
            if not self._po_objs.empty:
                df_ = self._po_objs.copy()
                df_['domain'] = '2d'
            if not self._rl_objs.empty:
                df1 = self._rl_objs.copy()
                df1['domain'] = 'rl'
                df_ = df1 if df_ is None else pd.concat([df_, df1], axis=0, ignore_index=True)

            if df_ is None:
                return df

            df = df_

        # geometry
        ctx1 = [x for x in ctx if x in ['point', 'line', 'polygon', 'region']]
        if ctx1:
            filtered_something = True
            ctx1 = [x if x != 'region' else 'polygon' for x in ctx1]
            df = df[df['geometry'].isin(ctx1)]
            j = len(ctx) - 1
            for i, x in enumerate(reversed(ctx.copy())):
                if x in ['point', 'line', 'polygon', 'region']:
                    ctx.pop(j - i)

        # data types
        ctx1 = [MapOutput._get_standard_data_type_name(x) for x in ctx]
        ctx1 = [x for x in ctx1 if x in df['data_type'].unique()]
        if ctx1:
            filtered_something = True
            df = df[df['data_type'].isin(ctx1)]
            j = len(ctx) - 1
            for i, x in enumerate(reversed(ctx.copy())):
                if MapOutput._get_standard_data_type_name(x) in ctx1:
                    ctx.pop(j - i)

        # ids
        if ctx:
            df = df[df['id'].str.lower().isin(ctx)] if not df.empty else pd.DataFrame()
            if not df.empty:
                j = len(ctx) - 1
                for i, x in enumerate(reversed(ctx.copy())):
                    if df['id'].str.lower().isin([x.lower()]).any():
                        ctx.pop(j - i)
                if ctx and not filtered_something:
                    df = pd.DataFrame()

        return df if not df.empty else pd.DataFrame(columns=['id', 'data_type', 'geometry', 'start', 'end', 'dt', 'domain'])

    def _context_refine_by_geometry(self, context: list[str], df: pd.DataFrame) -> pd.DataFrame:
        df1 = df.copy()
        if context:
            for geom in ['point', 'line', 'poly']:
                if geom in context:
                    df1 = pd.concat([df1, df[df['geometry'] == geom]], axis=1, ignore_index=True)
        return df
