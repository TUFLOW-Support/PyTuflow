from pathlib import Path

try:
    from netCDF4 import Dataset
    has_nc = True
except ImportError:
    Dataset = 'Dataset'
    has_nc = False

try:
    from osgeo import gdal
    has_gdal = True
except ImportError:
    gdal = None
    has_gdal = False

from .helpers.mesh_driver_qgis_nc import QgisNcMeshDriver
from .helpers.mesh_driver_nc_nc import NCMeshDriverNC
from .mesh import Mesh
from .._pytuflow_types import PathLike
from ..results import ResultTypeError

from .pymesh import PyNCMesh


class NCMesh(Mesh):
    """Class for handling TUFLOW FV style output files.

    The ``NCMesh`` class supports both QGIS and Python drivers. The drivers are also split between geometry handling and
    data extraction.

    If using Python libraries, the ``NCMesh`` class is initialised without loading the mesh geometry data. This
    makes the class cheap to initialise and allows querying of available data types and times without requiring
    mesh loading. The mesh geometry data is only loaded when required for spatial data extraction.

    QGIS libraries can be used for geometry handling and Python libraries can be used for data extraction, this also
    allows for the cheap initialisation of the class. If QGIS libraries are used for both geometry and data extraction,
    the mesh geometry data is loaded at initialisation.

    Parameters
    ----------
    fpath : PathLike
        Path to the NetCDF file.
    driver: str, optional
       The driver to use for reading the NCMesh file. Options are:

       - ``"v1.0"``: Use PyTUFLOW v1.0 NCMesh reader (legacy). This uses old QGIS geometry and extraction methods.
       - ``"v1.1"``: Use PyTUFLOW v1.1 NCMesh reader (default). Uses Python geometry handling if available, otherwise uses
         ``QGIS`` geometry. For data extraction, the order of preference is ``h5py``, ``netcdf4``, then ``QGIS``.
       - ``"qgis geometry [data extractor]"``: Use QGIS libraries for geometry (``"qgis geometry"``) and the optional
         use of QGIS for data extraction as well (``"qgis geometry data extractor"``). If only ``"qgis geometry"`` is
         provided, the data extraction can also use Python libraries if available e.g. ``"qgis geometry netcdf4"`` or
         ``"qgis geometry h5py"``. Using NetCDF4 or h5py for data extraction allows for cheap initialisation of the class.
       - ``"netcdf4"``: Use NetCDF4 library for extracting data. Can be used with ``"qgis geometry"`` otherwise
          uses Python libraries for geometry handling.
       - ``"h5py"``: Use h5py library for extracting data. Can be used with ``"qgis geometry"`` otherwise
         uses Python libraries for geometry handling.

    Examples
    --------
    >>> from pytuflow import NCMesh
    >>> nc = NCMesh('./path/to/nc')

    Get all the data types available in the NetCDF file:

    >>> nc.data_types()
    ['bed level', 'velocity', 'water level', 'salinity', 'temperature']

    Get all the times available in the NetCDF file:

    >>> nc.times()
    [0.0, 0.5, ..., 3.0]

    Get the water level time-series data for a given point defined in a shapefile:

    >>> nc.time_series('path/to/shapefile.shp', 'water level')
        time  pnt1/water level
    0.000000               NaN
    0.083333               NaN
    0.166667               NaN
    0.250000               NaN
    0.333333               NaN
    0.416667               NaN
    0.500000               NaN
    0.583333               NaN
    0.666667         41.561204
    0.750000         41.838923
    ...                    ...
    2.666667         41.278006
    2.750000         41.239387
    2.833334         41.201996
    2.916667         41.166462
    3.000000         41.128152

    Get the depth-averaged velocity time-series using the Sigma method:

    >>> nc.time_series('path/to/shapefile.shp', 'velocity', averaging_method='sigma&0.1&0.9')
    time      pnt1/velocity
    0.000000       0.353553
    0.016667       0.353553
    0.033333       0.353553
    0.050000       0.353553
    0.066667       0.353553
    0.083333       0.353553

    Get water level section data using a shapefile:

    >>> nc.section('path/to/shapefile.shp', 'water level', 1.0)
          line1
         offset water level
    0  0.000000         0.1
    1  0.605553         0.1
    2  0.605553         0.2
    3  1.614808         0.2
    4  1.614808         0.3
    5  2.220360         0.3

    Get a velocity curtain plot using a shapefile:

    >>> nc.curtain('path/to/shapefile.shp', 'velocity', 0.5)
           line1
               x    y  velocity
    0   0.000000  0.0  0.282843
    1   0.605553  0.0  0.282843
    2   0.605553  0.5  0.282843
    3   0.000000  0.5  0.282843
    4   0.000000  0.5  0.424264
    5   0.605553  0.5  0.424264
    6   0.605553  1.0  0.424264
    7   0.000000  1.0  0.424264
    8   0.605553  0.0  0.565685
    9   1.614808  0.0  0.565685
    10  1.614808  0.5  0.565685
    11  0.605553  0.5  0.565685
    12  0.605553  0.5  0.707107
    13  1.614808  0.5  0.707107
    14  1.614808  1.0  0.707107
    15  0.605553  1.0  0.707107
    16  1.614808  0.0  0.848528
    17  2.220360  0.0  0.848528
    18  2.220360  0.5  0.848528
    19  1.614808  0.5  0.848528
    20  1.614808  0.5  0.989949
    21  2.220360  0.5  0.989949
    22  2.220360  1.0  0.989949
    23  1.614808  1.0  0.989949

    Get a velocity (vertical) profile plot using a point shapefile:

    >>> nc.profile('path/to/shapefile.shp', 'velocity', 0.5)
           pnt1
      elevation  velocity
    0       0.0  0.282843
    1       0.5  0.282843
    2       0.5  0.424264
    3       1.0  0.424264
    """

    def __init__(self, fpath: PathLike, driver: str = 'v1.1'):
        if not Path(fpath).exists():
            raise FileNotFoundError(f'File does not exist: {fpath}')
        if not self._looks_like_this(Path(fpath)):
            raise ResultTypeError(f'File does not look like a NetCDF Mesh result file: {fpath}')
        
        super().__init__(fpath)

        if driver.lower() == 'v1.0':
            geom_driver = 'qgis'
            engine = 'qgis'
        elif driver.lower() == 'v1.1':  # PyNCMesh will choose best available
            geom_driver = None
            engine = None
        else:
            geom_driver = 'qgis' if 'qgis geometry' in driver.lower() else None
            engine = 'qgis' if 'qgis data extractor' in driver.lower() or 'qgis geometry data extractor' in driver.lower() else None
            if 'h5py' in driver.lower():
                engine = 'h5py'
            elif 'netcdf4' in driver.lower():
                engine = 'netcdf4'

        if driver.lower() == 'v1.0':
            self._driver = QgisNcMeshDriver(self.fpath)
            self._soft_load_driver = NCMeshDriverNC(self.fpath)
            if self._soft_load_driver.valid:
                self._driver.spherical = self._soft_load_driver.spherical
        else:
            self._driver = PyNCMesh(self.fpath, geom_driver, engine)
            self._soft_load_driver = self._driver

        self._initial_load()

    @staticmethod
    def _looks_like_this(fpath: Path) -> bool:
        if fpath.suffix.lower() != '.nc':
            return False
        try:
            if has_nc:
                with Dataset(fpath, 'r') as nc:
                    if 'Type' in nc.ncattrs() and nc.getncattr('Type') == 'Cell-centred TUFLOWFV output':
                        return True
            elif has_gdal:
                ds = gdal.Open(str(fpath))
                attr = ds.GetMetadata()
                type_ = attr.get('NC_GLOBAL#Type', '')
                if type_ == 'Cell-centred TUFLOWFV output':
                    return True
                ds = None
            else:
                with open(fpath, "rb") as f:
                    head = f.read(8192).decode("latin1", errors="ignore")
                if "Cell-centred TUFLOWFV output" in head:
                    return True
        except Exception:
            return False

        return False

