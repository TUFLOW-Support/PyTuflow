import tempfile
import os

import pytest

from ...pytuflow._tmf.gis import tuflow_type_requires_feature_iter, gdal_projection
from ...pytuflow._tmf.tfpathlib import TuflowPath, set_prefer_gdal
from ...pytuflow._tmf.tfpathlib.vector_file_open import OGROpen, PyOGRIOOpen

try:
    from shapely.geometry import Point, LineString, Polygon
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

try:
    from osgeo import ogr
    HAS_GDAL = True
except ImportError:
    HAS_GDAL = False

try:
    import geopandas
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False


def test_gdal_projection():
    p = TuflowPath(r'./tests/tmf/test_datasets/models/shp/model/grid/DEM_SI_Unit_01.flt')
    srs = gdal_projection(p)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _point(x, y):
    """Return a Point regardless of whether shapely is available."""
    if HAS_SHAPELY:
        return Point(x, y)
    from osgeo import ogr as _ogr
    p = _ogr.Geometry(_ogr.wkbPoint)
    p.AddPoint_2D(x, y)
    return p


def _line(coords):
    if HAS_SHAPELY:
        return LineString(coords)
    from osgeo import ogr as _ogr
    l = _ogr.Geometry(_ogr.wkbLineString)
    for x, y in coords:
        l.AddPoint_2D(x, y)
    return l


def _polygon(coords):
    if HAS_SHAPELY:
        return Polygon(coords)
    from osgeo import ogr as _ogr
    ring = _ogr.Geometry(_ogr.wkbLinearRing)
    for x, y in coords:
        ring.AddPoint_2D(x, y)
    ring.CloseRings()
    poly = _ogr.Geometry(_ogr.wkbPolygon)
    poly.AddGeometry(ring)
    return poly


