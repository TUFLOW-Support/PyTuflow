import numpy as np

try:
    import shapely

    has_shapely = True
except ImportError:
    shapely = 'shapely'
    has_shapely = False

try:
    from osgeo import ogr

    has_gdal = True
except ImportError:
    from ...stubs import ogr_ as ogr

    has_gdal = False

from ..._pytuflow_types import PathLike, TuflowPath
from ...util import geom as geom_util, gis


class LongProfileGIS:
    """Base class for handling a long profile GIS line/file. This can be a 2d_LP from HPC,
    or an FV BC Tide boundary line, etc.

    Parameters
    ----------
    path : PathLike
        Path to the GIS file.
    id_col_name : str
        The name of the ID attribute/column to use in the GIS file.
    """

    def __init__(self, path: PathLike, id_col_name: str) -> None:
        if not has_shapely:
            raise ImportError('Shapely is not installed, unable to initialise LongProfileGIS class.')
        #: Path: Path to the GIS file.
        self.path = TuflowPath(path) if path else None
        #: str: Name of the GIS layer.
        self.name = self.path.lyrname if self.path else ''
        #: str: Name of the column to be used for the line IDs
        self.id_col_name = id_col_name
        #: dict[str, Feature]: Dictionary of features in the GIS file, keyed by the ID column value.
        self.feats = {}
        self._feats_lower = {}
        self.crs = None
        self.geometry_type = None
        self._points = {}
        self.load()

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.name})'

    def load(self):
        if self.path:
            with self.path.open_gis() as fo:
                self.feats = {x[self.id_col_name]: x for x in fo}
                self.crs = fo.crs()
                self.geometry_type = fo.geometry_type

    def is_empty(self) -> bool:
        """Returns True if the GIS file is empty.

        Returns
        -------
        bool
        """
        return len(self.feats) == 0

    def is_valid(self) -> bool:
        """Returns True if the GIS file looks like a FV node string boundary layer.

        Returns
        -------
        bool
        """
        return self.geometry_type in ['LineString', 'MultiLineString']

    def get_labels(self) -> list[str]:
        """Returns the list of boundary labels in the GIS file.

        Returns
        -------
        list[str]
        """
        return list(self.feats.keys())

    def get_ch_points(self, label: str, chainages: np.ndarray) -> np.ndarray:
        """Returns the chainage points for the given label.

        Parameters
        ----------
        label : str
            The boundary label / name within the GIS file.
        chainages : np.ndarray
            Chainages along the node string.

        Returns
        -------
        np.ndarray
        """
        if self.is_empty():
            return np.array([])
        if self._points.get(label.lower()) is None:
            feat = self._get_feat(label)
            if feat is None:
                return np.array([])
            if feat.geometry_type == 'LineString':
                linestring = shapely.LineString(feat.geom.lines()[0])
            elif feat.geometry_type == 'MultiLineString':
                linestring = shapely.MultiLineString(feat.geom.lines())
            else:
                raise ValueError(f'Geometry type not supported for FV BC Tide GIS provider: {feat.geometry_type}')

            try:
                is_projected = self.crs.is_projected
            except Exception:
                is_projected = self.crs.IsProjected()

            if not is_projected:
                length = self.get_length(label)
                chainages = chainages / length
                points = np.array([linestring.interpolate(x, normalized=True).xy for x in chainages])
            else:
                points = np.array([linestring.interpolate(x).xy for x in chainages])

            if len(points.shape) == 3:
                points = points.reshape((points.shape[0], points.shape[1]))

            chs = np.reshape(chainages, (chainages.size, 1))
            points = np.append(chs, points, axis=1)
            self._points[label.lower()] = points
        return self._points.get(label.lower())

    def get_geometry(self, label: str) -> bytes:
        """Returns the geometry object as a wkbGeometry for the given label.

        Parameters
        ----------
        label : str
            The boundary label / name within the GIS file.

        Returns
        -------
        bytes
        """
        if self.is_empty():
            return b''
        feat = self._get_feat(label)
        if feat is None:
            return b''
        return feat.geom.to_wkb()

    def get_length(self, label: str) -> float:
        """Returns the length of the GIS line in meters.

        Parameters
        ----------
        label : str
            The boundary label / name within the GIS file.

        Returns
        -------
        float
        """
        if self.is_empty():
            return 0.
        feat = self._get_feat(label)
        if feat is None:
            return 0.

        if feat.geometry_type == 'LineString':
            linestring = shapely.LineString(feat.geom.lines()[0])
        elif feat.geometry_type == 'MultiLineString':
            linestring = shapely.MultiLineString(feat.geom.lines())
        else:
            raise ValueError(f'Geometry type not supported for FV BC Tide GIS provider: {feat.geometry_type}')

        try:
            is_projected = self.crs.is_projected
        except Exception:
            is_projected = self.crs.IsProjected()

        if not is_projected:
            x, y = linestring.xy
            points = list(zip(x.tolist(), y.tolist()))
            return geom_util.calc_spherical_length(points)
        return linestring.length

    def _get_feat(self, label: str) -> gis.Feature:
        if not self._feats_lower:
            self._feats_lower = {key.lower(): x for key, x in self.feats.items()}
        return self._feats_lower.get(label.lower())
