import unittest
from datetime import datetime

import numpy as np
import pandas as pd
import rasterio
import shapely
import geopandas

from pytuflow import XMDF, NCMesh, CATCHJson, DAT, NCGrid, Grid, TuflowPath


def load_comparison_data(path):
    with open(path, 'rb') as f:
        buf = f.read()
    return np.frombuffer(buf)


class TestXMDF(unittest.TestCase):

    def test_load_2dm_only(self):
        twodm = './tests/xmdf/run.2dm'
        res = XMDF(twodm)
        self.assertEqual('run', res.name)
        self.assertEqual(['bed level'], res.data_types())
        df = res.section('./tests/xmdf/section_line.shp', 'bed level', 0)
        self.assertFalse(df.empty)

    def test_data_point(self):
        xmdf = './tests/xmdf/run.xmdf'
        res = XMDF(xmdf)
        point = (1.0, 1.0)
        df = res.data_point(point, 'max h', 0)
        self.assertTrue(isinstance(df, float))
        df = res.data_point(point, 'max vector velocity', 0)
        self.assertTrue(isinstance(df, tuple))
        df = res.data_point(point, ['max h', 'max vector velocity'], 0)
        self.assertEqual((1, 2), df.shape)

    def test_data_point_datetime(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        res = XMDF(xmdf)
        point = './tests/xmdf/xmdf_point.shp'
        time = datetime(1990, 1, 1, 1)
        val = res.data_point(point, 'h', time)
        self.assertTrue(isinstance(val, float))

    def test_section_7(self):
        # this tests when a line intersects a node/vertex exactly
        xmdf = './tests/xmdf/run.xmdf'
        res = XMDF(xmdf)
        line = [(0.5, 0.5), (1.5, 1.5)]
        df = res.section(line, 'max h', 0)
        self.assertEqual((4, 2), df.shape)
        self.assertTrue(df[np.isnan(df.iloc[:, 1])].empty)

        # test opposite direction
        line = [(1.5, 1.5), (0.5, 0.5)]
        df = res.section(line, 'max h', 0)
        self.assertEqual((4, 2), df.shape)
        self.assertTrue(df[np.isnan(df.iloc[:, 1])].empty)

    def test_section_from_shapely_geom(self):
        xmdf = './tests/xmdf/run.xmdf'
        res = XMDF(xmdf)
        line = shapely.LineString([(0.5, 0.5), (1.5, 1.5)])
        df = res.section(line, 'max h', 0)
        self.assertEqual((4, 2), df.shape)
        self.assertTrue(df[np.isnan(df.iloc[:, 1])].empty)

        # multi-line string
        line = shapely.MultiLineString([[(0.5, 0.5), (1.5, 1.5)]])
        df = res.section(line, 'max h', 0)
        self.assertEqual((4, 2), df.shape)
        self.assertTrue(df[np.isnan(df.iloc[:, 1])].empty)

    def test_section_from_feature(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        res = XMDF(xmdf)
        p = TuflowPath('./tests/xmdf/xmdf_line.shp')
        test = res.section('./tests/xmdf/xmdf_line.shp', 'max h', 0).to_numpy()
        with p.open_gis() as fo:
            for feat in fo:
                df = res.section(feat.geom, 'max h', 0)
                equal = (test == df.to_numpy()).all()
                self.assertTrue(equal)

                df = res.section(feat, 'max h', 0)
                equal = (test == df.to_numpy()).all()
                self.assertTrue(equal)

    def test_section_from_geodf(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        res = XMDF(xmdf)
        gdf = geopandas.read_file('./tests/xmdf/xmdf_line.shp')
        test = res.section('./tests/xmdf/xmdf_line.shp', 'max h', 0).to_numpy()
        df = res.section(gdf, 'max h', 0)
        equal = (test == df.to_numpy()).all()
        self.assertTrue(equal)

    def test_maximum_level(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        res = XMDF(xmdf)
        mx = res.maximum('h')
        self.assertTrue(np.isclose(50.42428207, mx).all())

    def test_maximum_multiple_result_types(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        res = XMDF(xmdf)
        mx = res.maximum(['h', 'd', 'v'])
        self.assertEqual((3, 1), mx.shape)
        self.assertTrue(np.isclose([50.42428, 3.03354, 3.03524], mx.to_numpy().flatten()).all())

    def test_minimum_level(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        res = XMDF(xmdf)
        mn = res.minimum('h')
        self.assertTrue(np.isclose(35.9343795, mn).all())

    def test_minimum_multiple_result_types(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        res = XMDF(xmdf)
        mn = res.minimum(['h', 'd', 'v'])
        self.assertEqual((3, 1), mn.shape)
        self.assertTrue(np.isclose([35.9343795, 0., 0.], mn.to_numpy().flatten()).all())

    def test_surface(self):
        xmdf = './tests/xmdf/run.xmdf'
        res = XMDF(xmdf)
        df = res.surface('h', 0.)
        self.assertEqual((25, 4), df.shape)

    def test_surface_max(self):
        xmdf = './tests/xmdf/run.xmdf'
        res = XMDF(xmdf)
        df = res.surface('max h', 0.)
        self.assertEqual((25, 4), df.shape)

    def test_surface_vector(self):
        xmdf = './tests/xmdf/run.xmdf'
        res = XMDF(xmdf)
        df = res.surface('vector vel', 0.)
        self.assertEqual((25, 5), df.shape)

    def test_surface_vector_max(self):
        xmdf = './tests/xmdf/run.xmdf'
        res = XMDF(xmdf)
        df = res.surface('max vector vel', 0.)
        self.assertEqual((25, 5), df.shape)

    def test_flux(self):
        p = './tests/xmdf/EG00_001.xmdf'
        res = XMDF(p)
        df = res.flux('./tests/xmdf/xmdf_flux_line.shp', '')
        self.assertEqual((7, 1), df.shape)
        self.assertAlmostEqual(76.108, float(df.iloc[:,0].max()), places=3)
        df_r = res.flux('./tests/xmdf/xmdf_flux_line_reversed.shp', '')
        is_close = np.isclose(df.iloc[:,0], df_r.iloc[:,0] * -1)
        self.assertTrue(is_close.all())

    def test_flux_tracer(self):
        p = './tests/xmdf/EG17_001.xmdf'
        res = XMDF(p)
        df = res.flux('./tests/xmdf/xmdf_flux_line.shp', 'conc tracer1', use_unit_flow=False)
        self.assertAlmostEqual(116.031, float(df.iloc[:,0].max()), places=3)

        df = res.flux('./tests/xmdf/xmdf_flux_line.shp', 'conc tracer1', use_unit_flow=True)
        self.assertAlmostEqual(123.393, float(df.iloc[:,0].max()), places=3)



class TestDAT(unittest.TestCase):

    def test_load(self):
        p = './tests/dat/small_model_001.ALL.sup'
        res = DAT(p)
        self.assertEqual('small_model_001', res.name)
        self.assertFalse(res.has_reference_time)

    def test_load_2(self):
        p = ['./tests/dat/small_model_001_d.dat', './tests/dat/small_model_001_V.dat',
             './tests/dat/small_model_001_h.dat', './tests/dat/small_model_001_q.dat',
             './tests/dat/small_model_001_Times.dat']
        res = DAT(p)
        self.assertEqual('small_model_001', res.name)

    def test_times(self):
        p = './tests/dat/small_model_001.ALL.sup'
        res = DAT(p)
        times = res.times()
        self.assertEqual(13, len(times))

    def test_data_types(self):
        p = './tests/dat/small_model_001.ALL.sup'
        res = DAT(p)
        dtypes = res.data_types()
        self.assertEqual(8, len(dtypes))

    def test_newer_format(self):
        p = './tests/dat/small_model_002_h.dat'  # model name is now 80 characters long rather than 40
        res = DAT(p)
        dtypes = res.data_types()
        self.assertEqual(sorted(['bed level', 'water level', 'max water level']), sorted(dtypes))

    def test_time_series(self):
        p = './tests/dat/small_model_002_h.dat'
        res = DAT(p)
        df = res.time_series((1.0, 1.0), 'water level')
        self.assertEqual((13, 1), df.shape)

    def test_section(self):
        p = './tests/dat/small_model_002_h.dat'
        res = DAT(p)
        df = res.section([(1.5, 1.2), (2.5, 1.2)], 'water level', 1.0)
        self.assertEqual((4, 2), df.shape)

    def test_maximum_level(self):
        p = './tests/dat/EG00_001_h.dat'
        res = DAT(p)
        mx = res.maximum('water level')
        self.assertTrue(np.isclose(mx, 50.4242821).all())

    def test_maximum_velocity_vector(self):
        p = './tests/dat/EG00_001_V.dat'
        res = DAT(p)
        mx = res.maximum('velocity')
        self.assertTrue(np.isclose(mx, 3.03523898).all())

    def test_maximum_max_level(self):
        p = './tests/dat/EG00_001_h.dat'
        res = DAT(p)
        mx = res.maximum('max water level')
        self.assertTrue(np.isclose(mx, 50.42952346801758).all())

    def test_maximum_bed_level(self):
        p = './tests/dat/EG00_001_h.dat'
        res = DAT(p)
        mx = res.maximum('bed level')
        self.assertTrue(np.isclose(mx, 100.).all())

    def test_minimum_level(self):
        p = './tests/dat/EG00_001_h.dat'
        res = DAT(p)
        mn = res.minimum('water level')
        self.assertTrue(np.isclose(mn, 35.9343795).all())

    def test_minimum_bed_level(self):
        p = './tests/dat/EG00_001_h.dat'
        res = DAT(p)
        mn = res.minimum('bed level')
        self.assertTrue(np.isclose(mn, 36.01).all())


class TestNCMesh(unittest.TestCase):

    def test_load(self):
        nc = './tests/nc_mesh/fv_res.nc'
        res = NCMesh(nc)
        self.assertEqual('fv_res', res.name)
        self.assertFalse(res.has_reference_time)

    def test_time_series_averaging(self):
        nc = './tests/nc_mesh/fv_res.nc'
        res = NCMesh(nc)
        df = res.time_series((1.5, 4.5), 'vel', averaging_method='singlelevel?dir=top&1')
        self.assertEqual((7, 1), df.shape)

    def test_section_averaging(self):
        nc = './tests/nc_mesh/fv_res.nc'
        res = NCMesh(nc)
        line = [(1.4, 4.5), (3.6, 4.2)]
        df = res.section(line, 'v', 0, averaging_method='sigma&0.1&0.9')
        self.assertEqual((6, 2), df.shape)

    def test_maximum_water_level(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        res = NCMesh(nc)
        mx = res.maximum('h')
        self.assertTrue(np.isclose(mx, 0.185768127).all())

    def test_maximum_salinity(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        res = NCMesh(nc)
        mx = res.maximum('sal', averaging_method=None)
        self.assertTrue(np.isclose(mx, 34.9937744).all())

    def test_maximum_velocity(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        res = NCMesh(nc)
        mx = res.maximum('V', averaging_method=None)
        self.assertTrue(np.isclose(mx, 0.42056167).all())

    def test_maximum_salinity_depth_averaged(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        res = NCMesh(nc)
        mx = res.maximum('sal', averaging_method='sigma&0.0&1.0')
        self.assertTrue(np.isclose(mx, 34.9360265569985).all())
        mx = res.maximum('sal', averaging_method='singlelevel?dir=top&1')
        self.assertTrue(np.isclose(mx, 34.6935348510742).all())

    def test_maximum_velocity_depth_averaged(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        res = NCMesh(nc)
        mx = res.maximum('V', averaging_method='sigma&0.0&1.0')
        self.assertTrue(np.isclose(mx, 0.419554057591823).all())
        mx = res.maximum('V', averaging_method='singlelevel?dir=bottom&1')
        self.assertTrue(np.isclose(mx, 0.419554057591823).all())

    def test_minimum_salinity(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        res = NCMesh(nc)
        mn = res.minimum('sal', averaging_method=None)
        self.assertTrue(np.isclose(mn, 0., atol=0.0001).all())

    def test_surface(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        res = NCMesh(nc)
        df = res.surface('h', 186972, coord_scope='local')
        self.assertEqual(df.shape, (1375, 4))

    def test_surface_vector(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        res = NCMesh(nc)
        df = res.surface('v', 186972)
        self.assertEqual(df.shape, (1375, 5))

    def test_surface_to_vertex(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        res = NCMesh(nc)
        df = res.surface('H', 186972, averaging_method='sigma&0&1', coord_scope='local', to_vertex=True)
        self.assertEqual(df.shape, (1419, 4))

    def test_flux_2d(self):
        nc = './tests/nc_mesh/Trap_Steady_000.nc'
        res = NCMesh(nc)
        df = res.flux('./tests/nc_mesh/fv_steady_2d_flux_line.shp', '')
        self.assertEqual((37, 1), df.shape)
        self.assertAlmostEqual(446.486, float(df.iloc[:,0].max()), places=3)

    def test_flux_3d(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        res = NCMesh(nc)
        df = res.flux('./tests/nc_mesh/fv_estuary_flux_line.shp', '')
        self.assertEqual((5, 1), df.shape)
        self.assertAlmostEqual(85.971, float(df.iloc[:,0].max()), places=3)
        self.assertAlmostEqual(-39.142, float(df.iloc[:,0].min()), places=3)
        df_r = res.flux('./tests/nc_mesh/fv_estuary_flux_line_reversed.shp', '')
        is_close = np.isclose(df.iloc[:,0], df_r.iloc[:,0] * -1)
        self.assertTrue(is_close.all())

        df2 = res.flux('./tests/nc_mesh/fv_estuary_flux_line_2.shp', '')
        df2_r = res.flux('./tests/nc_mesh/fv_estuary_flux_line_2_reversed.shp', '')
        is_close = np.isclose(df.iloc[:,0], df_r.iloc[:,0] * -1)
        self.assertTrue(is_close.all())
        self.assertAlmostEqual(85.970, float(df2.iloc[:,0].max()), places=3)
        self.assertAlmostEqual(-39.141, float(df2.iloc[:,0].min()), places=3)

    def test_flux_3d_sal(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        res = NCMesh(nc)
        df = res.flux('./tests/nc_mesh/fv_estuary_flux_line.shp', 'sal')
        self.assertAlmostEqual(875.946, float(df.iloc[:,0].max()), places=3)
        self.assertAlmostEqual(-391.437, float(df.iloc[:,0].min()), places=3)


class TestCATCHJson(unittest.TestCase):

    def test_load(self):
        p = './tests/catch_json/res.tuflow.json'
        res = CATCHJson(p)
        self.assertEqual('res', res.name)
        self.assertTrue(res.has_reference_time)

    def test_times(self):
        p = './tests/catch_json/res.tuflow.json'
        res = CATCHJson(p)
        times = res.times()
        self.assertEqual(7, len(times))

    def test_data_types(self):
        p = './tests/catch_json/res.tuflow.json'
        res = CATCHJson(p)
        dtypes = res.data_types()
        self.assertEqual(10, len(dtypes))

    def test_data_point(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        res = CATCHJson(p)
        df = res.data_point(point, 'water level', 0.)
        self.assertTrue(isinstance(df, float))

    def test_data_point_2(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 3.5)
        res = CATCHJson(p)
        df = res.data_point(point, 'vector velocity', 0.)
        self.assertTrue(isinstance(df, tuple))

    def test_data_point_3(self):
        p = './tests/catch_json/res.tuflow.json'
        points = [(1.5, 4.5), (1.5, 3.5)]
        res = CATCHJson(p)
        df = res.data_point(points, ['h', 'v'], 0.)
        self.assertTrue(isinstance(df, pd.DataFrame))
        self.assertEqual((2, 2), df.shape)
        self.assertEqual(0, np.flatnonzero(df.isna()).size)

    def test_time_series(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        res = CATCHJson(p)
        df = res.time_series(point, 'water level')
        self.assertEqual((7, 1), df.shape)

    def test_time_series_2(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        res = CATCHJson(p)
        df = res.time_series(point, 'water level', time_fmt='absolute')
        self.assertEqual((7, 1), df.shape)

    def test_section(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        res = CATCHJson(p)
        df = res.section(line, 'water level', 0.)
        self.assertEqual((9, 2), df.shape)

    def test_section_2(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        res = CATCHJson(p)
        df = res.section(line, ['water level', 'velocity'], 0.)
        self.assertEqual((9, 3), df.shape)

    def test_section_3(self):
        p = './tests/catch_json/res_reversed.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        res = CATCHJson(p)
        df = res.section(line, ['water level'], 0.)
        self.assertEqual((9, 2), df.shape)

    def test_section_4(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_reversed.shp'
        res = CATCHJson(p)
        df = res.section(line, ['water level'], 0.)
        self.assertEqual((9, 2), df.shape)

    def test_section_5(self):
        p = './tests/catch_json/res_reversed.tuflow.json'
        line = './tests/catch_json/section_line_reversed.shp'
        res = CATCHJson(p)
        df = res.section(line, ['water level'], 0.)
        self.assertEqual((9, 2), df.shape)

    def test_section_6(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook.shp'
        res = CATCHJson(p)
        df = res.section(line, ['water level'], 0.)
        self.assertEqual((12, 2), df.shape)

    def test_section_7(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook_reversed.shp'
        res = CATCHJson(p)
        df = res.section(line, ['water level'], 0.)
        self.assertEqual((8, 2), df.shape)

    def test_section_8(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/xmdf/section_line_long.shp'
        res = CATCHJson(p)
        df = res.section(line, ['water level'], 0.)
        self.assertEqual((9, 2), df.shape)

    def test_section_9(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/catch_json/section_line_ugly.shp'
        res = CATCHJson(p)
        df = res.section(line, ['water level'], 0.)
        self.assertEqual((16, 2), df.shape)

    def test_curtain(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        res = CATCHJson(p)
        df = res.curtain(line, 'velocity', 0.)
        self.assertEqual((24, 4), df.shape)

    def test_curtain_2(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook.shp'
        res = CATCHJson(p)
        df = res.curtain(line, 'velocity', 0.)
        self.assertEqual((40, 4), df.shape)

    def test_curtain_3(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook_reversed.shp'
        res = CATCHJson(p)
        df = res.curtain(line, 'velocity', 0.)
        self.assertEqual((32, 4), df.shape)

    def test_curtain_4(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/xmdf/section_line_long.shp'
        res = CATCHJson(p)
        df = res.curtain(line, 'velocity', 0.)
        self.assertEqual((24, 4), df.shape)

    def test_curtain_5(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/catch_json/section_line_ugly.shp'
        res = CATCHJson(p)
        df = res.curtain(line, 'velocity', 0.)
        self.assertEqual((64, 4), df.shape)

    def test_profile(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        res = CATCHJson(p)
        df = res.profile(point, 'v', 0)
        self.assertEqual((4, 2), df.shape)

    def test_profile_2(self):
        p = './tests/catch_json/res.tuflow.json'
        shp = './tests/xmdf/time_series_point.shp'
        res = CATCHJson(p)
        df = res.profile(shp, 'v', 0)
        self.assertEqual((2, 2), df.shape)

    def test_maximum(self):
        p = './tests/catch_json/res.tuflow.json'
        res = CATCHJson(p)
        mx = res.maximum('h')
        self.assertTrue(np.isclose(mx, 1.0).all())

    def test_minimum(self):
        p = './tests/catch_json/res.tuflow.json'
        res = CATCHJson(p)
        mn = res.minimum('h')
        self.assertTrue(np.isclose(mn, 0.).all())


class TestQuadtree(unittest.TestCase):

    def test_simple_line_1(self):
        p = './tests/quadtree/EG13_001.xmdf'
        line = './tests/quadtree/simple_line_1.shp'
        res = XMDF(p)
        df = res.section(line, 'water level', 1.)
        self.assertEqual((4, 2), df.shape)

    def test_simple_line_2(self):
        p = './tests/quadtree/EG13_001.xmdf'
        line = './tests/quadtree/simple_line_2.shp'
        res = XMDF(p)
        df = res.section(line, 'water level', 1.)
        self.assertEqual((4, 2), df.shape)


class TestNCGrid(unittest.TestCase):

    def test_surface(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        df = res.surface('h', 0, to_vertex=False, coord_scope='global')
        self.assertEqual((25, 4), df.shape)

    def test_surface_vertex(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        df = res.surface('h', 0, to_vertex=True, coord_scope='global')
        self.assertEqual((36, 4), df.shape)

    def test_surface_vector_direction(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        df = res.surface('velocity direction', 1.5, direction_to_vector=True)
        self.assertEqual((25, 5), df.shape)

    def test_surface_vertex_vector_direction(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        df = res.surface('velocity direction', 1.5, to_vertex=True, direction_to_vector=True)
        self.assertEqual((36, 5), df.shape)

    def test_surface_local(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        df = res.surface('h', 0, to_vertex=False, coord_scope='local')
        self.assertEqual((25, 4), df.shape)
        self.assertEqual(-2, df.x.min())

    def test_to_mesh(self):
        p = './tests/nc_grid/EG00_001.nc'
        res = NCGrid(p)
        mesh = res.to_mesh('max water level')
        df = mesh.surface('water level', 0.5)
        self.assertEqual((6530, 4), df.shape)

    def test_to_mesh_time_series(self):
        p = './tests/nc_grid/EG00_001.nc'
        point = './tests/xmdf/xmdf_point.shp'
        res = NCGrid(p)
        mesh = res.to_mesh('max water level')
        df = mesh.time_series(point, 'h')
        df_grid = res.time_series(point, 'h')
        self.assertEqual(df_grid.shape, df.shape)
        is_close = np.isclose(df.to_numpy(), df_grid.to_numpy(), equal_nan=True)
        self.assertTrue(is_close.all())

    def test_to_mesh_section(self):
        p = './tests/nc_grid/EG00_001.nc'
        line = './tests/xmdf/xmdf_line.shp'
        res = NCGrid(p)
        mesh = res.to_mesh('max water level')
        df = mesh.section(line, 'h', 1.5)
        df_grid = res.section(line, 'h', 1.5)
        self.assertEqual(df_grid.shape, df.shape)
        is_close = np.isclose(df.to_numpy(), df_grid.to_numpy(), atol=0.0001, equal_nan=True)
        self.assertTrue(is_close.all())

    def test_to_mesh_surface(self):
        p = './tests/nc_grid/EG00_001.nc'
        res = NCGrid(p)
        mesh = res.to_mesh('max water level')
        df = mesh.surface('max water level', -1, to_vertex=True)
        df_grid = res.surface('max water level', -1, to_vertex=True)

        a = df.loc[df['active'], ['x', 'y', 'value']].to_numpy()
        b = df_grid.loc[df_grid['active'], ['x', 'y', 'value']].to_numpy()
        self.assertEqual(b.shape, a.shape)
        is_close = np.isclose(a, b, atol=0.0001, equal_nan=True)
        self.assertTrue(is_close.all())

    def test_to_mesh_surface_vector(self):
        p = './tests/nc_grid/EG00_001.nc'
        res = NCGrid(p)
        mesh = res.to_mesh('max water level')
        df = mesh.surface('vector velocity', 1.5)
        self.assertEqual((6530, 5), df.shape)

    def test_to_mesh_surface_vertex_vector(self):
        p = './tests/nc_grid/EG00_001.nc'
        res = NCGrid(p)
        mesh = res.to_mesh('max water level')
        df = mesh.surface('vector velocity', 1.5, to_vertex=True)
        self.assertEqual((6871, 5), df.shape)

    def test_flux_vel_depth(self):
        p = './tests/nc_grid/EG00_001_unit_flow.nc'
        line = './tests/xmdf/xmdf_flux_line.shp'
        line_rev = './tests/xmdf/xmdf_flux_line_reversed.shp'
        res = NCGrid(p)
        df = res.flux(line, '', use_unit_flow=False)
        self.assertEqual((7, 1), df.shape)
        self.assertAlmostEqual(80.436, float(df.iloc[:, 0].max()), places=3)
        # reversed line must give identical magnitude with opposite sign
        df_r = res.flux(line_rev, '', use_unit_flow=False)
        self.assertTrue(np.isclose(df.iloc[:, 0].values, -df_r.iloc[:, 0].values).all())

    def test_flux_unit_flow(self):
        p = './tests/nc_grid/EG00_001_unit_flow.nc'
        line = './tests/xmdf/xmdf_flux_line.shp'
        line_rev = './tests/xmdf/xmdf_flux_line_reversed.shp'
        res = NCGrid(p)
        df = res.flux(line, '', use_unit_flow=True)
        self.assertEqual((7, 1), df.shape)
        self.assertAlmostEqual(82.204, float(df.iloc[:, 0].max()), places=3)
        # reversed line must give identical magnitude with opposite sign
        df_r = res.flux(line_rev, '', use_unit_flow=True)
        self.assertTrue(np.isclose(df.iloc[:, 0].values, -df_r.iloc[:, 0].values).all())

    def test_flux_vel_depth_tracer(self):
        p = './tests/nc_grid/EG17_001.nc'
        line = './tests/xmdf/xmdf_flux_line.shp'
        line_rev = './tests/xmdf/xmdf_flux_line_reversed.shp'
        res = NCGrid(p)
        df = res.flux(line, 'ad01_conc', use_unit_flow=False)
        self.assertEqual((7, 1), df.shape)
        self.assertAlmostEqual(130.778, float(df.iloc[:, 0].max()), places=3)
        df_r = res.flux(line_rev, 'ad01_conc', use_unit_flow=False)
        self.assertTrue(np.isclose(df.iloc[:, 0].values, -df_r.iloc[:, 0].values).all())

    def test_flux_grid_mesh(self):
        p = './tests/nc_grid/EG17_001.nc'
        line = './tests/xmdf/xmdf_flux_line.shp'
        res = NCGrid(p).to_mesh()
        df = res.flux(line)
        self.assertAlmostEqual(88, float(df.iloc[:, 0].max()), places=0)

        df = res.flux(line, use_unit_flow=False)
        self.assertAlmostEqual(86, float(df.iloc[:, 0].max()), places=0)

    def test_flux_grid_mesh_tracer(self):
        p = './tests/nc_grid/EG17_001.nc'
        line = './tests/xmdf/xmdf_flux_line.shp'
        line_rev = './tests/xmdf/xmdf_flux_line_reversed.shp'
        res = NCGrid(p).to_mesh()
        df = res.flux(line, 'ad01_conc', use_unit_flow=True)
        self.assertEqual((7, 1), df.shape)
        self.assertAlmostEqual(137.143, float(df.iloc[:, 0].max()), places=3)
        df_r = res.flux(line_rev, 'ad01_conc', use_unit_flow=True)
        self.assertTrue(np.isclose(df.iloc[:, 0].values, -df_r.iloc[:, 0].values).all())

        df = res.flux(line, 'ad01_conc', use_unit_flow=False)
        self.assertAlmostEqual(130.778, float(df.iloc[:, 0].max()), places=3)
        df_r = res.flux(line_rev, 'ad01_conc', use_unit_flow=False)
        self.assertTrue(np.isclose(df.iloc[:, 0].values, -df_r.iloc[:, 0].values).all())


class TestGrid(unittest.TestCase):

    def test_grid_file(self):
        p = 'NETCDF:"./tests/nc_grid/small_model_001.nc":maximum_water_level'
        res = Grid(p)
        self.assertEqual(1., res.dx)
        self.assertEqual(1., res.dy)
        self.assertEqual(5, res.ncol)
        self.assertEqual(5, res.nrow)
        self.assertEqual(0., res.ox)
        self.assertEqual(0., res.oy)
        a = res.surface()
        self.assertEqual((25, 4), a.shape)

    def test_preloaded_array(self):
        p = 'NETCDF:"./tests/nc_grid/small_model_001.nc":maximum_water_level'
        ds = rasterio.open(p)
        a = ds.read(1)
        ds.close()
        d = {
            'dx': 1.,
            'dy': 1.,
            'ncol': 5,
            'nrow': 5,
            'ox': 0.,
            'oy': 0.,
            'nodatavalue': -9999,
            'data_type': 'maximum_water_level',
            'timesteps': -1,
            'data': a,
        }
        res = Grid(d)
        self.assertEqual(1., res.dx)
        self.assertEqual(1., res.dy)
        self.assertEqual(5, res.ncol)
        self.assertEqual(5, res.nrow)
        self.assertEqual(0., res.ox)
        self.assertEqual(0., res.oy)
        a = res.surface()
        self.assertEqual((25, 4), a.shape)

        # test temporal dataset
        p = 'NETCDF:"./tests/nc_grid/small_model_001.nc":water_level'
        ds = rasterio.open(p)
        a = ds.read()
        d['timesteps'] = np.arange(ds.count) * 0.25
        d['data_type'] = 'water level'
        d['data'] = a
        ds.close()
        res = Grid(d)
        self.assertEqual(13, len(res.times()))


class TestPyMeshRegression(unittest.TestCase):

    def test_pymesh_vertex_mesh(self):
        p = './tests/xmdf/EG00_001.xmdf'
        point = './tests/xmdf/xmdf_point.shp'
        line = './tests/xmdf/xmdf_line.shp'
        line_outside_mesh = './tests/xmdf/xmdf_line_outside_mesh.shp'
        comp = './tests/regression_test_comparisons/test_qgis_vertex_mesh'

        res = XMDF(p)

        # data point
        a = res.data_point(point, 'water level', 1.)
        b = load_comparison_data(f'{comp}_time_series.data').reshape(-1, 2)[2, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        # time series
        a = res.time_series(point, 'water level').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # time series vector
        a = res.time_series(point, 'vector velocity').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series_vec.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # section
        a = res.section(line, 'water level', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # section vector
        a = res.section(line, 'vector velocity', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_vec.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # section lines that start/end outside the mesh
        a = res.section(line_outside_mesh, 'water level', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_outside_mesh.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # section lines that start/end outside the mesh - vector
        a = res.section(line_outside_mesh, 'velocity', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_outside_mesh_vec.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # profile
        a = res.profile(point, 'velocity', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_profile.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # profile vector
        a = res.profile(point, 'vector velocity', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_profile_vec.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # curtain scalar
        a = res.curtain(line, 'z0', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_curtain.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True, atol=0.0001)
        self.assertTrue(is_close.all())

        # curtain vector
        a = res.curtain(line, 'velocity', 1.).reset_index().to_numpy()
        a = np.column_stack((a[..., :3], np.vstack(a[..., 3]), np.vstack(a[..., 4]))).astype('f8')
        b = load_comparison_data(f'{comp}_curtain_vec.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True, atol=0.0001)
        self.assertTrue(is_close.all())

        # curtain outside mesh
        a = res.curtain(line_outside_mesh, 'z0', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_curtain_outside_mesh.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # curtain outside mesh vector
        a = res.curtain(line_outside_mesh, 'velocity', 1.).reset_index().to_numpy()
        df = pd.DataFrame(a)
        df1 = df.loc[:, :3].copy()

        m = ~df.loc[:, 3].isna()
        df1[3] = np.nan
        df1[4] = np.nan
        df1[5] = np.nan
        df1[6] = np.nan
        df1.loc[m, [3, 4]] = np.vstack(df.loc[m, 3])
        df1.loc[m, [5, 6]] = np.vstack(df.loc[m, 4])
        df1[7] = a[:, 5]
        df1[8] = a[:, 6]

        m = ~df.loc[:, 7].isna()
        df1[9] = np.nan
        df1[10] = np.nan
        df1[11] = np.nan
        df1[12] = np.nan
        df1.loc[m, [9, 10]] = np.vstack(df.loc[m, 7])
        df1.loc[m, [11, 12]] = np.vstack(df.loc[m, 8])
        df1[13] = a[:, 9]
        df1[14] = a[:, 10]

        m = ~df.loc[:, 11].isna()
        df1[15] = np.nan
        df1[16] = np.nan
        df1[17] = np.nan
        df1[18] = np.nan
        df1.loc[m, [15, 16]] = np.vstack(df.loc[m, 11])
        df1.loc[m, [17, 18]] = np.vstack(df.loc[m, 12])

        a = df1.astype(float).to_numpy()
        b = load_comparison_data(f'{comp}_curtain_outside_mesh_vec.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True, atol=0.0001)
        self.assertTrue(is_close.all())

    def test_qgis_dat_mesh(self):
        p = './tests/dat/EG00_001.ALL.sup'
        point = './tests/xmdf/xmdf_point.shp'
        line = './tests/xmdf/xmdf_line.shp'
        comp = './tests/regression_test_comparisons/test_qgis_dat_mesh'

        res = DAT(p)

        # data point
        a = res.data_point(point, 'water level', 1.)
        b = load_comparison_data(f'{comp}_time_series.data').reshape(-1, 2)[2, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        # time series
        a = res.time_series(point, 'water level').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # section
        a = res.section(line, 'water level', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

    def test_pymesh_cell_mesh_latlong(self):
        p = './tests/nc_mesh/EST000_3D_001.nc'
        point = './tests/nc_mesh/ncmesh_point_longlat.shp'
        line = './tests/nc_mesh/ncmesh_line_longlat.shp'
        line_outside_mesh = './tests/nc_mesh/ncmesh_line_longlat_outside_mesh.shp'
        line_outside_mesh_2 = './tests/nc_mesh/ncmesh_line_longlat_outside_mesh_2.shp'
        comp = './tests/regression_test_comparisons/test_qgis_cell_mesh_latlong'

        res = NCMesh(p)

        # data point
        a = res.data_point(point, 'salinity', 186972)
        b = load_comparison_data(f'{comp}_time_series.data').reshape(-1, 2)[4, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        # data point level
        a = res.data_point(point, 'h', 186972)
        b = load_comparison_data(f'{comp}_time_series_h.data').reshape(-1, 2)[4, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        # data point vector
        a = res.data_point(point, 'velocity', 186972)
        b = (0.028592855, -0.020573288)
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        # data point with depth averaging
        a = res.data_point(point, 'salinity', 186972, averaging_method='singlelevel?dir=top&4')
        b = load_comparison_data(f'{comp}_time_series_single_top_4.data').reshape(-1, 2)[4, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        a = res.data_point(point, 'salinity', 186972, averaging_method='singlelevel?dir=bottom&2')
        b = load_comparison_data(f'{comp}_time_series_single_bottom_2.data').reshape(-1, 2)[4, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        a = res.data_point(point, 'salinity', 186972, averaging_method='multilevel?dir=top&2&4')
        b = load_comparison_data(f'{comp}_time_series_multi_top_2_4.data').reshape(-1, 2)[4, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        a = res.data_point(point, 'salinity', 186972, averaging_method='multilevel?dir=bottom&2&4')
        b = load_comparison_data(f'{comp}_time_series_multi_bottom_2_4.data').reshape(-1, 2)[4, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        a = res.data_point(point, 'salinity', 186972, averaging_method='depth&0.5&2.0')
        b = load_comparison_data(f'{comp}_time_series_depth_05_2.data').reshape(-1, 2)[4, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        a = res.data_point(point, 'salinity', 186972, averaging_method='height&0.5&2.0')
        b = load_comparison_data(f'{comp}_time_series_height_05_2.data').reshape(-1, 2)[4, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        a = res.data_point(point, 'salinity', 186972, averaging_method='elevation&-5&0')
        b = load_comparison_data(f'{comp}_time_series_elevation_5_0.data').reshape(-1, 2)[4, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        a = res.data_point(point, 'salinity', 186972, averaging_method='sigma&0.1&0.9')
        b = load_comparison_data(f'{comp}_time_series_sigma_01_09.data').reshape(-1, 2)[4, 1]
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        # time series
        a = res.time_series(point, 'salinity').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # time series level
        a = res.time_series(point, 'h').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series_h.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # time series with depth averaging
        a = res.time_series(point, 'salinity', averaging_method='singlelevel?dir=top&4').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series_single_top_4.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        a = res.time_series(point, 'salinity', averaging_method='singlelevel?dir=bottom&2').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series_single_bottom_2.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        a = res.time_series(point, 'salinity', averaging_method='multilevel?dir=top&2&4').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series_multi_top_2_4.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        a = res.time_series(point, 'salinity', averaging_method='multilevel?dir=bottom&2&4').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series_multi_bottom_2_4.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        a = res.time_series(point, 'salinity', averaging_method='depth&0.5&2.0').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series_depth_05_2.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        a = res.time_series(point, 'salinity', averaging_method='height&0.5&2.0').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series_height_05_2.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        a = res.time_series(point, 'salinity', averaging_method='elevation&-5&0').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series_elevation_5_0.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        a = res.time_series(point, 'salinity', averaging_method='sigma&0.1&0.9').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series_sigma_01_09.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # section
        a = res.section(line, 'salinity', 186969).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:,1], b[:,1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:,2], b[:,2], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        # section level
        a = res.section(line, 'h', 186969).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_h.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        # section with depth averaging
        a = res.section(line, 'salinity', 186969, averaging_method='singlelevel?dir=top&4').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_single_top_4.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        a = res.section(line, 'salinity', 186969, averaging_method='singlelevel?dir=bottom&4').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_single_bottom_4.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        a = res.section(line, 'salinity', 186969, averaging_method='multilevel?dir=top&2&4').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_multi_top_2_4.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        a = res.section(line, 'salinity', 186969,averaging_method='multilevel?dir=bottom&2&4').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_multi_bottom_2_4.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        a = res.section(line, 'salinity', 186969, averaging_method='depth&0.5&2.0').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_depth_05_2.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        a = res.section(line, 'salinity', 186969, averaging_method='height&0.5&2.0').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_height_05_2.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        a = res.section(line, 'salinity', 186969, averaging_method='elevation&-5&0').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_elevation_5_0.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        a = res.section(line, 'salinity', 186969, averaging_method='sigma&0.1&0.9').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_sigma_01_09.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        # section outside mesh
        a = res.section(line_outside_mesh, 'salinity', 186969).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_outside_mesh.data').reshape(a.shape)
        is_close_offset1 = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val1 = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        is_close_offset2 = np.isclose(a[:, 3], b[:, 3], atol=1, equal_nan=True)
        is_close_val2 = np.isclose(a[:, 4], b[:, 4], equal_nan=True)
        is_close_offset3 = np.isclose(a[:, 5], b[:, 5], atol=1, equal_nan=True)
        is_close_val3 = np.isclose(a[:, 6], b[:, 6], equal_nan=True)
        self.assertTrue(is_close_offset1.all())
        self.assertTrue(is_close_val1.all())
        self.assertTrue(is_close_offset2.all())
        self.assertTrue(is_close_val2.all())
        self.assertTrue(is_close_offset3.all())
        self.assertTrue(is_close_val3.all())

        # section outside mesh vector
        a = res.section(line_outside_mesh, 'velocity', 186969).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_outside_mesh_vec.data').reshape(a.shape)
        is_close_offset1 = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val1 = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        is_close_offset2 = np.isclose(a[:, 3], b[:, 3], atol=1, equal_nan=True)
        is_close_val2 = np.isclose(a[:, 4], b[:, 4], equal_nan=True)
        is_close_offset3 = np.isclose(a[:, 5], b[:, 5], atol=1, equal_nan=True)
        is_close_val3 = np.isclose(a[:, 6], b[:, 6], equal_nan=True)
        self.assertTrue(is_close_offset1.all())
        self.assertTrue(is_close_val1.all())
        self.assertTrue(is_close_offset2.all())
        self.assertTrue(is_close_val2.all())
        self.assertTrue(is_close_offset3.all())
        self.assertTrue(is_close_val3.all())

        # section outside mesh - leaves and re-enters mesh in a single segment
        a = res.section(line_outside_mesh_2, 'salinity', 186969).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section_outside_mesh_reenters.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        # profile
        a = res.profile(point, 'salinity', 186969).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_profile.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # profile linear interpolation
        a = res.profile(point, 'salinity', 186969, 'linear').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_profile_linear.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # curtain
        a = res.curtain(line, 'salinity', 186969).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_curtain.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2:], b[:, 2:], equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())

        # curtain vector
        a = res.curtain(line, 'velocity', 186969).reset_index().to_numpy()
        a = np.column_stack((a[...,:3], np.vstack(a[...,3]), np.vstack(a[...,4]))).astype('f8')
        b = load_comparison_data(f'{comp}_curtain_vec.data').reshape(a.shape)
        is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val = np.isclose(a[:, 2:5], b[:, 2:5], equal_nan=True)
        is_close_local_vec = np.isclose(a[:, 5:], b[:, 5:], atol=0.1, equal_nan=True)
        self.assertTrue(is_close_offset.all())
        self.assertTrue(is_close_val.all())
        self.assertTrue(is_close_local_vec.all())

        # curtain outside mesh
        a = res.curtain(line_outside_mesh, 'salinity', 186969).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_curtain_outside_mesh.data').reshape(a.shape)
        is_close_offset1 = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
        is_close_val1 = np.isclose(a[:, 2:4], b[:, 2:4], equal_nan=True)
        is_close_offset2 = np.isclose(a[:, 4], b[:, 4], atol=1, equal_nan=True)
        is_close_val2 = np.isclose(a[:, 5:7], b[:, 5:7], equal_nan=True)
        is_close_offset3 = np.isclose(a[:, 7], b[:, 7], atol=1, equal_nan=True)
        is_close_val3 = np.isclose(a[:, 8:10], b[:, 8:10], equal_nan=True)
        self.assertTrue(is_close_offset1.all())
        self.assertTrue(is_close_val1.all())
        self.assertTrue(is_close_offset2.all())
        self.assertTrue(is_close_val2.all())
        self.assertTrue(is_close_offset3.all())
        self.assertTrue(is_close_val3.all())

        # test surface
        a = res.surface('h', 186972, to_vertex=True)['value'].to_numpy()
        b = load_comparison_data(f'{comp}_surface_vertex_h.data')  # created using tfv FVExtractor.get_sheet_node()
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        a = res.surface('sal', 186972, to_vertex=True)['value'].to_numpy()
        b = load_comparison_data(f'{comp}_surface_vertex_salinity.data')  # created using tfv FVExtractor.get_sheet_node()
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        a = res.surface('h', 186972, to_vertex=False)['value'].to_numpy()
        b = load_comparison_data(f'{comp}_surface_cell_h.data')  # created using tfv FVExtractor.get_sheet_cell()
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

        a = res.surface('sal', 186972, to_vertex=False)['value'].to_numpy()
        b = load_comparison_data(f'{comp}_surface_cell_salinity.data')  # created using tfv FVExtractor.get_sheet_cell()
        is_close = np.isclose(a, b)
        self.assertTrue(is_close.all())

    def test_pymesh_quadtree(self):
        p = './tests/quadtree/EG13_001.xmdf'
        point = './tests/quadtree/qdt_point.shp'
        line = './tests/quadtree/qdt_line.shp'
        point_outside = './tests/quadtree/qdt_point_outside.shp'
        comp = './tests/regression_test_comparisons/test_qgis_quadtree'

        res = XMDF(p)

        # time series
        a = res.time_series(point, 'water level').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # point outside mesh
        a = res.time_series(point_outside, 'water level').reset_index().to_numpy()
        self.assertTrue(a.size == 0)

        # section
        a = res.section(line, 'water level', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_section.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # profile
        a = res.profile(point, 'velocity', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_profile.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # curtain
        a = res.curtain(line, 'z0', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_curtain.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())
