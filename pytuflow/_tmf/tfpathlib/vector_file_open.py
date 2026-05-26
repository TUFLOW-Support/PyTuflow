import os
from collections import OrderedDict
from typing import Union
import numpy as np
from pathlib import Path

try:
    import shapely
except ImportError:
    shapely = None

try:
    import pyproj
except ImportError:
    pyproj = None


class Geom:

    def __init__(self, geom):
        self.geom = geom
        self.geom_is_wkb = False
        if isinstance(geom, bytes):  # occurs if shapely is not installed
            self.geom_is_wkb = True

    def __repr__(self):
        return f'Geom({self.geom})'

    def geometry_type(self) -> str:
        if self.geom_is_wkb:
            from osgeo import ogr
            ogr_geom = ogr.CreateGeometryFromWkb(self.geom)
            if ogr_geom.GetGeometryType() == 1: return 'Point'
            elif ogr_geom.GetGeometryType() == 4: return 'MultiPoint'
            elif ogr_geom.GetGeometryType() == 2: return 'LineString'
            elif ogr_geom.GetGeometryType() == 5: return 'MultiLineString'
            elif ogr_geom.GetGeometryType() == 3: return 'Polygon'
            elif ogr_geom.GetGeometryType() == 6: return 'MultiPolygon'
            else:
                raise ValueError(f'OGR Geometry type not supported: {ogr_geom.GetGeometryType()}')
        else:
            return self.geom.geom_type

    def to_wkb(self) -> bytes:
        if self.geom_is_wkb:
            return self.geom
        else:
            return self.geom.wkb

    def points(self):
        if self.geom_is_wkb:
            # this means GDAL is installed and shapely is not
            from osgeo import ogr
            ogr_geom = ogr.CreateGeometryFromWkb(self.geom)
            if ogr_geom.GetGeometryType() == 1:  # wkbPoint
                x = ogr_geom.GetX()
                y = ogr_geom.GetY()
                return np.array([[x, y]])
            elif ogr_geom.GetGeometryType() == 4:  # wkbMultiPoint
                points = []
                for i in range(ogr_geom.GetGeometryCount()):
                    pt = ogr_geom.GetGeometryRef(i)
                    x = pt.GetX()
                    y = pt.GetY()
                    points.append([x, y])
                return np.array(points)
            elif ogr_geom.GetGeometryType() == 2:  # wkbLineString
                points = []
                for i in range(ogr_geom.GetPointCount()):
                    x, y, _ = ogr_geom.GetPoint(i)
                    points.append([x, y])
                return np.array(points)
            elif ogr_geom.GetGeometryType() == 5:  # wkbMultiLineString
                points = []
                for j in range(ogr_geom.GetGeometryCount()):
                    line = ogr_geom.GetGeometryRef(j)
                    for i in range(line.GetPointCount()):
                        x, y, _ = line.GetPoint(i)
                        points.append([x, y])
                return np.array(points)
            elif ogr_geom.GetGeometryType() == 3:  # wkbPolygon
                points = []
                ring = ogr_geom.GetGeometryRef(0)  # exterior ring
                for i in range(ring.GetPointCount()):
                    x, y, _ = ring.GetPoint(i)
                    points.append([x, y])
                return np.array(points)
            elif ogr_geom.GetGeometryType() == 6:  # wkbMultiPolygon
                points = []
                for k in range(ogr_geom.GetGeometryCount()):
                    poly = ogr_geom.GetGeometryRef(k)
                    ring = poly.GetGeometryRef(0)  # exterior ring
                    for i in range(ring.GetPointCount()):
                        x, y, _ = ring.GetPoint(i)
                        points.append([x, y])
                return np.array(points)
        else:
            # assume shapely is installed if we reach here
            if self.geom.geom_type == 'Point':
                x = self.geom.x
                y = self.geom.y
                return np.array([[x, y]])
            elif self.geom.geom_type == 'MultiPoint':
                points = []
                for pt in self.geom.geoms:
                    x = pt.x
                    y = pt.y
                    points.append([x, y])
                return np.array(points)
            elif self.geom.geom_type == 'LineString':
                points = []
                for x, y in self.geom.coords:
                    points.append([x, y])
                return np.array(points)
            elif self.geom.geom_type == 'MultiLineString':
                points = []
                for line in self.geom.geoms:
                    for x, y in line.coords:
                        points.append([x, y])
                return np.array(points)
            elif self.geom.geom_type == 'Polygon':
                points = []
                exterior = self.geom.exterior
                for x, y in exterior.coords:
                    points.append([x, y])
                return np.array(points)
            elif self.geom.geom_type == 'MultiPolygon':
                points = []
                for poly in self.geom.geoms:
                    exterior = poly.exterior
                    for x, y in exterior.coords:
                        points.append([x, y])
                return np.array(points)

    def lines(self):
        if self.geom_is_wkb:
            from osgeo import ogr
            ogr_geom = ogr.CreateGeometryFromWkb(self.geom)
            lines = []
            if ogr_geom.GetGeometryType() == 2:  # wkbLineString
                line_points = []
                for i in range(ogr_geom.GetPointCount()):
                    x, y, _ = ogr_geom.GetPoint(i)
                    line_points.append([x, y])
                lines.append(np.array(line_points))
            elif ogr_geom.GetGeometryType() == 5:  # wkbMultiLineString
                for j in range(ogr_geom.GetGeometryCount()):
                    line = ogr_geom.GetGeometryRef(j)
                    line_points = []
                    for i in range(line.GetPointCount()):
                        x, y, _ = line.GetPoint(i)
                        line_points.append([x, y])
                    lines.append(np.array(line_points))
            return lines
        else:
            lines = []
            if self.geom.geom_type == 'LineString':
                line_points = []
                for x, y in self.geom.coords:
                    line_points.append([x, y])
                lines.append(np.array(line_points))
            elif self.geom.geom_type == 'MultiLineString':
                for line in self.geom.geoms:
                    line_points = []
                    for x, y in line.coords:
                        line_points.append([x, y])
                    lines.append(np.array(line_points))
            return lines

    def polygons(self):
        if self.geom_is_wkb:
            from osgeo import ogr
            ogr_geom = ogr.CreateGeometryFromWkb(self.geom)
            polygons = []
            if ogr_geom.GetGeometryType() == 3:  # wkbPolygon
                poly_points = []
                ring = ogr_geom.GetGeometryRef(0)  # exterior ring
                for i in range(ring.GetPointCount()):
                    x, y, _ = ring.GetPoint(i)
                    poly_points.append([x, y])
                polygons.append(np.array(poly_points))
            elif ogr_geom.GetGeometryType() == 6:  # wkbMultiPolygon
                for k in range(ogr_geom.GetGeometryCount()):
                    poly = ogr_geom.GetGeometryRef(k)
                    poly_points = []
                    ring = poly.GetGeometryRef(0)  # exterior ring
                    for i in range(ring.GetPointCount()):
                        x, y, _ = ring.GetPoint(i)
                        poly_points.append([x, y])
                    polygons.append(np.array(poly_points))
            return polygons
        else:
            polygons = []
            if self.geom.geom_type == 'Polygon':
                poly_points = []
                exterior = self.geom.exterior
                for x, y in exterior.coords:
                    poly_points.append([x, y])
                polygons.append(np.array(poly_points))
            elif self.geom.geom_type == 'MultiPolygon':
                for poly in self.geom.geoms:
                    poly_points = []
                    exterior = poly.exterior
                    for x, y in exterior.coords:
                        poly_points.append([x, y])
                    polygons.append(np.array(poly_points))
            return polygons



