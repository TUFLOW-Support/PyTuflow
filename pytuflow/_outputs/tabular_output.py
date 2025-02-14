from abc import abstractmethod

import pandas as pd

from .output import Output
from ..pytuflow_types import PathLike, TuflowPath


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
    def _filter(self, filter_by: str) -> pd.DataFrame:
        """Returns a DataFrame with the output combinations for the given filter string.

        Parameters
        ----------
        filter_by : str
            The context to extract the combinations for.

        Returns
        -------
        pd.DataFrame
            The context combinations.

        Examples
        --------
        Extracting the available :code:`channel` output combinations. The returned DataFrame contains a row for each
        :code:`id` / :code:`data_type` combination that is available for :code:`channel` types.

        >>> res._filter('channel')
                   id data_type geometry  start  end    dt domain
        55        ds1      flow     line    0.0  3.0  60.0     1d
        56        ds2      flow     line    0.0  3.0  60.0     1d
        57        ds3      flow     line    0.0  3.0  60.0     1d
        58        ds4      flow     line    0.0  3.0  60.0     1d
        59        ds5      flow     line    0.0  3.0  60.0     1d
        ..        ...       ...      ...    ...  ...   ...    ...
        158   FC02.04  velocity     line    0.0  3.0  60.0     1d
        159   FC02.05  velocity     line    0.0  3.0  60.0     1d
        160   FC02.06  velocity     line    0.0  3.0  60.0     1d
        161  FC04.1_C  velocity     line    0.0  3.0  60.0     1d
        162  FC_weir1  velocity     line    0.0  3.0  60.0     1d

        Similarly, extracting combinations for :code:`flow`:

        >>> res._filter('flow')
                           id data_type geometry  start  end    dt domain
        55        ds1      flow     line    0.0  3.0  60.0     1d
        56        ds2      flow     line    0.0  3.0  60.0     1d
        57        ds3      flow     line    0.0  3.0  60.0     1d
        58        ds4      flow     line    0.0  3.0  60.0     1d
        59        ds5      flow     line    0.0  3.0  60.0     1d
        ..        ...       ...      ...    ...  ...   ...    ...
        104   FC02.04      flow     line    0.0  3.0  60.0     1d
        105   FC02.05      flow     line    0.0  3.0  60.0     1d
        106   FC02.06      flow     line    0.0  3.0  60.0     1d
        107  FC04.1_C      flow     line    0.0  3.0  60.0     1d
        108  FC_weir1      flow     line    0.0  3.0  60.0     1d
        """
        pass

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
