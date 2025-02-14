from pathlib import Path

import numpy as np

from pytuflow.pytuflow_types import PathLike, TimeLike
from .fv_bc_tide_gis_provider import FVBCTideGISProvider
from .fv_bc_tide_nc_provider import FVBCTideNCProvider
from pytuflow.util.gis import has_gdal

try:
    import shapely
    has_shapely = True
except ImportError:
    has_shapely = False


class FVBCTideProvider:
    """Class for providing FV BC tide data to the FVBCTide result class."""

    def __init__(self, nc_path: PathLike, gis_path: PathLike, use_local_time: bool = True) -> None:
        """
        Parameters
        ----------
        nc_path : PathLike
            Path to the netCDF file.
        gis_path : PathLike
            Path to the node string GIS file.
        label: str
            The boundary label / name within the netCDF file.
        """
        if not has_shapely:
            raise ImportError('Shapely is required for FVBCTideProvider')
        if not has_gdal:
            raise ImportError('GDAL is required for FVBCTideProvider')
        self.display_name = ''
        self.reference_time = None
        self.nc = FVBCTideNCProvider(nc_path, use_local_time)
        self.gis = FVBCTideGISProvider(gis_path)
        self.load()

    def __del__(self) -> None:
        self.close()

    def __repr__(self) -> str:
        return f'FVBCTideProvider({self.nc.path.name}, {self.gis.path.name})'

    def load(self) -> None:
        """Loads the data from the netCDF and GIS files."""
        self.nc.open()
        self.gis.open()
        self.name = Path(self.nc.path).stem
        self.display_name = f'{self.name}[TZ:{self.nc.tz}]'
        self.reference_time = self.nc.reference_time
        self.gis_name = self.gis.name

    def close(self) -> None:
        """Closes the netCDF and GIS files."""
        self.nc.close()
        self.gis.close()

    def is_empty(self) -> bool:
        """Returns True if the netCDF or GIS files are empty.

        Returns
        -------
        bool
        """
        return self.nc.is_empty() or self.gis.is_empty()

    def is_fv_tide_bc(self) -> bool:
        """Returns True if the inputs look like FV tide boundary conditions.

        Returns
        -------
        bool
        """
        return self.nc.is_fv_tide_bc() and self.gis.is_fv_tide_bc()

    def get_crs(self) -> str:
        """Returns the CRS of the GIS file in the form of AUTHORITY:CODE.

        Returns
        -------
        str
        """
        return self.gis.get_crs()

    def number_of_points(self, label: str) -> int:
        """Returns the number of points along the node string for the given label.

        Parameters
        ----------
        label : str
            The boundary label / name within the GIS file.

        Returns
        -------
        int
        """
        return self.nc.number_of_points(label)

    def get_ch_points(self, label: str) -> np.ndarray:
        """Returns the chainage as points along the node string GIS file from the
        FV Tide boundary based on the chainage values in the netCDF file.

        Returns a 2D array of shape (n, 2) where n is the number of points.

        Returns
        -------
        np.ndarray
        """
        return self.gis.get_ch_points(label, self.nc.get_chainages(label))

    def get_timesteps(self, fmt: str = 'relative') -> np.ndarray:
        """Returns the timesteps from the netCDF file. Returns from 'local_time' if available, otherwise
        returns from 'time'. The time format can be 'relative' (default) or 'datetime'/'absolute'.

        Returns a 1D array of shape (n,) where n is the number of timesteps.

        Parameters
        ----------
        fmt : str, optional
            The format of the timesteps. Default is 'relative'.

        Returns
        -------
        np.ndarray
        """
        return self.nc.get_timesteps(fmt)

    def get_section(self, label: str, time: TimeLike, data_at_ends: bool = False) -> np.ndarray:
        """Returns section data (i.e. long profile data) for a given time. Time can be passed in as
        either a float (relative time) or a datetime object.

        Returns a 2D array of shape (n, 2) where n is the number of points.

        Parameters
        ----------
        label : str
            The boundary name / label to get data for.
        time : float or datetime
            The time of the section data.
        data_at_ends : bool, optional
            If True, will ensure there are data points at the start and end of the line (will be set to nan
            if it is added).

        Returns
        -------
        np.ndarray
        """
        section = self.nc.get_section(label, time)
        if data_at_ends:
            if not np.isclose(section[0, 0], 0, rtol=0.):
                section = np.insert(section, 0, [[0, np.nan]], axis=0)
            length = self.gis.get_length(label)
            if not np.isclose(section[-1, 0], length, rtol=0.001):
                section = np.append(section, [[length, np.nan]], axis=0)
        return section

    def get_time_series(self, label: str, point_ind: int, time_fmt: str = 'relative') -> np.ndarray:
        """Returns time series data at a given point index. The time format can be 'relative' (default) or 'datetime'.

        Returns a 2D array of shape (n, 2) where n is the number of timesteps.

        Parameters
        ----------
        point_ind : int
            The index of the point.
        time_fmt : str, optional
            The format of the timesteps. Default is 'relative'.

        Returns
        -------
        np.ndarray
        """
        return self.nc.get_time_series(label, point_ind, time_fmt)

    def get_time_series_data_raw(self, label: str) -> np.ndarray:
        """Returns the time series data for the given label as the raw numpy array extracted
        from the netCDF file.

        Parameters
        ----------
        label : str
            The boundary label / name within the netCDF file.

        Returns
        -------
        np.ndarray
        """
        return self.nc.get_time_series_data_raw(label)

    def get_geometry(self, label: str) -> bytes:
        """Returns the geometry of the GIS line in a WKB format.

        Returns
        -------
        bytes
        """
        return self.gis.get_geometry(label)

    def get_labels(self) -> list[str]:
        """Returns the boundary labels in the netCDF file.

        Returns
        -------
        list[str]
        """
        return self.nc.labels
