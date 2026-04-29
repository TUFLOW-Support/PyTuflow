from pathlib import Path
import numpy as np

from ..._pytuflow_types import PathLike, TimeLike
from .lp_base_provider import LongProfileBaseProvider
from .fv_bc_tide_gis_provider import FVBCTideGISProvider
from .fv_bc_tide_nc_provider import FVBCTideNCProvider

try:
    import shapely
    has_shapely = True
except ImportError:
    shapely = 'shapely'
    has_shapely = False


from ...util import pytuflow_logging
logger = pytuflow_logging.get_logger()


class FVBCTideProvider(LongProfileBaseProvider):
    """Class for providing FV BC tide data to the FVBCTide result class.

    Parameters
    ----------
    nc_path : PathLike
        Path to the netCDF file.
    gis_path : PathLike
        Path to the node string GIS file.
    use_local_time : bool
        Use local time from the NetCDF file if it exists. If local time does not exist, UTC will be used.
        Default is True.
    """

    def __init__(self, nc_path: PathLike, gis_path: PathLike, use_local_time: bool = True) -> None:
        super().__init__(nc_path, gis_path)
        if not has_shapely:
            raise ImportError('Shapely is required for FVBCTideProvider')
        self.reference_time = None
        self.provider = FVBCTideNCProvider(nc_path, use_local_time)
        self.gis_provider = FVBCTideGISProvider(gis_path)
        self.load()

    def __del__(self) -> None:
        self.close()

    def load(self) -> None:
        """Loads the data from the netCDF and GIS files."""
        self.provider.open()
        nc_labels = set(self.provider.labels)
        gis_labels = set(self.gis_provider.get_labels())
        inter = nc_labels.intersection(gis_labels)
        if len(inter) != len(nc_labels) or len(inter) != len(gis_labels):
            logger.warning(
                f'Boundary labels in netCDF and GIS files do not match. netCDF labels: {nc_labels if nc_labels else "{}"}, GIS labels: {gis_labels if gis_labels else "{}"}'
            )
        self.name = Path(self.provider.path).stem
        self.display_name = f'{self.name}[TZ:{self.provider.tz}]'
        self.reference_time = self.provider.reference_time
        self.has_reference_time = self.provider.has_reference_time
        self.gis_name = self.gis_provider.name

    def close(self) -> None:
        """Closes the netCDF and GIS files."""
        self.provider.close()

    def is_fv_tide_bc(self) -> bool:
        """Returns True if the inputs look like FV tide boundary conditions.

        Returns
        -------
        bool
        """
        return self.is_valid()
