import re
import typing
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from TUFLOW_results import ResData, ChanInfo, NodeInfo, Data1D
from compatibility_routines import Path, Logging

try:
    from qgis.core import QgsVectorLayer
    has_qgis_lib = True
except ImportError:
    has_qgis_lib = False
try:
    from osgeo import ogr
    has_gdal_lib = True
except ImportError:
    has_gdal_lib = False


GisLayerType = typing.Union['QgsVectorLayer', 'ogr.Layer', str]
GisFeatureType = typing.Union['QgsFeature', 'ogr.Feature']


@dataclass
class Pos:
    x: float = field(default=None)
    y: float = field(default=None)
    valid: bool = field(default=False, init=False)

    def __post_init__(self):
        if self.x is None or self.y is None:
            return
        self.valid = True

    def __eq__(self, other):
        if not isinstance(other, Pos):
            return False
        return np.allclose([self.x, self.y], [other.x, other.y], rtol=0., atol=1e-6)


@dataclass
class Rect:
    x_min: float = field(default=None)
    y_min: float = field(default=None)
    x_max: float = field(default=None)
    y_max: float = field(default=None)
    width: float = field(default=None)
    height: float = field(default=None)
    valid: bool = field(default=False, init=False)

    def __post_init__(self):
        if self.x_min is None or self.y_min is None:
            return
        if self.x_max is None and self.width is None:
            return
        if self.y_max is None and self.height is None:
            return
        if self.x_max is not None and self.y_max is not None:
            self.valid = True
            return
        if self.x_max is None:
            self.x_max = self.x_min + self.width / 2.
            self.x_min = self.x_min - self.width / 2.
        if self.y_max is None:
            self.y_max = self.y_min + self.height / 2.
            self.y_min = self.y_min - self.height / 2.
        self.valid = True

    def to_wkt(self) -> str:
        if not self.valid:
            return ''
        return 'POLYGON(({0} {1}, {0} {3}, {2} {3}, {2} {1}, {0} {1}))'.format(self.x_min, self.y_min, self.x_max, self.y_max)


class Feature:
    """Abstract feature so it can use libraries outside of QGIS."""

    def __init__(self, feat: GisFeatureType):
        self.feat = feat

    def __getitem__(self, item):
        pass

    def vertices(self) -> list[Pos]:
        pass

    def length(self) -> float:
        pass


class QgisFeature(Feature):

    def __getitem__(self, item):
        return self.feat[item]

    def vertices(self) -> list[Pos]:
        return [Pos(x.x(), x.y()) for x in self.feat.geometry().vertices()]

    def length(self) -> float:
        return self.feat.geometry().length()


class GdalFeature(Feature):

    def __getitem__(self, item):
        return self.feat.GetField(item)

    def vertices(self) -> list[Pos]:
        return [Pos(x[0], x[1]) for x in self.feat.GetGeometryRef().GetPoints()]

    def length(self) -> float:
        return self.feat.GetGeometryRef().Length()



class GISDriver:
    """Abstract GIS driver so it can use libraries outside of QGIS."""

    def __new__(cls, layer: GisLayerType, ds: 'ogr.DataSource' = None) -> 'GISDriver':
        if has_qgis_lib and isinstance(layer, QgsVectorLayer):
            cls = QgisDriver
        elif has_gdal_lib and (isinstance(layer, ogr.Layer) or (isinstance(layer, str) and ds is not None)):
            cls = GdalDriver
        elif not has_gdal_lib and not has_qgis_lib:
            raise ModuleNotFoundError('No GIS drivers available')
        else:
            raise NotImplementedError('GIS Driver not recognised: {0}'.format(type(layer)))
        self = object.__new__(cls)
        self._init(layer, ds)
        return self

    def _init(self, layer: GisLayerType, ds: 'ogr.DataSource') -> None:
        self.layer = layer

    def still_alive(self) -> bool:
        return True

    def get_feature_by_field_value(self, field: str, value: str) -> GisFeatureType:
        pass

    def start_vertex_from_field_value(self, field: str, id_: str) -> Pos:
        pass

    def end_vertex_from_field_value(self, field: str, id_: str) -> Pos:
        feat = self.get_feature_by_field_value(field, id_)
        if feat is None:
            return Pos()
        verts = feat.vertices()
        if verts:
            return verts[-1]
        return Pos()

    def feat_is_ds_dir(self, pos: Pos, feat: GisFeatureType) -> bool:
        verts = feat.vertices()
        snapped = bool(verts) and pos == verts[0]
        return snapped

    def feat_is_us_dir(self, pos: Pos, feat: GisFeatureType) -> bool:
        verts = feat.vertices()
        snapped = bool(verts) and pos == verts[-1]
        return snapped

    def get_features_by_region(self, rect: Rect, timestep: float) -> typing.Generator[GisFeatureType, None, None]:
        pass

    def get_snapped_features(self, rect: Rect, pos: Pos, timestep: float) -> typing.Generator[GisFeatureType, None, None]:
        not_snapped = []
        for feat in self.get_features_by_region(rect, timestep):
            if feat['ID'] not in not_snapped:
                yield feat
            else:
                not_snapped.append(feat['ID'])

    def get_snapped_features_in_ds_dir(self, rect: Rect, pos: Pos, timestep: float) -> typing.Generator[GisFeatureType, None, None]:
        not_snapped = []
        for feat in self.get_features_by_region(rect, timestep):
            if feat['ID'] not in not_snapped and self.feat_is_ds_dir(pos, feat):
                yield feat
            else:
                not_snapped.append(feat['ID'])

    def get_snapped_features_in_us_dir(self, rect: Rect, pos: Pos, timestep: float) -> typing.Generator[GisFeatureType, None, None]:
        not_snapped = []
        for feat in self.get_features_by_region(rect, timestep):
            if feat['ID'] not in not_snapped and self.feat_is_us_dir(pos, feat):
                yield feat
            else:
                not_snapped.append(feat['ID'])


