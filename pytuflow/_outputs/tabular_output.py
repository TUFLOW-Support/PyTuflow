import typing
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

    def _tabular_type_filter(self, possible_types: list[str], ctx: list[str], df: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        """Common filtering method for tabular outputs."""
        df, filtered_something = self._filter_by_type(possible_types, ctx, df)

        # data types
        df, filtered_something_ = self._filter_by_data_type(ctx, df, self._get_standard_data_type_name)
        if filtered_something_:
            filtered_something = True

        # ids
        df, filtered_something_ = self._filter_by_id(['id', 'uid'], ctx, df)
        if filtered_something_:
            filtered_something = True

        return df, filtered_something
