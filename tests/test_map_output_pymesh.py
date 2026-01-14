import unittest
from datetime import datetime

import numpy as np
import pandas as pd

from pytuflow import XMDF, NCMesh, CATCHJson, DAT


def load_comparison_data(path):
    with open(path, 'rb') as f:
        buf = f.read()
    return np.frombuffer(buf)


class TestXMDF(unittest.TestCase):

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

        m = df.loc[:, 3].astype(str) != 'nan'
        df1[3] = np.nan
        df1[4] = np.nan
        df1[5] = np.nan
        df1[6] = np.nan
        df1.loc[m, [3, 4]] = np.vstack(df.loc[m, 3])
        df1.loc[m, [5, 6]] = np.vstack(df.loc[m, 4])
        df1[7] = a[:, 5]
        df1[8] = a[:, 6]

        m = df.loc[:, 7].astype(str) != 'nan'
        df1[9] = np.nan
        df1[10] = np.nan
        df1[11] = np.nan
        df1[12] = np.nan
        df1.loc[m, [9, 10]] = np.vstack(df.loc[m, 7])
        df1.loc[m, [11, 12]] = np.vstack(df.loc[m, 8])
        df1[13] = a[:, 9]
        df1[14] = a[:, 10]

        m = df.loc[:, 11].astype(str) != 'nan'
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
