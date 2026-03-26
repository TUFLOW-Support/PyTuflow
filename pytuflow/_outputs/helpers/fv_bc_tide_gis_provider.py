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
from ...util import geom as geom_util


class FVBCTideGISProvider:
    """Class for providing GIS data to the FVBCTideProvider class."""

    def __init__(self, path: PathLike) -> None:
        """
        Parameters
        ----------
        path : PathLike
            Path to the GIS file.
        """
        if not has_shapely:
            raise ImportError('Shapely is not installed, unable to initialise FVBCTideGISProvider class.')
        #: Path: Path to the GIS file.
        self.path = path
        #: str: Name of the GIS layer.
        self.name = None
        self._fo = None
        self._points = {}

    def __repr__(self) -> str:
        return f'FVBCTideGISProvider({self.path.name})'

    def open(self) -> None:
        """Open the GIS Node String file."""
        p = TuflowPath(self.path)
        self.name = p.lyrname
        self._fo = p.open_gis()

    def close(self) -> None:
        """Closes the GIS Node String file."""
        if self._fo is not None:
            self._fo.close()
            self._fo = None

    def is_empty(self) -> bool:
        """Returns True if the GIS file is empty.

        Returns
        -------
        bool
        """
        return self._fo.feature_count() == 0

    def is_fv_tide_bc(self) -> bool:
        """Returns True if the GIS file looks like a FV node string boundary layer.

        Returns
        -------
        bool
        """
        return self._fo.geometry_type in ['LineString', 'MultiLineString']

    def get_crs(self) -> str:
        """Returns the CRS of the GIS file in the form of AUTHORITY:CODE.

        Returns
        -------
        str
        """
        return self._fo.crs_auth()

    def get_labels(self) -> list[str]:
        """Returns the list of boundary labels in the GIS file.

        Returns
        -------
        list[str]
        """
        if self.is_empty():
            return []
        return [f['ID'] for f in self._fo]

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
            feat = None
            for f in self._fo:
                if f['ID'].lower() == label.lower():
                    feat = f
                    break
            if feat is None:
                return np.array([])
            if feat.geometry_type == 'LineString':
                linestring = shapely.LineString(feat.geom.lines()[0])
            elif feat.geometry_type == 'MultiLineString':
                linestring = shapely.MultiLineString(feat.geom.lines())
            else:
                raise ValueError(f'Geometry type not supported for FV BC Tide GIS provider: {feat.geometry_type}')

            try:
                is_projected = self._fo.crs().is_projected
            except Exception:
                is_projected = self._fo.crs().IsProjected()

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
        feat = None
        for f in self._fo:
            if f['ID'].lower() == label.lower():
                feat = f
                break
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
        feat = None
        for f in self._fo:
            if f['ID'].lower() == label.lower():
                feat = f
                break
        if feat is None:
            return 0.

        if feat.geometry_type == 'LineString':
            linestring = shapely.LineString(feat.geom.lines()[0])
        elif feat.geometry_type == 'MultiLineString':
            linestring = shapely.MultiLineString(feat.geom.lines())
        else:
            raise ValueError(f'Geometry type not supported for FV BC Tide GIS provider: {feat.geometry_type}')

        try:
            is_projected = self._fo.crs().is_projected
        except Exception:
            is_projected = self._fo.crs().IsProjected()

        if not is_projected:
            x, y = linestring.xy
            points = list(zip(x.tolist(), y.tolist()))
            return geom_util.calc_spherical_length(points)
        return linestring.length

    # def _geometry_type(self) -> int:
    #     geom_type = self._fo.geometry_type
    #     while geom_type > 1000:
    #         geom_type -= 1000
    #     return geom_type