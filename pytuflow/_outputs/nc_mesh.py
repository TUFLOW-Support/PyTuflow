from .helpers.mesh_driver_qgis_nc import QgisNcMeshDriver
from .helpers.mesh_driver_nc_nc import NCMeshDriverNC
from .mesh import Mesh
from .._pytuflow_types import PathLike


class NCMesh(Mesh):
    """Class for handling TUFLOW FV style output files.

    The ``NCMesh`` class will only load header information from the NetCDF file on initialisation, this makes the class
    cheap to initialise. The class can be initialised and the methods :meth:`times` and
    :meth:`data_types` can be used without requiring QGIS libraries. However, extracting spatial data requires
    QGIS libraries to be available and QGIS to be initialised. The class will automatically load the full mesh
    the first time a spatial method is called which can cause the first time a spatial method is called to be slow.

    Parameters
    ----------
    fpath : PathLike
        Path to the NetCDF file.

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

    def __init__(self, fpath: PathLike):
        super().__init__(fpath)
        self._driver = QgisNcMeshDriver(self.fpath)
        self._soft_load_driver = NCMeshDriverNC(self.fpath)
        self._initial_load()
