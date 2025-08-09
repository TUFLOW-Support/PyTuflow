from abc import abstractmethod

from .output import Output
from .._pytuflow_types import PathLike
from ..util import get_logger


logger = get_logger()


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

    def _figure_out_loc_and_data_types(self, locations: str | list[str],
                                       data_types: str | list[str] | None) -> tuple[list[str], list[str]]:
        """Figure out the locations and data types to use."""
        # sort out locations and data types
        if not locations:
            locations = self.ids()
        else:
            locations1 = []
            locations = [locations] if not isinstance(locations, list) else locations
            for loc in locations:
                ids = self.ids(loc)
                if not self.ids(loc):
                    logger.warning(f'HydTablesCheck.section(): Location "{loc}" not found in the output - removing.')
                else:
                    locations1.append(ids[0])
            locations = locations1
            if not locations:
                raise ValueError('No valid locations provided.')

        if not data_types:
            data_types = self.data_types()
        else:
            data_types = [data_types] if not isinstance(data_types, list) else data_types
            valid_types = self.data_types()
            data_types1 = []
            for dtype in data_types:
                stndname = self._get_standard_data_type_name(dtype)
                if stndname not in valid_types:
                    logger.warning(
                        f'HydTablesCheck.section(): Data type "{dtype}" is not a valid section data type or '
                        f'not in output - removing.'
                    )
                else:
                    data_types1.append(stndname)
            if not data_types1:
                raise ValueError('No valid data types provided.')
            data_types = data_types1

        return locations, data_types

    def _figure_out_loc_and_data_types_lp(self, locations: str | list[str],
                                          data_types: str | list[str] | None,
                                          filter_by: str) -> tuple[list[str], list[str]]:
        """Figure out the locations and data types to use - long profile edition."""
        # sort out locations and data types
        if not locations:
            raise ValueError('No locations provided.')
        else:
            valid_loc = self.ids(filter_by)
            valid_loc_lower = [x.lower() for x in valid_loc]
            locations1 = []
            locations = [locations] if not isinstance(locations, list) else locations
            for loc in locations:
                if loc.lower() not in valid_loc_lower:
                    logger.warning(f'INFO.section(): Location "{loc}" not found in the output - removing.')
                else:
                    locations1.append(valid_loc[valid_loc_lower.index(loc.lower())])
            locations = locations1
            if not locations:
                raise ValueError('No valid locations provided.')

        if not data_types:
            data_types = self.data_types('section')
        else:
            data_types = [data_types] if not isinstance(data_types, list) else data_types
            valid_types = self.data_types('section')
            data_types1 = []
            for dtype in data_types:
                if self._get_standard_data_type_name(dtype) not in valid_types:
                    logger.warning(
                        f'INFO.section(): Data type "{dtype}" is not a valid section data type or '
                        f'not in output - removing.'
                    )
                else:
                    data_types1.append(dtype)
            if not data_types1:
                raise ValueError('No valid data types provided.')
            data_types = data_types1

        return locations, data_types
