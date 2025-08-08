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