# ---------------------------------------------------------------------------
# OGR write tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_GDAL, reason='GDAL not available')
class TestOGRWrite:

    def setup_method(self):
        set_prefer_gdal(True)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.d = self._tmpdir.name

    def teardown_method(self):
        set_prefer_gdal(False)
        self._tmpdir.cleanup()

    def _path(self, name):
        return TuflowPath(os.path.join(self.d, name))

    def test_write_shp_points(self):
        """Create a new shapefile with point features via OGR."""
        p = self._path('pts.shp')
        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            assert isinstance(f, OGROpen)
            f.create_field('Name', 'str')
            f.create_field('Value', 'float')
            f.add_feature(_point(1.0, 2.0), {'Name': 'A', 'Value': 1.5})
            f.add_feature(_point(3.0, 4.0), {'Name': 'B', 'Value': 2.5})

        with p.open_gis('r') as f:
            assert f.feature_count() == 2
            assert 'Point' in f.geometry_types()
            assert f.crs_auth() == 'EPSG:4326'
            feat = f.get_feature(0)
            assert feat['Name'] == 'A'
            assert feat['Value'] == pytest.approx(1.5)

    def test_write_shp_lines(self):
        """Create a shapefile with LineString features."""
        p = self._path('lines.shp')
        with p.open_gis('w', geometry_type='LineString', crs='EPSG:32760') as f:
            f.add_feature(_line([(0, 0), (1, 1), (2, 0)]), {'id': 1})
            f.add_feature(_line([(5, 5), (6, 6)]), {'id': 2})

        with p.open_gis('r') as f:
            assert f.feature_count() == 2
            assert 'LineString' in f.geometry_types()

    def test_write_gpkg_points(self):
        """Create a new GPKG layer with point features."""
        p = TuflowPath(os.path.join(self.d, 'out.gpkg') + ' >> my_points')
        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            assert isinstance(f, OGROpen)
            f.add_feature(_point(10.0, 20.0), {'label': 'p1', 'score': 42})
            f.add_feature(_point(30.0, 40.0), {'label': 'p2', 'score': 99})

        with p.open_gis('r') as f:
            assert f.feature_count() == 2
            feat = f.get_feature(1)
            assert feat['label'] == 'p2'
            assert feat['score'] == 99

    def test_write_gpkg_polygons(self):
        """Create a GPKG layer with polygon features."""
        p = TuflowPath(os.path.join(self.d, 'poly.gpkg') + ' >> polys')
        with p.open_gis('w', geometry_type='Polygon', crs='EPSG:4326') as f:
            f.add_feature(_polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]), {'area': 1.0})

        with p.open_gis('r') as f:
            assert f.feature_count() == 1
            assert 'Polygon' in f.geometry_types()

    def test_write_mode_w_overwrites_layer(self):
        """Opening an existing layer with 'w' should replace it."""
        p = TuflowPath(os.path.join(self.d, 'ow.gpkg') + ' >> lyr')
        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(_point(1, 2), {'id': 1})
            f.add_feature(_point(3, 4), {'id': 2})

        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(_point(9, 9), {'id': 99})

        with p.open_gis('r') as f:
            assert f.feature_count() == 1, 'Layer should have been replaced'
            assert f.get_feature(0)['id'] == 99

    def test_write_mode_rplus_updates_existing_layer(self):
        """Opening with 'r+' should keep existing features and allow adding more."""
        p = TuflowPath(os.path.join(self.d, 'rplus.gpkg') + ' >> lyr')
        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(_point(1, 2), {'id': 1})

        with p.open_gis('r+') as f:
            f.add_feature(_point(3, 4), {'id': 2})

        with p.open_gis('r') as f:
            assert f.feature_count() == 2

    def test_write_mode_rplus_creates_layer_if_missing(self):
        """Opening with 'r+' on a non-existent file should create it."""
        p = TuflowPath(os.path.join(self.d, 'new.gpkg') + ' >> lyr')
        with p.open_gis('r+', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(_point(0, 0), {'id': 1})

        with p.open_gis('r') as f:
            assert f.feature_count() == 1

    def test_auto_field_creation(self):
        """Fields not declared via create_field should be inferred automatically."""
        p = self._path('auto.shp')
        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(_point(0, 0), {'tag': 'hello', 'count': 3, 'ratio': 0.5})

        with p.open_gis('r') as f:
            feat = f.get_feature(0)
            assert feat['tag'] == 'hello'
            assert feat['count'] == 3
            assert feat['ratio'] == pytest.approx(0.5)

    def test_context_manager_closes_on_exit(self):
        """Verify the context manager properly closes and flushes."""
        p = self._path('cm.shp')
        ctx = p.open_gis('w', geometry_type='Point', crs='EPSG:4326')
        ctx.add_feature(_point(1, 1), {'x': 1})
        ctx.close()
        assert ctx.ds is None
        assert ctx.lyr is None

    @pytest.mark.skipif(not HAS_SHAPELY, reason='shapely required')
    def test_wkb_geometry_input(self):
        """add_feature should accept WKB bytes."""
        p = self._path('wkb.shp')
        wkb = Point(7.5, 8.5).wkb
        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(wkb, {'src': 'wkb'})

        with p.open_gis('r') as f:
            feat = f.get_feature(0)
            pts = feat.geom.points()
            assert pts[0][0] == pytest.approx(7.5)
            assert pts[0][1] == pytest.approx(8.5)


# ---------------------------------------------------------------------------
# PyOGRIO (GeoPandas) write tests
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_GEOPANDAS, reason='geopandas not available')
@pytest.mark.skipif(not HAS_SHAPELY, reason='shapely required for GeoPandas backend')
class TestPyOGRIOWrite:

    def setup_method(self):
        set_prefer_gdal(False)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.d = self._tmpdir.name

    def teardown_method(self):
        self._tmpdir.cleanup()

    def _path(self, name):
        return TuflowPath(os.path.join(self.d, name))

    def test_write_shp_points(self):
        """Create a new shapefile with point features via GeoPandas backend."""
        p = self._path('pts.shp')
        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            assert isinstance(f, PyOGRIOOpen)
            f.create_field('Name', 'str')
            f.create_field('Value', 'float')
            f.add_feature(Point(1.0, 2.0), {'Name': 'A', 'Value': 1.5})
            f.add_feature(Point(3.0, 4.0), {'Name': 'B', 'Value': 2.5})

        with p.open_gis('r') as f:
            assert f.feature_count() == 2
            assert 'Point' in f.geometry_types()
            feat = f.get_feature(0)
            assert feat['Name'] == 'A'
            assert feat['Value'] == pytest.approx(1.5)

    def test_write_shp_lines(self):
        """Create a shapefile with LineString features."""
        p = self._path('lines.shp')
        with p.open_gis('w', geometry_type='LineString', crs='EPSG:32760') as f:
            f.add_feature(LineString([(0, 0), (1, 1), (2, 0)]), {'id': 1})
            f.add_feature(LineString([(5, 5), (6, 6)]), {'id': 2})

        with p.open_gis('r') as f:
            assert f.feature_count() == 2
            assert 'LineString' in f.geometry_types()

    def test_write_gpkg_points(self):
        """Create a new GPKG layer with point features."""
        p = TuflowPath(os.path.join(self.d, 'out.gpkg') + ' >> my_points')
        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            assert isinstance(f, PyOGRIOOpen)
            f.add_feature(Point(10.0, 20.0), {'label': 'p1', 'score': 42})
            f.add_feature(Point(30.0, 40.0), {'label': 'p2', 'score': 99})

        with p.open_gis('r') as f:
            assert f.feature_count() == 2
            feat = f.get_feature(1)
            assert feat['label'] == 'p2'

    def test_write_gpkg_polygons(self):
        """Create a GPKG layer with polygon features."""
        p = TuflowPath(os.path.join(self.d, 'poly.gpkg') + ' >> polys')
        with p.open_gis('w', geometry_type='Polygon', crs='EPSG:4326') as f:
            f.add_feature(Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), {'area': 1.0})

        with p.open_gis('r') as f:
            assert f.feature_count() == 1
            assert 'Polygon' in f.geometry_types()

    def test_write_mode_w_overwrites_layer(self):
        """Opening an existing layer with 'w' should replace it."""
        p = TuflowPath(os.path.join(self.d, 'ow.gpkg') + ' >> lyr')
        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(Point(1, 2), {'id': 1})
            f.add_feature(Point(3, 4), {'id': 2})

        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(Point(9, 9), {'id': 99})

        with p.open_gis('r') as f:
            assert f.feature_count() == 1, 'Layer should have been replaced'

    def test_write_mode_rplus_updates_existing_layer(self):
        """Opening with 'r+' should keep existing features and allow adding more."""
        p = TuflowPath(os.path.join(self.d, 'rplus.gpkg') + ' >> lyr')
        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(Point(1, 2), {'id': 1})

        with p.open_gis('r+') as f:
            f.add_feature(Point(3, 4), {'id': 2})

        with p.open_gis('r') as f:
            assert f.feature_count() == 2

    def test_write_mode_rplus_creates_layer_if_missing(self):
        """Opening with 'r+' on a non-existent file should create it."""
        p = TuflowPath(os.path.join(self.d, 'new.gpkg') + ' >> lyr')
        with p.open_gis('r+', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(Point(0, 0), {'id': 1})

        with p.open_gis('r') as f:
            assert f.feature_count() == 1

    def test_auto_field_creation(self):
        """Fields not declared via create_field should be inferred automatically."""
        p = self._path('auto.shp')
        with p.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(Point(0, 0), {'tag': 'hello', 'count': 3, 'ratio': 0.5})

        with p.open_gis('r') as f:
            feat = f.get_feature(0)
            assert feat['tag'] == 'hello'
            assert feat['count'] == 3
            assert feat['ratio'] == pytest.approx(0.5)

    def test_context_manager_closes_on_exit(self):
        """Verify the context manager properly closes and flushes."""
        p = self._path('cm.shp')
        ctx = p.open_gis('w', geometry_type='Point', crs='EPSG:4326')
        ctx.add_feature(Point(1, 1), {'x': 1})
        ctx.close()
        assert ctx.ds is None
        assert ctx.lyr is None

    def test_gpkg_multiple_layers_preserved(self):
        """Writing to one GPKG layer should not delete other layers."""
        db = os.path.join(self.d, 'multi.gpkg')
        layer_a = TuflowPath(db + ' >> layer_a')
        layer_b = TuflowPath(db + ' >> layer_b')

        with layer_a.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(Point(1, 1), {'id': 1})
        with layer_b.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(Point(2, 2), {'id': 2})

        # Overwrite layer_a — layer_b must survive
        with layer_a.open_gis('w', geometry_type='Point', crs='EPSG:4326') as f:
            f.add_feature(Point(9, 9), {'id': 99})

        with layer_a.open_gis('r') as f:
            assert f.feature_count() == 1
        with layer_b.open_gis('r') as f:
            assert f.feature_count() == 1, 'layer_b should not be affected'
