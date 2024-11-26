from pathlib import Path

import numpy as np
import shapely
from osgeo import ogr

from pytuflow.pytuflow_types import PathLike, TuflowPath
from pytuflow.util.gis import get_driver_name_from_extension
from pytuflow.util.geom import calc_spherical_length


class FVBCTideGISProvider:
    """Class for providing GIS data to the FVBCTideProvider class."""

    def __init__(self, path: PathLike) -> None:
        """
        Parameters
        ----------
        path : PathLike
            Path to the GIS file.
        """
        #: Path: Path to the GIS file.
        self.path = path
        #: str: Name of the GIS layer.
        self.name = None
        self._ds = None
        self._lyr = None
        self._points = {}

    def __repr__(self) -> str:
        return f'FVBCTideGISProvider({self.path.name})'

    def open(self) -> None:
        """Open the GIS Node String file."""
        p = TuflowPath(self.path)
        self.name = p.lyrname
        driver_name = get_driver_name_from_extension('vector', p.dbpath.suffix)
        self._ds = ogr.GetDriverByName(driver_name).Open(str(p.dbpath))
        self._lyr = self._ds.GetLayer(self.name)

    def close(self) -> None:
        """Closes the GIS Node String file."""
        self._ds, self._lyr = None, None

    def is_empty(self) -> bool:
        """Returns True if the GIS file is empty.

        Returns
        -------
        bool
        """
        return self._lyr.GetFeatureCount() == 0

    def is_fv_tide_bc(self) -> bool:
        """Returns True if the GIS file looks like a FV node string boundary layer.

        Returns
        -------
        bool
        """
        return self._geometry_type() in [ogr.wkbLineString, ogr.wkbMultiLineString]

    def get_crs(self) -> str:
        """Returns the CRS of the GIS file in the form of AUTHORITY:CODE.

        Returns
        -------
        str
        """
        sr = self._lyr.GetSpatialRef()
        return f'{sr.GetAuthorityName(None)}:{sr.GetAuthorityCode(None)}'

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
            for f in self._lyr:
                if f.GetField('ID').lower() == label.lower():
                    feat = f
                    break
            if feat is None:
                return np.array([])
            geom = feat.GetGeometryRef()
            linestring = shapely.from_wkb(bytes(geom.ExportToWkb()))
            if not self._lyr.GetSpatialRef().IsProjected():
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
        for f in self._lyr:
            if f.GetField('ID').lower() == label.lower():
                feat = f
                break
        if feat is None:
            return b''
        geom = feat.GetGeometryRef()
        return bytes(geom.ExportToWkb())

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
        for f in self._lyr:
            if f.GetField('ID').lower() == label.lower():
                feat = f
                break
        if feat is None:
            return 0.
        geom = feat.GetGeometryRef()
        linestring = shapely.from_wkb(bytes(geom.ExportToWkb()))
        if not self._lyr.GetSpatialRef().IsProjected():
            x, y = linestring.xy
            points = list(zip(x.tolist(), y.tolist()))
            return calc_spherical_length(points)
        return linestring.length

    def _geometry_type(self) -> int:
        geom_type = self._lyr.GetGeomType()
        while geom_type > 1000:
            geom_type -= 1000
        return geom_type