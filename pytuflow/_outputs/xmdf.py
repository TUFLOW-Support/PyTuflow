from pathlib import Path

from .helpers.mesh_driver_qgis_xmdf import QgisXmdfMeshDriver
from .mesh import Mesh
from .._pytuflow_types import PathLike


class XMDF(Mesh):
    """Class for handling XMDF output files.

    Currently, the class uses QGIS drivers for loading the mesh and XMDF files, it is therefore a requirement to
    be working in a QGIS environment and have QGIS initialised before using this class.

    Parameters
    ----------
    fpath : PathLike
        Path to the XMDF file.
    twodm : PathLike, optional
        Path to the 2dm file. If not provided, the class will attempt to find the 2dm file with the same name as the
        XMDF file.

    Examples
    --------
    >>> from pytuflow import XMDF
    >>> xmdf = XMDF('./path/to/xmdf')

    Get all the data types available in the XMDF file:

    >>> xmdf.data_types()
    ['bed level', 'depth', 'vector velocity', 'velocity', 'water level', 'time of peak h']

    Get all the data types that have maximum values:

    >>> xmdf.data_types('max')
    ['depth', 'vector velocity', 'velocity', 'water level']

    Get all the available times in the XMDF file:

    >>> xmdf.times()
    [0.0, 0.016666666666666666, ..., 3.0]

    Get the water level time-series data for a given point defined as ``(x, y)``:

    >>> xmdf.time_series((293250, 6178030), 'water level')
            time  pnt1/water level
    0   0.000000               NaN
    1   0.083333               NaN
    2   0.166667               NaN
    3   0.250000               NaN
    4   0.333333               NaN
    5   0.416667               NaN
    6   0.500000               NaN
    7   0.583333               NaN
    8   0.666667         41.561204
    9   0.750000         41.838923
    ...    ...                 ...
    32  2.666667         41.278006
    33  2.750000         41.239387
    34  2.833334         41.201996
    35  2.916667         41.166462
    36  3.000000         41.128152

    Get velocity time-series of the points with a shapefile:

    >>> xmdf.time_series('path/to/shapefile.shp', 'vel')
            time  pnt1/velocity
    0   0.000000            NaN
    1   0.083333            NaN
    2   0.166667            NaN
    3   0.250000            NaN
    4   0.333333            NaN
    5   0.416667            NaN
    6   0.500000            NaN
    7   0.583333            NaN
    8   0.666667       0.975577
    9   0.750000       0.914921
    ...    ...              ...
    32  2.666667       0.320217
    33  2.750000       0.270925
    34  2.833334       0.233793
    35  2.916667       0.206761
    36  3.000000       0.183721
    """

    def __init__(self, fpath: PathLike, twodm: PathLike = None):
        self.twodm = Path(twodm) if twodm else self.find_2dm(fpath)
        super().__init__(self.twodm)
        self.fpath = Path(fpath)
        self._driver = QgisXmdfMeshDriver(self.twodm, self.fpath)
        self._load()

    @staticmethod
    def find_2dm(xmdf: PathLike) -> Path:
        p = Path(xmdf).with_suffix('.2dm')
        if not p.exists():
            raise FileNotFoundError(f'2dm file does not exist: {p}')
        return p
