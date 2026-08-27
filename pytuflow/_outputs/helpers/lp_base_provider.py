from pathlib import Path
import numpy as np

from ..._pytuflow_types import PathLike, TuflowPath, TimeLike


class LongProfileBaseProvider:

    def __init__(self, fpath: PathLike, gis_fpath: PathLike | None, *args, **kwargs):
        self.fpath = Path(fpath)
        self.gis_fpath = TuflowPath(gis_fpath) if gis_fpath else None
        self.name = ''
        self.display_name = ''
        self.gis_name = ''
        self.reference_time = None
        self.provider = None
        self.gis_provider = None

    def __repr__(self) -> str:
        pretty_name = ''
        if self.provider and self.provider.is_valid():
            pretty_name = self.provider.name
        if self.gis_provider and self.gis_provider.is_valid():
            pretty_name = f'{pretty_name}, {self.gis_provider.name}'
        return f'{self.__class__.__name__}({pretty_name})'

    def is_empty(self) -> bool:
        """Returns True if the netCDF or GIS files are empty.

        Returns
        -------
        bool
        """
        if self.provider and self.provider.is_valid() and not self.provider.is_empty():
            return False
        return True

    def is_valid(self) -> bool:
        if not self.provider or not self.provider.is_valid():
            return False
        if self.gis_provider and not self.gis_provider.is_valid():
            return False
        return True

    def get_crs(self) -> str:
        """Returns the CRS of the GIS file in the form of AUTHORITY:CODE.

        Returns
        -------
        str
        """
        return self.gis_provider.crs if self.gis_provider else ''

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
        return self.provider.number_of_points(label)

    def get_ch_points(self, label: str) -> np.ndarray:
        """Returns the chainage as points along the node string GIS file from the
        FV Tide boundary based on the chainage values in the netCDF file.

        Returns a 2D array of shape (n, 2) where n is the number of points.

        Returns
        -------
        np.ndarray
        """
        if not self.gis_provider:
            raise ValueError('GIS line/nodestring file required to get chainage points along the line.')
        if not self.gis_provider.is_valid():
            raise ValueError('GIS line/nodestring is not valid.')
        return self.gis_provider.get_ch_points(label, self.provider.get_chainages(label))

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
        return self.provider.get_timesteps(fmt)

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
        section = self.provider.get_section(label, time)
        if data_at_ends:
            if not np.isclose(section[0, 0], 0, rtol=0.):
                section = np.insert(section, 0, np.array([[0, np.nan]]), axis=0)
            if self.gis_provider and self.gis_provider.is_valid():
                length = self.gis_provider.get_length(label)
                if not np.isclose(section[-1, 0], length, rtol=0.001):
                    section = np.append(section, np.array([[length, np.nan]]), axis=0)
        return section

    def get_time_series(self, label: str, point_ind: int, time_fmt: str = 'relative') -> np.ndarray:
        """Returns time series data at a given point index. The time format can be 'relative' (default) or 'datetime'.

        Returns a 2D array of shape (n, 2) where n is the number of timesteps.

        Parameters
        ----------
        label : str
            The boundary label / name within the netCDF file.
        point_ind : int
            The index of the point.
        time_fmt : str, optional
            The format of the timesteps. Default is 'relative'.

        Returns
        -------
        np.ndarray
        """
        return self.provider.get_time_series(label, point_ind, time_fmt)

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
        return self.provider.get_time_series_data_raw(label)

    def get_geometry(self, label: str) -> bytes:
        """Returns the geometry of the GIS line in a WKB format.

        Returns
        -------
        bytes
        """
        if not self.gis_provider:
            raise ValueError('GIS line/nodestring file required to get geometry.')
        if not self.gis_provider.is_valid():
            raise ValueError('GIS line/nodestring is not valid.')
        return self.gis_provider.get_geometry(label)

    def get_labels(self) -> list[str]:
        """Returns the boundary labels in the netCDF file.

        Returns
        -------
        list[str]
        """
        return self.provider.labels