class QgisDriver(GISDriver):

    def _init(self, layer: GisLayerType, ds: 'ogr.DataSource') -> None:
        super()._init(layer, ds)
        self.si = None

    def still_alive(self) -> bool:
        try:
            self.layer.name()
            return True
        except RuntimeError:
            return False

    def get_feature_by_field_value(self, field: str, value: str) -> 'QgisFeature':
        from qgis.core import QgsFeatureRequest
        exp = '"{0}" = \'{1}\''.format(field, value)
        # use expression to get feature - use subset of attributes to speed up query - need geometry, so don't turn off
        req = QgsFeatureRequest().setFilterExpression(exp).setSubsetOfAttributes([field, 'Time_relative'], self.layer.fields())
        for feat in self.layer.getFeatures(req):
            return QgisFeature(feat)

    def start_vertex_from_field_value(self, field: str, id_: str) -> Pos:
        feat = self.get_feature_by_field_value(field, id_)
        if feat is None:
            return Pos()
        verts = feat.vertices()
        if verts:
            return verts[-1]
        return Pos()

    def get_features_by_region(self, rect: Rect, timestep: float) -> typing.Generator[GisFeatureType, None, None]:
        from qgis.core import QgsFeatureRequest, QgsSpatialIndex, QgsRectangle
        if self.si is None:
            exp = '"Time_hours" = {0}'.format(timestep)
            req = QgsFeatureRequest().setFilterExpression(exp)
            self.si = QgsSpatialIndex(self.layer.getFeatures(exp))
        qgsrect = QgsRectangle(rect.x_min, rect.y_min, rect.x_max, rect.y_max)
        for fid in self.si.intersects(qgsrect):
            yield QgisFeature(self.layer.getFeature(fid))


class GdalDriver(GISDriver):

    def __del__(self):
        self.layer = None

    def _init(self, layer: GisLayerType, ds: 'ogr.DataSource') -> None:
        super()._init(layer, ds)
        if isinstance(layer, str):
            self.layer = ds.GetLayer(layer)

    def get_feature_by_field_value(self, field: str, value: str) -> 'GdalFeature':
        self.layer.SetAttributeFilter('{0} = \'{1}\''.format(field, value))
        feat = self.layer.GetNextFeature()
        self.layer.SetAttributeFilter(None)
        if feat:
            return GdalFeature(feat)

    def get_features_by_region(self, rect: Rect, timestep: float) -> typing.Generator[GisFeatureType, None, None]:
        self.layer.SetAttributeFilter('Time_relative = {0}'.format(timestep))
        self.layer.SetSpatialFilter(ogr.CreateGeometryFromWkt(rect.to_wkt()))
        for feat in self.layer:
            yield GdalFeature(feat)
        self.layer.SetSpatialFilter(None)
        self.layer.SetAttributeFilter(None)


