from abc import abstractmethod

import pandas as pd

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

    @staticmethod
    def _loc_data_types_to_list(locations: str | list[str] | None,
                                data_types: str | list[str] | None) -> tuple[list[str], list[str]]:
        """Convert locations and data_types to list format."""
        locations = locations if locations is not None else []
        locations = locations if isinstance(locations, list) else [locations]
        data_types = data_types if data_types is not None else []
        data_types = data_types if isinstance(data_types, list) else [data_types]
        return locations, data_types

    def _time_series_filter_by(self,
                               locations: str | list[str] | None,
                               data_types: str | list[str] | None) -> tuple[pd.DataFrame, list[str], list[str]]:
        """similar to _filter, but for time series inputs in preparation for time-series and maximum extraction.
        Performs checks so that the locations and data types are valid.
        """
        self._load()
        locations, data_types = self._loc_data_types_to_list(locations, data_types)
        locations, data_types = self._figure_out_loc_and_data_types(locations, data_types)
        filter_by = '/'.join(locations + data_types)
        return self._filter(filter_by, ignore_excess_filters=True), locations, data_types

    def _figure_out_loc_and_data_types(self, locations: str | list[str],
                                       data_types: str | list[str] | None) -> tuple[list[str], list[str]]:
        """Figure out the locations and data types to use."""
        # sort out locations and data types
        valid_data_types = self.data_types()
        if not locations:
            locations = self.ids()
        else:
            locations1 = []
            locations = [locations] if not isinstance(locations, list) else locations
            for loc in locations:
                if self._get_standard_data_type_name(loc) in valid_data_types:
                    while loc in locations:
                        locations.remove(loc)
                    logger.warning(f'Location "{loc}" is a data type - removing.')
            # ids = {x.lower(): x for x in self.ids()}
            # locations_lower = [x.lower() for x in locations]
            for loc in locations:
                ids = self.ids(loc)
                if not ids:
                    logger.warning(f'Location "{loc}" not found in the output or a valid location filter - removing.')
                else:
                    for id_ in ids:
                        if id_.lower() not in locations1:
                            locations1.append(id_)
            locations = locations1
            if not locations:
                raise ValueError('No valid locations provided.')

        if not data_types:
            data_types = self.data_types()
        else:
            data_types = [data_types] if not isinstance(data_types, list) else data_types
            data_types1 = []
            for dtype in data_types:
                stndname = self._get_standard_data_type_name(dtype)
                if stndname not in valid_data_types:
                    logger.warning(
                        f'Data type "{dtype}" is not a valid section data type or not in output - removing.'
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
                    logger.warning(f'Location "{loc}" not found in the output - removing.')
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
                        f'Data type "{dtype}" is not a valid section data type or '
                        f'not in output - removing.'
                    )
                else:
                    data_types1.append(dtype)
            if not data_types1:
                raise ValueError('No valid data types provided.')
            data_types = data_types1

        return locations, data_types
