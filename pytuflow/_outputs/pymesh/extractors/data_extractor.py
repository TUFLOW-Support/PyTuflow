from datetime import datetime
import contextlib

import numpy as np


class PyDataExtractor:
    """Base class for extracting data from the mesh format."""
    SliceType = int | slice | list[int]
    MultiSliceType = tuple[SliceType, SliceType]
    Name = 'PyDataExtractor'

    @contextlib.contextmanager
    def open(self):
        """Context manager for opening and closing the data extractor."""
        yield self

    def times(self, data_type: str) -> np.ndarray:
        """Return all times for a given data type.

        Parameters
        ----------
        data_type : str
            The data type to extract times for.

        Returns
        -------
        np.ndarray
            The times for a given data type.
        """
        raise NotImplementedError

    def data_types(self) -> list[str]:
        """Return all data types available for this extractor. Temporal data will have any directory path
        removed from the name, by others won't e.g. 'Depth' and 'Maximums/Depth'.

        Returns
        -------
        list[str]
            The data types available for this extractor.
        """
        raise NotImplementedError

    def reference_time(self, data_type: str) -> datetime:
        """Return the reference time for a given data_type. If a reference time is present, ``None`` will
        be returned.

        Parameters
        ----------
        data_type : str
            The data type to extract the reference time for.

        Returns
        -------
        datetime
            The reference time for the given data type.
        """
        raise NotImplementedError

    def spherical(self) -> bool:
        """Returns whether the mesh is in spherical coordinates.

        Returns
        -------
        bool
            True if the mesh is in spherical coordinates, False if it is in Cartesian coordinates.
        """
        return False

    def is_vector(self, data_type: str) -> bool:
        """Returns whether the given data_type is a vector.

        Parameters
        ----------
        data_type : str
            The data_type to check whether it is a vector.

        Returns
        -------
        bool
            True if the data_type is a vector, False if it is a scalar.
        """
        raise NotImplementedError

    def is_static(self, data_type: str) -> bool:
        """Returns whether the given data_type is static (i.e. does not vary with time).

        Parameters
        ----------
        data_type : str
            The data_type to check whether it is static.

        Returns
        -------
        bool
            True if the data_type is static, False if it varies with time.
        """
        return len(self.times(data_type)) == 0

    def is_3d(self, data_type: str) -> bool:
        """Returns whether the given data_type is 3D.

        Parameters
        ----------
        data_type : str
            The data_type to check whether it is 3D.

        Returns
        -------
        bool
            True if the data_type is 3D, False if it is 2D.
        """
        return False

    def maximum(self, data_type: str) -> float:
        """Returns the maximum value for the given data type.

        Parameters
        ----------
        data_type : str
            The data_type to return the maximum values for.

        Returns
        -------
        float
            The maximum value for the given data type. Vectors are usually returned as a scalar as well.
        """
        raise NotImplementedError

    def minimum(self, data_type: str) -> float:
        """Returns the minimum value for the given data type.

        Parameters
        ----------
        data_type : str
            The data_type to return the minimum values for.

        Returns
        -------
        float
            The minimum value for the given data type. Vectors are usually returned as a scalar as well.
        """
        raise NotImplementedError

    def data(self, data_type: str, index: SliceType | MultiSliceType) -> np.ndarray:
        """Returns the data for the given data type and index.The index can be a single slice i.e. an integer
        or slice(), or a 2D slice i.e. a tuple[int | slice(), ...].

        Parameters
        ----------
        data_type : str
            The data_type to extract the wet/dry flag for.
        index : SliceType | MultiSliceType
            The index to extract the wet/dry flag for. Can be a single slice or a 2D slice.

        Returns
        -------
        np.ndarray
            The data for the given data_type and index.
        """
        raise NotImplementedError

    def wd_flag(self, data_type: str, index: SliceType | MultiSliceType) -> np.ndarray:
        """Returns the wet/dry flag for the given data type and index. The index can be a single slice i.e. an integer
        or slice(), or a 2D slice i.e. a tuple[int | slice(), ...].

        Parameters
        ----------
        data_type : str
            The data_type to extract the wet/dry flag for.
        index : SliceType | MultiSliceType
            The index to extract the wet/dry flag for. Can be a single slice or a 2D slice.

        Returns
        -------
        np.ndarray
            The wet/dry flag for the given data_type and index.
        """
        raise NotImplementedError

    def on_vertex(self, data_type: str) -> bool:
        return True

    def cell_index(self, cell_id: int | list[int] | np.ndarray, data_type: str) -> np.ndarray:
        return np.array([cell_id])

    def zlevel_count(self, cell_idx2: int | np.ndarray | list[int]) -> int | np.ndarray | list[int]:
        raise NotImplementedError

    def zlevels(self, time_index: int, nlevels: int, cell_idx2: int | np.ndarray,
                cell_idx3: int | np.ndarray) -> np.ndarray:
        raise NotImplementedError