class ResData_GPKG(ResData):
    """ResData class for GPKG"""

    def __init__(self):
        super().__init__()
        self.default_reference_time = datetime(1999, 12, 31, 14, 0, 0)
        self.has_reference_time = False
        self._display_name = ''
        self._fname = ''
        self._db = None
        self._cur = None
        self._reference_time = None
        self._timesteps = None
        self._point_ts_types = None
        self._line_ts_types = None
        self._region_ts_types = None
        self._gis_point_layer_name = None
        self._gis_line_layer_name = None
        self._gis_region_layer_name = None
        self._gis_point_layer = None
        self._gis_line_layer = None
        self._gis_region_layer = None
        self._gis_point_feat_count = None
        self._gis_line_feat_count = None
        self._gis_region_feat_count = None
        self._units = None
        self._saved_results = {}
        self.LP.id1 = None
        self.LP.id2 = None
        self.LP.loaded = False
        self.gdal_ds = None
        self.Channels = ChanInfo_GPKG(None)
        self.nodes = NodeInfo_GPKG(None)
        self.Data_1D = Data1D_GPKG()

    def __del__(self):
        self.close()

    @property
    def displayname(self) -> str:
        """Name displayed in TUFLOW Viewer."""
        if hasattr(self, '_display_name'):
            return self._display_name
        return ''

    @displayname.setter
    def displayname(self, name: str) -> None:
        """Set display name."""
        if hasattr(self, '_display_name'):
            self._display_name = name

    @property
    def reference_time(self) -> datetime:
        if self._reference_time is None:
            self._reference_time = self.get_reference_time()
        return self._reference_time

    @reference_time.setter
    def reference_time(self, rt: datetime) -> None:
        if hasattr(self, '_reference_time'):
            self._reference_time = rt

    @property
    def units(self) -> str:
        if self._units is None:
            if self._cur is not None:
                try:
                    self._cur.execute(
                        'SELECT'
                            ' DISTINCT Series_units '
                        'FROM'
                        ' Timeseries_info;'
                    )
                    ret = self._cur.fetchall()
                    if ret:
                        units = [x[0] for x in ret]
                        self._units = 'US Customary' if 'ft' in units else 'METRIC'
                except Exception as e:
                    Logging.warning(e)
        return self._units

    @units.setter
    def units(self, value: str):
        pass

    @property
    def gis_point_layer_name(self) -> str:
        if self._gis_point_layer_name is None:
            if self._cur is not None:
                try:
                    self._cur.execute(
                        'SELECT'
                        ' DISTINCT Timeseries_info.Table_name '
                        'FROM'
                        ' Timeseries_info '
                        'INNER JOIN gpkg_geometry_columns'
                        ' ON Timeseries_info.Table_name = gpkg_geometry_columns.table_name '
                        'WHERE'
                        ' gpkg_geometry_columns.geometry_type_name = "POINT" LIMIT 1;'
                    )
                    ret = self._cur.fetchone()
                    if ret:
                        self._gis_point_layer_name = ret[0]
                except Exception as e:
                    Logging.warning(e)
            if self._gis_point_layer_name is None and self.displayname:
                self._gis_point_layer_name = '{0}_P'.format(self.displayname)
        return self._gis_point_layer_name

    @gis_point_layer_name.setter
    def gis_point_layer_name(self, name: str) -> None:
        raise NotImplementedError('Cannot set GIS point layer name')

    @property
    def gis_line_layer_name(self) -> str:
        if self._gis_line_layer_name is None:
            if self._cur is not None:
                try:
                    self._cur.execute(
                        'SELECT'
                        ' DISTINCT Timeseries_info.Table_name '
                        'FROM'
                        ' Timeseries_info '
                        'INNER JOIN gpkg_geometry_columns'
                        ' ON Timeseries_info.Table_name = gpkg_geometry_columns.table_name '
                        'WHERE'
                        ' gpkg_geometry_columns.geometry_type_name = "LINESTRING" LIMIT 1;'
                    )
                    ret = self._cur.fetchone()
                    if ret:
                        self._gis_line_layer_name = ret[0]
                except Exception as e:
                    Logging.warning(e)
            if self._gis_line_layer_name is None and self.displayname:
                self._gis_line_layer_name = '{0}_L'.format(self.displayname)
        return self._gis_line_layer_name

    @gis_line_layer_name.setter
    def gis_line_layer_name(self, name: str) -> None:
        raise NotImplementedError('Cannot set GIS line layer name')

    @property
    def gis_region_layer_name(self) -> str:
        if self._gis_region_layer_name is None:
            if self._cur is not None:
                try:
                    self._cur.execute(
                        'SELECT'
                        ' DISTINCT Timeseries_info.Table_name '
                        'FROM'
                        ' Timeseries_info '
                        'INNER JOIN gpkg_geometry_columns'
                        ' ON Timeseries_info.Table_name = gpkg_geometry_columns.table_name '
                        'WHERE'
                        ' gpkg_geometry_columns.geometry_type_name = "POLYGON" LIMIT 1;'
                    )
                    ret = self._cur.fetchone()
                    if ret:
                        self._gis_region_layer_name = ret[0]
                except Exception as e:
                    Logging.warning(e)
            if self._gis_region_layer_name is None and self.displayname:
                self._gis_region_layer_name = '{0}_R'.format(self.displayname)
        return self._gis_region_layer_name

    @gis_region_layer_name.setter
    def gis_region_layer_name(self, name: str) -> None:
        raise NotImplementedError('Cannot set GIS region layer name')

    @property
    def gis_point_layer(self) -> GisLayerType:
        if self._gis_point_layer is not None and self._gis_point_layer.still_alive():
            return self._gis_point_layer
        elif has_gdal_lib and self._fname:
            if self.gdal_ds is None:
                self.gdal_ds = ogr.GetDriverByName('GPKG').Open(str(self._fname))
            if self.gdal_ds is not None:
                self._gis_point_layer = GISDriver(self.gis_point_layer_name, self.gdal_ds)
        else:
            self._gis_point_layer = None
        return self._gis_point_layer

    @gis_point_layer.setter
    def gis_point_layer(self, layer: GisLayerType) -> None:
        try:
            self._gis_point_layer = GISDriver(layer)
        except (ModuleNotFoundError, NotImplementedError):
            pass

    @property
    def gis_line_layer(self) -> GisLayerType:
        if self._gis_line_layer is not None and self._gis_line_layer.still_alive():
            return self._gis_line_layer
        elif has_gdal_lib and self._fname:
            if self.gdal_ds is None:
                self.gdal_ds = ogr.GetDriverByName('GPKG').Open(str(self._fname))
            if self.gdal_ds is not None:
                self._gis_line_layer = GISDriver(self.gis_line_layer_name, self.gdal_ds)
        else:
            self._gis_line_layer = None
        return self._gis_line_layer

    @gis_line_layer.setter
    def gis_line_layer(self, layer: GisLayerType) -> None:
        try:
            self._gis_line_layer = GISDriver(layer)
        except (ModuleNotFoundError, NotImplementedError):
            pass

    @property
    def gis_region_layer(self) -> GisLayerType:
        if self._gis_region_layer is not None and self._gis_region_layer.still_alive():
            return self._gis_region_layer
        elif has_gdal_lib and self._fname:
            if self.gdal_ds is None:
                self.gdal_ds = ogr.GetDriverByName('GPKG').Open(str(self._fname))
            if self.gdal_ds is not None:
                self._gis_region_layer = GISDriver(self.gis_region_layer_name, self.gdal_ds)
        else:
            self._gis_region_layer = None
        return self._gis_region_layer

    @gis_region_layer.setter
    def gis_region_layer(self, layer: GisLayerType) -> None:
        try:
            self._gis_region_layer = GISDriver(layer)
        except (ModuleNotFoundError, NotImplementedError):
            pass

    @property
    def times(self) -> typing.List[float]:
        return self.timeSteps()

    @property
    def gis_point_feature_count(self) -> int:
        if self._gis_point_feat_count is None:
            if self._cur is not None:
                try:
                    self._cur.execute(
                        'SELECT'
                        ' Count '
                        'FROM'
                        ' Timeseries_info '
                        'WHERE'
                        ' Table_name = "{0}" LIMIT 1;'.format(self.gis_point_layer_name)
                    )
                    ret = self._cur.fetchone()
                    if ret:
                        try:
                            self._gis_point_feat_count = int(ret[0])
                        except ValueError:
                            self._gis_point_feat_count = 0
                    else:
                        self._gis_point_feat_count = 0
                except Exception as e:
                    Logging.warning(e)
            else:
                self._gis_point_feat_count = 0
        return self._gis_point_feat_count

    @gis_point_feature_count.setter
    def gis_point_feature_count(self, count: int) -> None:
        raise NotImplementedError('Cannot set GIS point feature count')

    @property
    def gis_line_feature_count(self) -> int:
        if self._gis_line_feat_count is None:
            if self._cur is not None:
                try:
                    self._cur.execute(
                        'SELECT'
                        ' Count '
                        'FROM'
                        ' Timeseries_info '
                        'WHERE'
                        ' Table_name = "{0}" LIMIT 1;'.format(self.gis_line_layer_name)
                    )
                    ret = self._cur.fetchone()
                    if ret:
                        try:
                            self._gis_line_feat_count = int(ret[0])
                        except ValueError:
                            self._gis_line_feat_count = 0
                    else:
                        self._gis_line_feat_count = 0
                except Exception as e:
                    Logging.warning(e)
            else:
                self._gis_line_feat_count = 0
        return self._gis_line_feat_count

    @gis_line_feature_count.setter
    def gis_line_feature_count(self, count: int) -> None:
        raise NotImplementedError('Cannot set GIS line feature count')

    @property
    def gis_region_feature_count(self) -> int:
        if self._gis_region_feat_count is None:
            if self._cur is not None:
                try:
                    self._cur.execute(
                        'SELECT'
                        ' Count '
                        'FROM'
                        ' Timeseries_info '
                        'WHERE'
                        ' Table_name = "{0}" LIMIT 1;'.format(self.gis_region_layer_name)
                    )
                    ret = self._cur.fetchone()
                    if ret:
                        try:
                            self._gis_region_feat_count = int(ret[0])
                        except ValueError:
                            self._gis_region_feat_count = 0
                    else:
                        self._gis_region_feat_count = 0
                except Exception as e:
                    Logging.warning(e)
            else:
                self._gis_region_feat_count = 0
        return self._gis_region_feat_count

    @gis_region_feature_count.setter
    def gis_region_feature_count(self, count: int) -> None:
        raise NotImplementedError('Cannot set GIS region feature count')

    @staticmethod
    def is_gpkg_ts_res(fname: Path) -> bool:
        """Routine determining if file is valid / compatible."""
        import sqlite3
        try:
            conn = sqlite3.connect(fname)
        except Exception as e:
            return False
        try:
            cur = conn.cursor()
            cur.execute('SELECT Version FROM TUFLOW_timeseries_version;')
            version = cur.fetchone()[0]
            valid = True
        except Exception as e:
            # No need to log. If the table doesn't exist, we just want to return valid as False
            # Logging.error(e, Logging.get_stack_trace())
            valid = False
        finally:
            conn.close()
        return valid

    def close(self) -> None:
        if self._db is not None:
            try:
                self._db.close()
                self._db = None
                self._cur = None
            except Exception as e:
                Logging.warning(e)
        if self.gdal_ds is not None:
            self.gis_point_layer = None
            self.gis_line_layer = None
            self.gis_region_layer = None
            self.gdal_ds = None

    def load(self, fname: str) -> typing.Tuple[bool, str]:
        """Load file. This routine just checks compatibility etc. Load data on the fly as needed."""
        import sqlite3
        from sqlite3 import DatabaseError
        err, msg = False, ''
        self.formatVersion = 2
        self._fname = Path(fname)
        self._display_name = re.sub(r'_swmm_ts', '', self._fname.stem)
        self.fpath = str(self._fname.parent)
        self.filename = self._fname.name
        self.Channels.parent = self
        self.nodes.parent = self
        self.Data_1D.parent = self
        if not self._fname.exists():
            err, msg = True, 'File {0} does not exist\n'.format(fname)
            return err, msg
        if not self.is_gpkg_ts_res(self._fname):
            err, msg = True, 'File {0} is not recognised as a compatible time series result'.format(self._fname)
            return err, msg

        try:
            self._db = sqlite3.connect(self._fname)
            self._cur = self._db.cursor()
            self.Channels.cur = self._cur
            self.nodes.cur = self._cur
            self.Data_1D.cur = self._cur
        except DatabaseError as e:
            err, msg = True, 'Error opening SQLite database: {0}'.format(e)

        # gis layers
        self.GIS.P = r'{0}|layername={1}'.format(self._fname, self.gis_point_layer_name)
        self.GIS.L = r'{0}|layername={1}'.format(self._fname, self.gis_line_layer_name)
        self.GIS.R = None

        return err, msg

    def timestep_interval(self, layer_name: str, result_type: str) -> float:
        if self._cur is None:
            return 0.
        try:
            sql = 'SELECT dt FROM Timeseries_info WHERE Table_name = "{0}" and "Column_name" = "{1}";'.format(layer_name, result_type)
            self._cur.execute(sql)
            try:
                return float(self._cur.fetchone()[0])
            except (TypeError, IndexError):
                return 0.
        except Exception as e:
            Logging.error(e, Logging.get_stack_trace())
            return 0.


    def timeSteps(self, zero_time=None):
        if self._timesteps is not None:
            return self._timesteps
        timesteps = []
        if self._cur is None:
            return timesteps
        try:
            for row in self._cur.execute('SELECT Time_relative FROM DatasetTimes;'):
                try:
                    timesteps.append(float(row[0]))
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            Logging.warning(e)
        finally:
            self._timesteps = timesteps
            return self._timesteps

    def lineResultTypesLP(self) -> typing.List[str]:
        types = []
        if 'Water Level' in self.pointResultTypesTS() and 'Depth' in self.pointResultTypesTS():
            types.append('Bed Level')
        if 'Water Level' in self.pointResultTypesTS():
            types.append('Water Level')
        return types

    def pointResultTypesTS(self) -> typing.List[str]:
        if self._point_ts_types is None:
            self._point_ts_types = self.result_types_from_table(self.gis_point_layer_name)
        return self._point_ts_types

    def lineResultTypesTS(self) -> typing.List[str]:
        if self._line_ts_types is None:
            self._line_ts_types = self.result_types_from_table(self.gis_line_layer_name)
        return self._line_ts_types

    def regionResultTypesTS(self) -> typing.List[str]:
        if self._region_ts_types is None:
            self._region_ts_types = self.result_types_from_table(self.gis_region_layer_name)
        return self._region_ts_types

    def reloadTimesteps(self, zeroTime):
        raise NotImplementedError('reloadTimesteps not implemented for GPKG')

    def getTSData(self, id_: str, res: str, dom: str, geom: str = '') -> typing.Tuple[bool, list[float], str]:
        if self._cur is None:
            return False, [0.], 'No data'
        short_name_map = {
            'Q': 'Flow',
            'H': 'Water Level',
            'V': 'Velocity',
            'D': 'Depth',
            'Vol': 'Storage Volume',
            'L': 'Flood Losses'
        }
        if res.upper() in short_name_map:
            res = short_name_map[res.upper()]

        key = self.create_key(id_, res)
        if key in self._saved_results:
            return True, self._saved_results[key], ''

        if res in self.pointResultTypesTS():
            tbl = self.gis_point_layer_name
        elif res in self.lineResultTypesTS():
            tbl = self.gis_line_layer_name
        elif res in self.regionResultTypesTS():
            tbl = self.gis_region_layer_name
        else:
            return False, [0.], 'Result type not found in results: {0}'.format(res)

        y = []
        try:
            for row in self._cur.execute('SELECT "{0}" FROM "{1}" WHERE ID = "{2}";'.format(res, tbl, id_)):
                try:
                    y.append(float(row[0]))
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            Logging.error(e, Logging.get_stack_trace())
            return False, [0.], 'No data'

        self._saved_results[key] = np.array(y)

        return True, self._saved_results[key], ''

    def result_types_from_table(self, table: str) -> typing.List[str]:
        types = []
        if self._cur is None:
            return types
        try:
            start = False
            for row in self._cur.execute('PRAGMA "main".TABLE_INFO("{0}");'.format(table)):
                if row[1] == 'Datetime':
                    start = True
                    continue
                if start:
                    types.append(row[1])
        except Exception as e:
            Logging.warning(e)
        finally:
            return types

    def parse_reference_time(self, string: str) -> datetime:
        if 'hour' in string:
            self.time_units = 'h'
        elif 'second' in string:
            self.time_units = 's'
        else:
            self.time_units = string.split(' ')[0]

        if not re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', string):
            return datetime(2000, 1, 1)  # a default value

        return datetime.strptime(re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', string)[0], '%Y-%m-%d %H:%M:%S')

    def get_reference_time(self) -> datetime:
        if self._cur is None:
            return self.default_reference_time
        reference_time = self.default_reference_time
        try:
            self._cur.execute('SELECT Reference_time FROM Timeseries_info LIMIT 1;')
            row = self._cur.fetchone()[0]
            reference_time = self.parse_reference_time(row)
            self.has_reference_time = True
        except Exception as e:
            pass
        finally:
            return reference_time

    def create_key(self, id_: str, res: str):
        return '{0}_{1}'.format(id_, res)

    def getLPConnectivity(self, id1: str, id2: str, *args, **kwargs) -> typing.Tuple[bool, str]:
        self.LP.loaded = False
        if id1 == self.LP.id1 and id2 == self.LP.id2:
            self.LP.loaded = True
            return False, ''
        if self.gis_point_layer is None or self.gis_line_layer is None:
            return True, 'No GIS Layers or Drivers available'
        found = self.LP_force_connection(id1, id2)
        if found:
            self.LP.id1 = id1
            self.LP.id2 = id2
            return False, ''
        found = self.LP_force_connection(id2, id1)
        if found:
            self.LP.id1 = id2
            self.LP.id2 = id1
            return False, ''
        return True, 'No connection found'

    def LP_force_connection(self, start_chan: str, end_chan: str) -> bool:
        self.LP.chan_list = []
        self.LP.chan_index = []
        self.LP.node_list = []
        self.LP.dist_chan_inverts = []

        branches = []
        chans = []
        feat = self._gis_line_layer.get_feature_by_field_value('ID', start_chan)
        found = self.find_branches(feat, end_chan, chans[:], branches)
        if found and branches:
            dist = 0.
            for j, feat in enumerate(branches[-1]):
                self.LP.chan_list.append(feat['ID'])
                if j == 0:
                    self.LP.node_list.append(self.chan_us_node(feat['ID'], feat))
                    self.LP.dist_chan_inverts.append(dist)
                dist += feat.length()
                self.LP.dist_chan_inverts.append(dist)
                self.LP.node_list.append(self.chan_ds_node(feat['ID'], feat))

        return found

    def find_branches(self, feat, end_chan, chans, branches):
        found = False
        if feat:
            chans.append(feat)
            i = 0
            for feat_ in self.LP_iterate_downstream_channels(feat):
                chan = feat_['ID']
                if chan in [x['ID'] for x in chans]:
                    branches.append(chans)
                    return found
                if chan == end_chan:
                    chans.append(feat_)
                    branches.append(chans)
                    return True

                i += 1
                try:
                    found = self.find_branches(feat_, end_chan, chans[:], branches)
                    if found:
                        return found
                except RecursionError:
                    branches.append(chans)
                    return found

            if not i:
                branches.append(chans)
                if end_chan is None:
                    found = True

        return found

    def LP_iterate_downstream_channels(self, feat):
        # end vertex coordinates
        timestep = feat['Time_relative']
        try:
            pos = feat.vertices()[-1]
        except IndexError:
            return
        if not pos.valid:
            return
        # create search envelope
        rect = Rect(pos.x, pos.y, width=1., height=1.)
        if not rect.valid:
            return
        # iterate through snapped channels
        for feat_ in self.gis_line_layer.get_snapped_features_in_ds_dir(rect, pos, timestep):
            yield feat_

    def LP_iterate_upstream_channels(self, feat):
        # end vertex coordinates
        timestep = feat['Time_relative']
        try:
            pos = feat.vertices()[0]
        except IndexError:
            return
        if not pos.valid:
            return
        # create search envelope
        rect = Rect(pos.x, pos.y, width=1., height=1.)
        if not rect.valid:
            return
        # iterate through snapped channels
        for feat_ in self.gis_line_layer.get_snapped_features_in_us_dir(rect, pos, timestep):
            yield feat_

    def chan_us_node(self, channel_id: str, feat: Feature = None) -> str:
        if feat is None:
            feat = self.gis_line_layer.get_feature_by_field_value('ID', channel_id)
        if feat is None:
            return
        try:
            pos = feat.vertices()[0]
        except IndexError:
            return
        if not pos.valid:
            return
        rect = Rect(pos.x, pos.y, width=10., height=10.)
        if not rect.valid:
            return
        for feat in self.gis_point_layer.get_snapped_features_in_us_dir(rect, pos, feat['Time_relative']):
            return feat['ID']

    def chan_ds_node(self, channel_id: str, feat: Feature = None) -> str:
        if feat is None:
            feat = self.gis_line_layer.get_feature_by_field_value('ID', channel_id)
        if feat is None:
            return
        try:
            pos = feat.vertices()[-1]
        except IndexError:
            return
        if not pos.valid:
            return
        rect = Rect(pos.x, pos.y, width=1., height=1.)
        if not rect.valid:
            return
        for feat in self.gis_point_layer.get_snapped_features_in_ds_dir(rect, pos, feat['Time_relative']):
            return feat['ID']

    def getLPStaticData(self) -> typing.Tuple[bool, str]:
        if self.LP.loaded:
            return False, ''
        self.LP.chan_inv = []
        self.LP.node_bed = []
        self.LP.node_top = []
        self.LP.H_nd_index = []
        self.LP.node_index = []
        self.LP.Hmax = []
        self.LP.Emax = []
        self.LP.tHmax = []
        self.LP.adverseH.nLocs = 0
        self.LP.adverseH.chainage = []
        self.LP.adverseH.node = []
        self.LP.adverseH.elevation = []
        self.LP.adverseE.nLocs = 0
        self.LP.adverseE.chainage = []
        self.LP.adverseE.node = []
        self.LP.adverseE.elevation = []
        if self._cur is None:
            return False, 'Results not loaded'
        try:
            time = self.timeSteps()[0]
        except IndexError:
            return True, 'Cannot load bed level without temporal data'
        # use one query - very expensive to do multiple little queries
        ids = 'ID = ' + ' OR ID = '.join(['"{0}"'.format(x) for x in self.LP.node_list])
        sql = 'SELECT "ID", "Water Level", "Depth" FROM "{0}" WHERE Time_relative = {1} AND ({2});'.format(self.gis_point_layer_name, time, ids)
        z = [0. for _ in self.LP.node_list]
        try:
            for id_, h, d in self._cur.execute(sql):
                i = self.LP.node_list.index(id_)
                try:
                    z[i] = float(h) - float(d)
                except ValueError:
                    continue
        except Exception as e:
            return True, 'Error loading bed level'
        dists = self.LP.dist_chan_inverts[:]
        self.LP.dist_chan_inverts.clear()
        for i, (d_, z_) in enumerate(zip(dists, z)):
            self.LP.dist_chan_inverts.append(d_)
            self.LP.chan_inv.append(z_)
            if 0 < i < len(self.LP.node_list) - 1:
                self.LP.dist_chan_inverts.append(d_)
                self.LP.chan_inv.append(z_)
        return False, ''

    def getLongPlotXY(self, dat_type: str, time: float) -> typing.Tuple[bool, str]:
        values = []
        for i, node in enumerate(self.LP.node_list):
            found, data, msg = self.getTSData(node, dat_type, '1D')
            if not found:
                return True, 'Error loading {0}'.format(dat_type)
            try:
                j = self.timeSteps().index(float(time))
            except ValueError:
                return True, 'Time step not found', ([], [])
            v = data[j]
            values.append(v)
            if 0 < i < len(self.LP.node_list) - 1:
                values.append(v)

        if dat_type == 'Water Level':
            self.LP.Hdata = values
        return False, '', (self.LP.dist_chan_inverts, values)

class ChanInfo_GPKG(ChanInfo):
    """ChanInfo class for GPKG - lazy load all properties"""

    def __init__(self, fullpath: str):
        self.cur = None
        self.parent = None
        self._nChan = -1
        self._chan_num = []
        self._chan_name = []
        self._chan_US_Node = []
        self._chan_DS_Node = []
        self._chan_US_Chan = []
        self._chan_DS_Chan = []
        self._chan_Flags = []
        self._chan_Length = []
        self._chan_FormLoss = []
        self._chan_n = []
        self._chan_slope = []
        self._chan_US_Inv = []
        self._chan_DS_Inv = []
        self._chan_LBUS_Obv = []
        self._chan_RBUS_Obv = []
        self._chan_LBDS_Obv = []
        self._chan_RBDS_Obv = []
        self._chan_Blockage = []
        self._inv_warning_shown = False
        ChanInfo.__init__(self, None)  # don't want base class to ever try and read a GPKG file

    @property
    def nChan(self) -> int:
        if self._nChan == -1:
            self._nChan = self.parent.gis_line_feature_count
        return self._nChan

    @nChan.setter
    def nChan(self, value: int) -> None:...

    @property
    def chan_num(self) -> list[int]:
        if self._nChan == -1:
            self._chan_num = [x + 1 for x in range(self.nChan)]
        return self._chan_num

    @chan_num.setter
    def chan_num(self, value: list[int]) -> None:...

    @property
    def chan_name(self) -> list[str]:
        if self._nChan == -1:
            if self.cur and self.parent:
                try:
                    self.cur.execute(
                        'SELECT'
                        ' ID '
                        'FROM'
                        ' {0} '
                        'LIMIT {1};'.format(self.parent.gis_line_layer_name, self.nChan)
                    )
                    ret = self.cur.fetchall()
                    if ret:
                        try:
                            self._chan_name = [x[0] for x in ret]
                        except ValueError:
                            pass
                except Exception as e:
                    Logging.warning(e)
        return self._chan_name

    @chan_name.setter
    def chan_name(self, value: list[str]) -> None:
        pass

    @property
    def chan_US_Node(self) -> list[str]:
        if self.cur and self.parent:
            if not self._chan_US_Node:
                if self.parent.gis_line_layer is None:
                    raise ModuleNotFoundError(
                        'No GIS driver available - '
                        'GPKG time series requires PyQGIS or GDAL to determine channel connections'
                    )
                for chan in self.chan_name:
                    self._chan_US_Node.append(self.parent.chan_us_node(chan))
        return self._chan_US_Node

    @chan_US_Node.setter
    def chan_US_Node(self, valud: list[str]) -> None:
        pass

    @property
    def chan_DS_Node(self) -> list[str]:
        if self.cur and self.parent:
            if not self._chan_DS_Node:
                if self.parent.gis_line_layer is None:
                    raise ModuleNotFoundError(
                        'No GIS driver available - '
                        'GPKG time series requires PyQGIS or GDAL to determine channel connections'
                    )
                for chan in self.chan_name:
                    self._chan_DS_Node.append(self.parent.chan_ds_node(chan))
        return self._chan_DS_Node

    @chan_DS_Node.setter
    def chan_DS_Node(self, valud: list[str]) -> None:
        pass

    @property
    def chan_US_Chan(self) -> list[list[str]]:
        if self.cur and self.parent:
            if not self._chan_US_Chan:
                if self.parent.gis_line_layer is None:
                    raise ModuleNotFoundError(
                        'No GIS driver available - '
                        'GPKG time series requires PyQGIS or GDAL to determine channel connections'
                    )
                for chan in self.chan_name:
                    feat = self.parent.gis_line_layer.get_feature_by_field_value('ID', chan)
                    if feat is None:
                        self._chan_US_Chan.append([])
                        continue
                    self._chan_US_Chan.append([x['ID'] for x in self.parent.LP_iterate_upstream_channels(feat)])
        return self._chan_US_Chan

    @chan_US_Chan.setter
    def chan_US_Chan(self, valud: list[list[str]]) -> None:
        pass

    @property
    def chan_DS_Chan(self) -> list[list[str]]:
        if self.cur and self.parent:
            if not self._chan_DS_Chan:
                if self.parent.gis_line_layer is None:
                    raise ModuleNotFoundError(
                        'No GIS driver available - '
                        'GPKG time series requires PyQGIS or GDAL to determine channel connections'
                    )
                for chan in self.chan_name:
                    feat = self.parent.gis_line_layer.get_feature_by_field_value('ID', chan)
                    if feat is None:
                        self._chan_DS_Chan.append([])
                        continue
                    self._chan_DS_Chan.append([x['ID'] for x in self.parent.LP_iterate_downstream_channels(feat)])
        return self._chan_DS_Chan

    @chan_DS_Chan.setter
    def chan_DS_Chan(self, valud: list[list[str]]) -> None:
        pass

    @property
    def chan_Flags(self) -> list[str]:
        raise NotImplementedError('GPKG time series format does not support chan_Flags property')

    @chan_Flags.setter
    def chan_Flags(self, valud: list[str]) -> str:
        pass

    @property
    def chan_Length(self) -> list[float]:
        if self.cur and self.parent:
            if not self._chan_Length:
                if self.parent.gis_line_layer is None:
                    raise ModuleNotFoundError(
                        'No GIS driver available - '
                        'GPKG time series requires PyQGIS or GDAL to determine channel lengths'
                    )
                for chan in self.chan_name:
                    feat = self.parent.gis_line_layer.get_feature_by_field_value('ID', chan)
                    if feat is None:
                        self._chan_Length.append(0.)
                        continue
                    self._chan_Length.append(feat.length())
        return self._chan_Length

    @chan_Length.setter
    def chan_Length(self, valud: list[float]) -> None:
        pass

    @property
    def chan_FormLoss(self) -> list[float]:
        raise NotImplementedError('GPKG time series format does not support chan_FormLoss property')

    @chan_FormLoss.setter
    def chan_FormLoss(self, valud: list[float]) -> None:
        pass

    @property
    def chan_n(self) -> list[float]:
        raise NotImplementedError('GPKG time series format does not support chan_n property')

    @chan_n.setter
    def chan_n(self, valud: list[float]) -> None:
        pass

    @property
    def chan_slope(self) -> list[float]:
        if self.cur and self.parent:
            if not self._chan_slope:
                if self.chan_US_Inv and self.chan_DS_Inv and self.chan_Length:
                    self._chan_slope = [(us - ds) / l for us, ds, l in zip(self.chan_US_Inv, self.chan_DS_Inv, self.chan_Length)]
        return self._chan_slope

    @chan_slope.setter
    def chan_slope(self, valud: list[float]) -> None:
        pass

    @property
    def chan_US_Inv(self) -> list[float]:
        if self.cur and self.parent:
            if not self._chan_US_Inv:
                if self.parent.gis_line_layer is None:
                    raise ModuleNotFoundError(
                        'No GIS driver available - '
                        'GPKG time series requires PyQGIS or GDAL to determine channel inverts'
                    )
                if not self._inv_warning_shown:
                    self._inv_warning_shown = True
                    Logging.warning(
                        'Channel inverts calculated based on node bed levels and not directly from pipe inverts'
                    )
                for i, chan in enumerate(self.chan_name):
                    node = self.chan_US_Node[i]
                    self._chan_US_Inv.append(self.parent.nodes.node_bed[self.parent.nodes.node_name.index(node)])
        return self._chan_US_Inv

    @chan_US_Inv.setter
    def chan_US_Inv(self, valud: list[float]) -> None:
        pass

    @property
    def chan_DS_Inv(self) -> list[float]:
        if not self._chan_DS_Inv:
            if self.parent.gis_line_layer is None:
                raise ModuleNotFoundError(
                    'No GIS driver available - '
                    'GPKG time series requires PyQGIS or GDAL to determine channel inverts'
                )
            if not self._inv_warning_shown:
                self._inv_warning_shown = True
                Logging.warning(
                    'Channel inverts calculated based on node bed levels and not directly from pipe inverts'
                )
            for i, chan in enumerate(self.chan_name):
                node = self.chan_DS_Node[i]
                self._chan_DS_Inv.append(self.parent.nodes.node_bed[self.parent.nodes.node_name.index(node)])
        return self._chan_DS_Inv

    @chan_DS_Inv.setter
    def chan_DS_Inv(self, valud: list[float]) -> None:
        pass

    @property
    def chan_LBUS_Obv(self) -> list[float]:
        raise NotImplementedError('GPKG time series format does not support chan_LBUS_Obv property')

    @chan_LBUS_Obv.setter
    def chan_LBUS_Obv(self, valud: list[float]) -> None:
        pass

    @property
    def chan_LBDS_Obv(self) -> list[float]:
        raise NotImplementedError('GPKG time series format does not support chan_LBDS_Obv property')

    @chan_LBDS_Obv.setter
    def chan_LBDS_Obv(self, valud: list[float]) -> None:
        pass

    @property
    def chan_Blockage(self) -> list[float]:
        raise NotImplementedError('GPKG time series format does not support chan_Blockage property')

    @chan_Blockage.setter
    def chan_Blockage(self, valud: list[float]) -> None:
        pass


class NodeInfo_GPKG(NodeInfo):
    """NodeInfo class for GPKG - lazy load all properties"""

    def __init__(self, fullpath: str):
        self.cur = None
        self.parent = None
        self._nNode = -1
        self._node_num = []
        self._node_name = []
        self._node_bed = []
        self._node_top = []
        self._node_nChan = []
        self._node_channels = []
        NodeInfo.__init__(self, None)

    @property
    def nNode(self) -> int:
        if self._nNode == -1:
            if self.parent is not None:
                self._nNode = self.parent.gis_point_feature_count
        return self._nNode

    @nNode.setter
    def nNode(self, value: int) -> None:...

    @property
    def node_num(self) -> list[int]:
        if self._nNode == -1:
            self._node_num = [x + 1 for x in range(self.nNode)]
        return self._node_num

    @node_num.setter
    def node_num(self, value: list[int]) -> None:...

    @property
    def node_name(self) -> list[str]:
        if self.cur and self.parent:
            if not self._node_name:
                try:
                    self.cur.execute(
                        'SELECT'
                        ' ID '
                        'FROM'
                        ' {0} '
                        'LIMIT {1};'.format(self.parent.gis_point_layer_name, self.nNode)
                    )
                    ret = self.cur.fetchall()
                    if ret:
                        try:
                            self._node_name = [x[0] for x in ret]
                        except ValueError:
                            pass
                except Exception as e:
                    Logging.warning(e)
        return self._node_name

    @node_name.setter
    def node_name(self, value: list[str]) -> None:...

    @property
    def node_bed(self) -> list[float]:
        if self.cur and self.parent:
            if not self._node_bed:
                time = self.parent.timeSteps()
                if time:
                    time = time[0]
                else:
                    time = 0
                ids = 'ID = ' + ' OR ID = '.join(['"{0}"'.format(x) for x in self.node_name])
                sql = 'SELECT "ID", "Water Level", "Depth" FROM "{0}" WHERE Time_relative = {1} AND ({2});'.format(
                    self.parent.gis_point_layer_name, time, ids)
                self._node_bed = [0. for _ in self.node_name]
                for id_, h, d in self.cur.execute(sql):
                    i = self._node_name.index(id_)  # don't want to accidentally reset cursor so use _node_name
                    try:
                        self._node_bed[i] = float(h) - float(d)
                    except ValueError:
                        continue
        return self._node_bed

    @node_bed.setter
    def node_bed(self, value: list[float]) -> None:...

    @property
    def node_top(self) -> list[float]:
        raise NotImplementedError('GPKG time series format does not support node_top property')

    @node_top.setter
    def node_top(self, value: list[float]) -> None:...

    @property
    def node_nChan(self) -> list[int]:
        if self.cur and self.parent:
            if not self._node_nChan:
                self._node_nChan = len(self.node_channels)
        return self._node_nChan

    @node_nChan.setter
    def node_nChan(self, value: list[int]) -> None:...

    @property
    def node_channels(self) -> list[list[str]]:
        if self.cur and self.parent:
            if not self._node_channels:
                if self.parent.gis_point_layer is None:
                    raise ModuleNotFoundError(
                        'No GIS driver available - '
                        'GPKG time series requires PyQGIS or GDAL to determine node connections'
                    )
                time = self.parent.timeSteps()
                if time:
                    time = time[0]
                    for nd in self.node_name:
                        feat = self.parent.gis_point_layer.get_feature_by_field_value('ID', nd)
                        if feat is None:
                            self._node_channels.append([])
                            continue
                        pos = feat.vertices()[0]
                        rect = Rect(pos.x, pos.y, width=1., height=1.)
                        self._node_channels.append(
                            [x['ID'] for x in self.parent.gis_line_layer.get_snapped_features(rect, pos, time)]
                        )
        return self._node_channels

    @node_channels.setter
    def node_channels(self, value: list[list[str]]) -> None:...


class Data1D_GPKG(Data1D):
    """Data1D class for GPKG - lazy load all properties."""

    def __init__(self):
        self.cur = None
        self.parent = None
        self._nNode = -1
        self._nChan = -1
        super().__init__()

    @property
    def nNode(self) -> int:
        if self._nNode == -1:
            if self.parent is not None:
                self._nNode = self.parent.gis_point_feature_count
        return self._nNode

    @nNode.setter
    def nNode(self, value: int) -> None:...

    @property
    def nChan(self) -> int:
        if self._nChan == -1:
            if self.parent is not None:
                self._nChan = self.parent.gis_line_feature_count
        return self._nChan

    @nChan.setter
    def nChan(self, value: int) -> None:...
