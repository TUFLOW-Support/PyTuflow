from abc import abstractmethod

from .output import Output
from ..pytuflow_types import PathLike, TuflowPath


class TabularOutput(Output):
    """Base class for all TUFLOW tabular outputs."""

    @abstractmethod
    def __init__(self, *fpath: PathLike) -> None:
        # docstring inherited
        super().__init__(*fpath)
        #: :doc:`TuflowPath <pytuflow.pytuflow_types.TuflowPath>`: The path to the point GIS layer file
        self.gis_layer_p_fpath = None
        #: :doc:`TuflowPath <pytuflow.pytuflow_types.TuflowPath>`: The path to the line GIS layer file
        self.gis_layer_l_fpath = None
        #: :doc:`TuflowPath <pytuflow.pytuflow_types.TuflowPath>`: The path to the polygon GIS layer file
        self.gis_layer_r_fpath = None
        #: Layer: The point GIS layer
        self.gis_layer_p = None
        #: Layer: The line GIS layer
        self.gis_layer_l = None
        #: Layer: The polygon GIS layer
        self.gis_layer_r = None

    @abstractmethod
    def ids(self, context: str = None) -> list[str]:
        """Returns all the available IDs for the output.

        The context argument can be used to add a filter to the returned IDs. E.g. passing in a data type will return
        all the ids that contain that results for that data type.

        Parameters
        ----------
        context : str, optional
            The context to filter the IDs by.

        Returns
        -------
        list[str]
            The available IDs.
        """
        pass
