from abc import abstractmethod

import pandas as pd

from .output import Output
from pytuflow._pytuflow_types import PathLike, TuflowPath


class TabularOutput(Output):
    """Base class for all TUFLOW tabular outputs."""

    @abstractmethod
    def __init__(self, *fpath: PathLike) -> None:
        # docstring inherited
        super().__init__(*fpath)
        #: TuflowPath: The path to the point GIS layer file
        self._gis_layer_p_fpath = None
        #: TuflowPath: The path to the line GIS layer file
        self._gis_layer_l_fpath = None
        #: TuflowPath: The path to the polygon GIS layer file
        self._gis_layer_r_fpath = None

    @abstractmethod
    def ids(self, filter_by: str = None) -> list[str]:
        """Returns all the available IDs for the output.

        The ``filter_by`` argument can be used to add a filter to the returned IDs.
        E.g. passing in a data type will return all the ids that contain that results for that data type.

        Parameters
        ----------
        filter_by : str, optional
            The context to filter the IDs by.

        Returns
        -------
        list[str]
            The available IDs.
        """
        pass

    @staticmethod
    def _filter_by_type(possible_types: list[str], ctx: list[str], df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        filtered_something = False
        ctx1 = [x for x in ctx if x.lower() in possible_types]
        ctx2 = [x for x in ctx1 if x in df['type'].str.lower().unique()]
        if ctx2:
            filtered_something = True
            df = df[df['type'].str.lower().isin(ctx2)]
            j = len(ctx) - 1
            for i, x in enumerate(reversed(ctx.copy())):
                if x in ctx2:
                    ctx.pop(j - i)
        elif ctx1:
            df = pd.DataFrame(columns=df.columns)
        return df, filtered_something

    def _filter_by_data_type(self, ctx: list[str], df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        filtered_something = False
        ctx1 = [self._get_standard_data_type_name(x) for x in ctx]
        ctx2 = [x for x in ctx1 if x in df['data_type'].unique()]
        if ctx2:
            filtered_something = True
            df = df[df['data_type'].isin(ctx2)]
            j = len(ctx) - 1
            for i, x in enumerate(reversed(ctx.copy())):
                if self._get_standard_data_type_name(x) in ctx2:
                    ctx.pop(j - i)
        return df, filtered_something

    @staticmethod
    def _filter_by_id(id_cols: list[str], ctx: list[str], df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        filtered_something = False
        if not ctx or df.empty:
            return df, filtered_something

        df1 = pd.DataFrame()
        for id_ in id_cols:
            df2 = df[df[id_].str.lower().isin(ctx)]
            if not df2.empty:
                filtered_something = True
                df1 = pd.concat([df1, df2], axis=0) if not df1.empty else df2
            if not df.empty:
                j = len(ctx) - 1
                for i, x in enumerate(reversed(ctx.copy())):
                    if df[id_].str.lower().isin([x.lower()]).any():
                        ctx.pop(j - i)

        df = df1 if not df1.empty else df
        return df, filtered_something
