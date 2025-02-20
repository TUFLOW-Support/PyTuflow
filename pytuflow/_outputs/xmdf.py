from pathlib import Path

from .helpers.mesh_driver_qgis_xmdf import QgisXmdfMeshDriver
from .helpers.super_file import SuperFile
from .mesh import Mesh
from .._pytuflow_types import PathLike
from ..results import ResultTypeError


class XMDF(Mesh):
    """Class for handling XMDF output files.

    Currently, the class uses QGIS drivers for loading the mesh and XMDF files, it is therefore a requirement to
    be working in a QGIS environment and have QGIS initialised before using this class.

    Parameters
    ----------
    fpath : PathLike
        Path to the XMDF file, or XMDF SUP file.
    twodm : PathLike, optional
        Path to the 2dm file. If not provided, the class will attempt to find the 2dm file with the same name as the
        XMDF file. If an XMDF SUP file is provided in the first argument, the 2dm argument is not used.

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

    Get velocity time-series using all the points within a shapefile:

    >>> xmdf.time_series('path/to/shapefile.shp', 'vel')
        time  pnt1/velocity
    0.000000            NaN
    0.083333            NaN
    0.166667            NaN
    0.250000            NaN
    0.333333            NaN
    0.416667            NaN
    0.500000            NaN
    0.583333            NaN
    0.666667       0.975577
    0.750000       0.914921
    ...                 ...
    2.666667       0.320217
    2.750000       0.270925
    2.833334       0.233793
    2.916667       0.206761
    3.000000       0.183721

    Get the bed level and max water level data using a shapefile to define the location:

    >>> xmdf.section('path/to/shapefile.shp', ['bed level', 'max h'], -1)
           Line_1                                 Line_2
           offset  bed level max water level      offset  bed level max water level
    0    0.000000  43.646312             NaN    0.000000  43.112894             NaN
    1    0.145704  43.645835             NaN    2.213407  43.088104             NaN
    2    2.801012  43.647998             NaN    6.926959  43.035811             NaN
    3    7.819650  43.643313             NaN   11.926842  42.987500             NaN
    4   12.838279  43.634620             NaN   16.926803  42.950000             NaN
    5   17.856980  43.626645             NaN   21.926729  42.916000             NaN
    6   22.875678  43.615949             NaN   26.926655  42.888000             NaN
    7   25.941652  43.611225             NaN   31.926952  42.865499             NaN
    8   28.451249  43.603039             NaN   36.926835  42.846001             NaN
    9   32.913571  43.591435             NaN   41.926869  42.829500             NaN
    10  37.932185  43.578406             NaN   46.926830  42.812500             NaN
    11  42.950809  43.569102             NaN   51.926756  42.795000       42.443355
    12  47.969530  43.577088             NaN   56.926682  42.777190       42.443967
    13  52.988495  43.666201             NaN   61.926643  42.760000       42.444545
    14  58.007149  43.773129             NaN   66.926940  42.744000       42.445528
    15  63.026036  43.897195             NaN   71.926823  42.730500       42.447615
    16  68.044737  43.612406             NaN   76.926857  42.719000       42.449872
    17  73.063420  42.849014       42.834780   81.926818  42.708500       42.452022
    """

    def __init__(self, fpath: PathLike, twodm: PathLike = None):
        if Path(fpath).suffix.lower() == '.sup':
            sup = SuperFile(fpath)
            fpath = Path(fpath).parent / sup['DATA']
            self.twodm = Path(fpath).parent / Path(sup['MESH2D'])
        else:
            self.twodm = Path(twodm) if twodm else self._find_2dm(fpath)

        if not Path(fpath).exists():
            raise FileNotFoundError(f'XMDF file does not exist: {fpath}')
        if not self.twodm.exists():
            raise FileNotFoundError(f'2dm file does not exist: {self.twodm}')
        if not self._looks_like_this(Path(fpath)):
            raise ResultTypeError(f'File does not look like an XMDF file: {fpath}')

        super().__init__(self.twodm)
        self.fpath = Path(fpath)
        self._driver = QgisXmdfMeshDriver(self.twodm, self.fpath)
        self._load()

    @staticmethod
    def _find_2dm(xmdf: PathLike) -> Path:
        p = Path(xmdf).with_suffix('.2dm')
        if not p.exists():
            raise FileNotFoundError(f'2dm file does not exist: {p}')
        return p

    @staticmethod
    def _looks_like_this(fpath: Path) -> bool:
        return fpath.suffix.lower() == '.xmdf'