class Feature:

    def __init__(self, geom, attrs: OrderedDict, geometry_type: str):
        self.geom = Geom(geom)
        self.attrs = attrs
        self.geometry_type = geometry_type

    def __repr__(self):
        return f'Feature(geom={self.geom}, attrs={self.attrs})'

    def __getitem__(self, item):
        if isinstance(item, str):
            return self.attrs[item]
        elif isinstance(item, int):
            key = list(self.attrs.keys())[item]
            return self.attrs[key]
        else:
            raise KeyError(f'Invalid key type: {type(item)}')

    def __len__(self):
        return len(self.attrs)

    def field_index(self, field_name: str) -> int:
        keys = [x.lower() for x in self.attrs.keys()]
        if field_name.lower() in keys:
            return keys.index(field_name.lower())
        return -1


class VectorLayerOpen:

    def __init__(self, path, mode: str, geometry_type: str = None, crs: Union[str, 'pyproj.CRS'] = None):
        self.fpath = path
        self.mode = mode
        self.driver = None
        self.ds = None
        self.lyr = None
        self.fmt = None
        self.geometry_type = geometry_type
        self._crs = crs
        self.open(path, mode, geometry_type, crs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __iter__(self):
        return self.__next__()

    def crs(self):
        raise NotImplementedError

    def crs_wkt(self) -> str:
        raise NotImplementedError

    def crs_auth(self) -> str:
        raise NotImplementedError

    def get_feature(self, index: int) -> Feature:
        for i, feat in enumerate(self):
            if i == index:
                return feat
        raise IndexError('Feature index out of range')

    def feature_count(self) -> int:
        return 0

    def geometry_types(self) -> list[str]:
        return []

    def open(self, path, mode: str, geometry_type: str = None, crs: Union[str, 'pyproj.CRS'] = None):
        pass

    def create_field(self, name: str, field_type: str = 'str', width: int = None, prec: int = None) -> None:
        """Add a field definition to the layer. Must be called before adding features.

        Parameters
        ----------
        name : str
            Field name.
        field_type : str, optional
            Field type. One of 'str', 'int', 'float'. Default is 'str'.
        width : int, optional
            Field width (used by OGR backend). Ignored by GeoPandas backend.
        prec : int, optional
            Field precision (used by OGR backend). Ignored by GeoPandas backend.
        """
        raise NotImplementedError

    def add_feature(self, geom, attrs: dict = None) -> None:
        """Add a feature to the layer.

        Fields that do not yet exist on the layer are created automatically, with the
        type inferred from the Python value.  Call :meth:`create_field` explicitly if
        you need precise type control.

        Parameters
        ----------
        geom : shapely geometry, bytes (WKB), or None
            The feature geometry.
        attrs : dict, optional
            Attribute values keyed by field name.
        """
        raise NotImplementedError

    def close(self):
        pass


class OGROpen(VectorLayerOpen):

    # Maps friendly type names to OGR field type constants (populated lazily).
    _FIELD_TYPE_MAP = None

    # Maps geometry type strings to OGR wkb constants (populated lazily).
    _GEOM_TYPE_MAP = None

    @classmethod
    def _field_type_map(cls):
        if cls._FIELD_TYPE_MAP is None:
            from osgeo import ogr
            cls._FIELD_TYPE_MAP = {
                'str': ogr.OFTString,
                'string': ogr.OFTString,
                'int': ogr.OFTInteger,
                'integer': ogr.OFTInteger,
                'float': ogr.OFTReal,
                'real': ogr.OFTReal,
                'double': ogr.OFTReal,
                'date': ogr.OFTDate,
            }
        return cls._FIELD_TYPE_MAP

    @classmethod
    def _geom_type_map(cls):
        if cls._GEOM_TYPE_MAP is None:
            from osgeo import ogr
            cls._GEOM_TYPE_MAP = {
                'point': ogr.wkbPoint,
                'linestring': ogr.wkbLineString,
                'polygon': ogr.wkbPolygon,
                'multipoint': ogr.wkbMultiPoint,
                'multilinestring': ogr.wkbMultiLineString,
                'multipolygon': ogr.wkbMultiPolygon,
                'unknown': ogr.wkbUnknown,
            }
        return cls._GEOM_TYPE_MAP

    def __next__(self):
        from . import GisFormat, ogr_geom_type_to_string
        for feat in self.lyr:
            if self.fmt == GisFormat.MIF:
                self.geometry_type = ogr_geom_type_to_string(feat.GetGeometryRef().GetGeometryType())
            geom = feat.GetGeometryRef()
            attrs = OrderedDict()
            for i in range(feat.GetFieldCount()):
                field_defn = feat.GetFieldDefnRef(i)
                field_name = field_defn.GetName()
                field_value = feat.GetField(i)
                attrs[field_name] = field_value
            if shapely is not None:
                geom = shapely.from_wkb(bytes(geom.ExportToWkb()))
            else:
                geom = bytes(geom.ExportToWkb())
            feat = Feature(geom, attrs, self.geometry_type)
            yield feat

    def crs_wkt(self) -> str:
        sr = self.lyr.GetSpatialRef()
        return sr.ExportToWkt()

    def crs_auth(self) -> str:
        sr = self.lyr.GetSpatialRef()
        return f'{sr.GetAuthorityName(None)}:{sr.GetAuthorityCode(None)}'

    def crs(self):
        if pyproj is not None:  # try and return a pyproj CRS object
            return pyproj.CRS.from_string(self.crs_auth())
        return self.lyr.GetSpatialRef()

    def feature_count(self) -> int:
        return self.lyr.GetFeatureCount()

    def geometry_types(self) -> list[str]:
        from . import ogr_geom_type_to_string
        if not self.lyr.GetGeometryTypes() and self.geometry_type:  # this will trigger if the layer is empty
            return [self.geometry_type]
        return [ogr_geom_type_to_string(x) for x in self.lyr.GetGeometryTypes()]

    def open(self, path, mode: str, geometry_type: str = None, crs: Union[str, 'pyproj.CRS'] = None):
        from . import ogr_format, get_driver_name_from_gis_format, GisFormat, ogr_geom_type_to_string
        from osgeo import ogr, osr
        self.fmt = ogr_format(self.fpath)
        driver_name = get_driver_name_from_gis_format(self.fmt)
        self.driver = ogr.GetDriverByName(driver_name)
        if self.mode == 'r':
            if not path.exists():
                raise FileExistsError(f'Could not open {path} for reading')
            self.ds = self.driver.Open(str(path.dbpath))
        else:
            if os.path.exists(path.dbpath):
                self.ds = self.driver.Open(str(path.dbpath), 1)
            else:
                self.ds = self.driver.CreateDataSource(str(path.dbpath))
        if self.ds is None:
            raise Exception(f'Could not open {path.dbpath}')
        self.lyr = self.ds.GetLayer(path.lyrname)
        if mode == 'w' and self.lyr is not None:
            self.ds.DeleteLayer(path.lyrname)
            self.lyr = None
        if mode == 'w' or (mode == 'r+' and self.lyr is None):
            srs = self._build_srs(crs)
            ogr_geom_type = self._resolve_geom_type(geometry_type)
            self.lyr = self.ds.CreateLayer(path.lyrname, srs=srs, geom_type=ogr_geom_type)
        if self.lyr is None:
            raise Exception(f'Could not open layer {path.lyrname}')
        if mode == 'r' and self.fmt != GisFormat.MIF:
            self.geometry_type = ogr_geom_type_to_string(self.lyr.GetGeomType())

    def _build_srs(self, crs):
        """Convert a CRS value to an OGR SpatialReference, or return None."""
        if crs is None:
            return None
        from osgeo import osr
        srs = osr.SpatialReference()
        if isinstance(crs, str):
            if ':' in crs:
                srs.ImportFromEPSG(int(crs.split(':', 1)[1]))
            else:
                srs.ImportFromWkt(crs)
        elif hasattr(crs, 'to_wkt'):  # pyproj CRS
            srs.ImportFromWkt(crs.to_wkt())
        else:
            return None
        return srs

    def _resolve_geom_type(self, geometry_type: str):
        """Return the OGR wkb geometry type constant for a string name."""
        from osgeo import ogr
        if geometry_type is None:
            return ogr.wkbUnknown
        return self._geom_type_map().get(geometry_type.lower(), ogr.wkbUnknown)

    def create_field(self, name: str, field_type: str = 'str', width: int = None, prec: int = None) -> None:
        """Add a field to the OGR layer.

        Parameters
        ----------
        name : str
            Field name.
        field_type : str, optional
            One of 'str', 'int', 'float'. Default is 'str'.
        width : int, optional
            Field width.
        prec : int, optional
            Field decimal precision.
        """
        from osgeo import ogr
        ogr_type = self._field_type_map().get(field_type.lower(), ogr.OFTString)
        field_defn = ogr.FieldDefn(name, ogr_type)
        if width is not None:
            field_defn.SetWidth(width)
        if prec is not None:
            field_defn.SetPrecision(prec)
        self.lyr.CreateField(field_defn)

    def add_feature(self, geom, attrs: dict = None) -> None:
        """Add a feature to the OGR layer.

        Unknown fields in *attrs* are auto-created with a type inferred from the
        Python value type.

        Parameters
        ----------
        geom : shapely geometry, bytes (WKB), OGR geometry, or None
            Feature geometry.
        attrs : dict, optional
            Attribute values keyed by field name.
        """
        from osgeo import ogr
        attrs = attrs or {}

        # Auto-create any fields that do not yet exist on the layer.
        defn = self.lyr.GetLayerDefn()
        existing = {defn.GetFieldDefn(i).GetName().lower() for i in range(defn.GetFieldCount())}
        for name, value in attrs.items():
            if name.lower() not in existing:
                if isinstance(value, bool):
                    self.create_field(name, 'str')
                elif isinstance(value, int):
                    self.create_field(name, 'int')
                elif isinstance(value, float):
                    self.create_field(name, 'float')
                else:
                    self.create_field(name, 'str')
                existing.add(name.lower())

        feat = ogr.Feature(self.lyr.GetLayerDefn())
        if geom is not None:
            if isinstance(geom, str):
                ogr_geom = ogr.CreateGeometryFromWkt(geom)
            elif isinstance(geom, bytes):
                ogr_geom = ogr.CreateGeometryFromWkb(geom)
            elif hasattr(geom, 'ExportToWkb'):  # already an OGR geometry
                ogr_geom = geom
            elif hasattr(geom, 'wkb'):  # shapely geometry
                ogr_geom = ogr.CreateGeometryFromWkb(bytes(geom.wkb))
            else:
                raise ValueError(f'Unsupported geometry type: {type(geom)}')
            feat.SetGeometry(ogr_geom)

        for k, v in attrs.items():
            feat.SetField(k, v)

        self.lyr.CreateFeature(feat)

    def close(self):
        self.lyr = None
        if self.ds is not None:
            self.ds.FlushCache()
            self.ds = None


class PyOGRIOOpen(VectorLayerOpen):

    def __next__(self):
        from . import GisFormat
        for _, feat in self.lyr.iterrows():
            if self.fmt == GisFormat.MIF:
                self.geometry_type = feat.geometry.geom_type
            attrs = OrderedDict()
            for col in self.lyr.columns:
                if col != 'geometry':
                    attrs[col] = feat[col]
            geom = feat.geometry
            feat = Feature(geom, attrs, self.geometry_type)
            yield feat

    def crs_wkt(self) -> str:
        crs = self.lyr.crs
        if crs is None:
            return ''
        return crs.to_wkt()

    def crs_auth(self) -> str:
        crs = self.lyr.crs
        if crs is None:
            return 'UNKNOWN'
        if crs.to_authority() is not None:
            auth_name, auth_code = crs.to_authority()
            return f'{auth_name}:{auth_code}'
        return crs.to_string()

    def crs(self):
        return self.lyr.crs

    def feature_count(self) -> int:
        return self.lyr.shape[0]

    def geometry_types(self) -> list[str]:
        return [x for x in self.lyr.geometry.geom_type.unique().tolist() if x is not None]

    def open(self, path, mode: str, geometry_type: str = None, crs: Union[str, 'pyproj.CRS'] = None):
        import geopandas as gpd
        from . import ogr_format
        self.fmt = ogr_format(self.fpath)
        if self.mode == 'r':
            if not path.exists():
                raise FileExistsError(f'Could not open {path} for reading')
            self.ds = gpd.read_file(str(path.dbpath), layer=path.lyrname)
            self.lyr = self.ds
            if not self.lyr.empty:
                self.geometry_type = self.lyr.geometry.geom_type.unique()[0]
        elif self.mode == 'w':
            # Always start with a fresh empty GeoDataFrame.
            self.lyr = gpd.GeoDataFrame(geometry=gpd.GeoSeries(dtype='geometry'), crs=crs)
            self.ds = self.lyr
        elif self.mode in ('r+', 'a'):
            # Try to read the existing layer; create an empty one if it doesn't exist.
            layer_arg = path.lyrname
            if path.exists():
                try:
                    self.lyr = gpd.read_file(str(path.dbpath), layer=layer_arg)
                except Exception:
                    self.lyr = gpd.GeoDataFrame(geometry=gpd.GeoSeries(dtype='geometry'), crs=crs)
            else:
                self.lyr = gpd.GeoDataFrame(geometry=gpd.GeoSeries(dtype='geometry'), crs=crs)
            self.ds = self.lyr
            if not self.lyr.empty:
                self.geometry_type = self.lyr.geometry.geom_type.unique()[0]

    def create_field(self, name: str, field_type: str = 'str', width: int = None, prec: int = None) -> None:
        """Add a column to the backing GeoDataFrame.

        Parameters
        ----------
        name : str
            Column name.
        field_type : str, optional
            One of 'str', 'int', 'float'. Default is 'str'.
        width : int, optional
            Ignored by the GeoPandas backend (accepted for API compatibility).
        prec : int, optional
            Ignored by the GeoPandas backend (accepted for API compatibility).
        """
        import pandas as pd
        type_map = {'str': object, 'string': object, 'int': 'Int64', 'integer': 'Int64',
                    'float': float, 'real': float, 'double': float}
        dtype = type_map.get(field_type.lower(), object)
        if name not in self.lyr.columns:
            self.lyr[name] = pd.Series(dtype=dtype)

    def add_feature(self, geom, attrs: dict = None) -> None:
        """Append a feature row to the backing GeoDataFrame.

        Unknown fields in *attrs* are added automatically.

        Parameters
        ----------
        geom : shapely geometry, bytes (WKB), or None
            Feature geometry.
        attrs : dict, optional
            Attribute values keyed by field name.
        """
        import geopandas as gpd
        import pandas as pd

        attrs = attrs or {}

        # Convert WKT/WKB strings and bytes to shapely so GeoPandas is happy.
        if isinstance(geom, str):
            if shapely is None:
                raise ImportError('shapely is required to add WKT features via the GeoPandas backend')
            geom = shapely.from_wkt(geom)
        elif isinstance(geom, bytes):
            if shapely is None:
                raise ImportError('shapely is required to add WKB features via the GeoPandas backend')
            geom = shapely.from_wkb(geom)

        # Auto-create missing columns.
        for name, value in attrs.items():
            if name not in self.lyr.columns:
                if isinstance(value, bool):
                    dtype = object
                elif isinstance(value, int):
                    dtype = 'Int64'
                elif isinstance(value, float):
                    dtype = float
                else:
                    dtype = object
                import pandas as pd
                self.lyr[name] = pd.Series(dtype=dtype)

        row = {'geometry': geom}
        row.update(attrs)
        new_row = gpd.GeoDataFrame([row], geometry='geometry', crs=self.lyr.crs)
        # Preserve existing column dtypes: Python None does not carry type information
        # so pd.concat may silently cast typed columns (e.g. float64) to object.
        original_dtypes = {col: self.lyr[col].dtype for col in self.lyr.columns if col != 'geometry'}
        self.lyr = pd.concat([self.lyr, new_row], ignore_index=True)
        for col, dtype in original_dtypes.items():
            try:
                self.lyr[col] = self.lyr[col].astype(dtype)
            except (ValueError, TypeError):
                pass
        self.ds = self.lyr

    def close(self):
        if self.mode != 'r' and self.lyr is not None:
            from . import GisFormat, get_driver_name_from_gis_format
            driver = get_driver_name_from_gis_format(self.fmt)
            dbpath = str(self.fpath.dbpath)
            lyrname = self.fpath.lyrname
            if not Path(dbpath).parent.exists():
                Path(dbpath).parent.mkdir(parents=True, exist_ok=True)
            # We always overwrite the target layer — existing features were already
            # merged into self.lyr during open() for r+/a modes.
            if self.fmt == GisFormat.GPKG:
                self.lyr.to_file(dbpath, layer=lyrname, driver=driver, mode='w')
            else:
                self.lyr.to_file(dbpath, driver=driver)
        self.ds = None
        self.lyr = None
