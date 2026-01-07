import unittest
from contextlib import contextmanager
from datetime import datetime

import numpy as np
import pandas as pd
from qgis.core import QgsApplication

from pytuflow import XMDF, NCMesh, CATCHJson, DAT, NCGrid


global qapp


@contextmanager
def pyqgis():
    global qapp  # global qapp since it can sometimes be cleaned up
    qapp = QgsApplication.instance()
    if not qapp:
        qapp = QgsApplication([], False)
        qapp.initQgis()

    yield qapp

    # let QGIS be destroyed when the process ends, exitQgis() causes a crash if the providers are initialised again


class TestXMDF(unittest.TestCase):

    def test_load(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            self.assertEqual(res.name, 'run')
            self.assertFalse(res.has_reference_time)

    def test_times(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            times = res.times()
            self.assertEqual(7, len(times))

    def test_times_filter(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            times = res.times('depth')
            self.assertEqual(7, len(times))


    def test_data_types(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            dtypes = res.data_types()
            self.assertEqual(10, len(dtypes))

    def test_data_types_filter(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            dtypes = res.data_types('max')
            self.assertEqual(4, len(dtypes))
            dtypes = res.data_types('temporal')
            self.assertEqual(4, len(dtypes))
            dtypes = res.data_types('vector')
            self.assertEqual(2, len(dtypes))

    def test_time_series(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.time_series((1, 1), 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_2(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.time_series({'test name': 'POINT (1.5 3.2)'}, 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_3(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.time_series(shp, 'vel')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_4(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_multi_point.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.time_series(shp, 'vel')
            self.assertEqual((7, 2), df.shape)

    def test_time_series_vec(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_multi_point.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.time_series(shp, 'vector velocity')
            self.assertEqual((7, 2), df.shape)

    def test_section(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.section(shp, 'h', 0)
            self.assertEqual((9, 2), df.shape)

    def test_section_2(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            line = 'LINESTRING (0.697468354430381 0.633670886075949,3.27063291139241 3.34506329113924)'
            df = res.section(line, 'h', 0)
            self.assertEqual((9, 2), df.shape)

    def test_section_3(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_multi_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.section(shp, 'h', 0)
            self.assertEqual((9, 4), df.shape)

    def test_section_4(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.section(shp, ['h', 'v'], 0)
            self.assertEqual((9, 3), df.shape)

    def test_section_5(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_multi_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.section(shp, ['h', 'v'], 0)
            self.assertEqual((9, 6), df.shape)

    def test_section_6(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.section(shp, ['bed level', 'h'], 0)
            self.assertEqual((9, 3), df.shape)

    def test_section_7(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            line = [(0.5, 0.5), (1.5, 1.5)]
            df = res.section(line, 'max h', 0)
            self.assertEqual((4, 2), df.shape)

    def test_section_vec(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            line = [(0.5, 0.5), (1.5, 1.5)]
            df = res.section(line, 'vector velocity', 0)
            self.assertEqual((4, 2), df.shape)

    def test_section_long(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.section(shp, 'max h', 0)
            self.assertEqual((8, 2), df.shape)

    def test_section_quadtree(self):
        xmdf = './tests/quadtree/EG13_001.xmdf'
        shp = './tests/quadtree/simple_line_3.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.section(shp, 'h', 1.)
            self.assertEqual((6, 2), df.shape)

    def test_curtain(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((28, 4), df.shape)

    def test_curtain_2(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_multi_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((28, 8), df.shape)

    def test_curtain_3(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, ['vel', 'depth'], 0)
            self.assertEqual((28, 5), df.shape)

    def test_curtain_vector(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, 'vector velocity', 0)
            self.assertEqual((28, 4), df.shape)

    def test_curtain_long(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((16, 4), df.shape)

    def test_curtain_maximums(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, 'max vel', 0)
            self.assertEqual((28, 4), df.shape)

    def test_curtain_maximums_2(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, 'max depth', 0)
            self.assertEqual((28, 3), df.shape)

    def test_profile(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.profile(shp, 'vel', 0)
            self.assertEqual((2, 2), df.shape)

    def test_profile_vec(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.profile(shp, 'vector velocity', 0)
            self.assertEqual((2, 2), df.shape)


class TestNCMesh(unittest.TestCase):

    def test_load(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            self.assertEqual('fv_res', res.name)
            self.assertFalse(res.has_reference_time)

    def test_times(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            times = res.times()
            self.assertEqual(7, len(times))

    def test_data_types(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            dtypes = res.data_types()
            self.assertEqual(3, len(dtypes))

    def test_data_types_filter(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            dtypes = res.data_types('static')
            self.assertEqual(1, len(dtypes))

    def test_time_series(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            df = res.time_series((1.5, 4.5), 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_averaging(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            df = res.time_series((1.5, 4.5), 'vel', averaging_method='singlelevel?top&1')
            self.assertEqual((7, 1), df.shape)

    def test_section(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            line = [(1.4, 4.5), (3.6, 4.2)]
            df = res.section(line, 'h', 0)
            self.assertEqual((6, 2), df.shape)

    def test_section_averaging(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            line = [(1.4, 4.5), (3.6, 4.2)]
            df = res.section(line, 'v', 0, averaging_method='sigma&0.1&0.9')
            self.assertEqual((6, 2), df.shape)

    def test_section_long_lat(self):
        nc = './tests/nc_mesh/EST001_3D_002.nc'
        with pyqgis():
            res = NCMesh(nc)
            line = [(159.07617177, -31.36419353), (159.07704259, -31.36703514), (159.07855506, -31.36937259)]
            df = res.section(line, 'salinity', 186961)
            self.assertTrue(np.isclose(df.iloc[:,0].max(), 622.208, atol=0.001))

    def test_curtain(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            line = [(1.4, 4.5), (3.6, 4.2)]
            df = res.curtain(line, 'v', 0)
            self.assertEqual((24, 4), df.shape)

    def test_profile(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            df = res.profile((1.5, 4.5), 'v', 0)
            self.assertEqual((4, 2), df.shape)


class TestCATCHJson(unittest.TestCase):

    # def test_load_tmp(self):
    #     dtime = datetime(2021, 1, 1, 1)
    #     p = r"C:\TUFLOW\working\catch_units\model\TUFLOWCatch\results\Demonstration_005.tuflow.json"
    #     with pyqgis():
    #         res = CATCHJson(p)
    #         df = res.section(r"C:\Users\ellis.symons\Downloads\demonstation_line.shp", 'h', dtime)
    #         print()

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
        with pyqgis():
            res = CATCHJson(p)
            df = res.time_series(point, 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_2(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        with pyqgis():
            res = CATCHJson(p)
            df = res.time_series(point, 'water level', time_fmt='absolute')
            self.assertEqual((7, 1), df.shape)

    def test_section(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.section(line, 'water level', 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_2(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.section(line, ['water level', 'velocity'], 0.)
            self.assertEqual((9, 3), df.shape)

    def test_section_3(self):
        p = './tests/catch_json/res_reversed.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_4(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_reversed.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_5(self):
        p = './tests/catch_json/res_reversed.tuflow.json'
        line = './tests/catch_json/section_line_reversed.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_6(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((12, 2), df.shape)

    def test_section_7(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook_reversed.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((8, 2), df.shape)

    def test_section_8(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_9(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/catch_json/section_line_ugly.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((16, 2), df.shape)

    def test_curtain(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((24, 4), df.shape)

    def test_curtain_2(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((40, 4), df.shape)

    def test_curtain_3(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook_reversed.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((32, 4), df.shape)

    def test_curtain_4(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((24, 4), df.shape)

    def test_curtain_5(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/catch_json/section_line_ugly.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((64, 4), df.shape)

    def test_profile(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        with pyqgis():
            res = CATCHJson(p)
            df = res.profile(point, 'v', 0)
            self.assertEqual((4, 2), df.shape)

    def test_profile_2(self):
        p = './tests/catch_json/res.tuflow.json'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.profile(shp, 'v', 0)
            self.assertEqual((2, 2), df.shape)

class TestDAT(unittest.TestCase):

    def test_load(self):
        p = './tests/dat/small_model_001.ALL.sup'
        with pyqgis():
            res = DAT(p)
            self.assertEqual('small_model_001', res.name)
            self.assertFalse(res.has_reference_time)

    def test_load_2(self):
        p = ['./tests/dat/small_model_001_d.dat', './tests/dat/small_model_001_V.dat',
             './tests/dat/small_model_001_h.dat', './tests/dat/small_model_001_q.dat',
             './tests/dat/small_model_001_Times.dat']
        with pyqgis():
            res = DAT(p)
            self.assertEqual('small_model_001', res.name)

    def test_times(self):
        p = './tests/dat/small_model_001.ALL.sup'
        with pyqgis():
            res = DAT(p)
            times = res.times()
            self.assertEqual(13, len(times))

    def test_data_types(self):
        p = './tests/dat/small_model_001.ALL.sup'
        with pyqgis():
            res = DAT(p)
            dtypes = res.data_types()
            self.assertEqual(8, len(dtypes))

    def test_newer_format(self):
        p = './tests/dat/small_model_002_h.dat'  # model name is now 80 characters long rather than 40
        with pyqgis():
            res = DAT(p)
            dtypes = res.data_types()
            self.assertEqual(['bed level', 'water level', 'max water level'], dtypes)

    def test_time_series(self):
        p = './tests/dat/small_model_002_h.dat'
        with pyqgis():
            res = DAT(p)
            df = res.time_series((1.0, 1.0), 'water level')
            self.assertEqual((13, 1), df.shape)

    def test_section(self):
        p = './tests/dat/small_model_002_h.dat'
        with pyqgis():
            res = DAT(p)
            df = res.section([(1.5, 1.2), (2.5, 1.2)], 'water level', 1.0)
            self.assertEqual((4, 2), df.shape)


class TestNCGrid(unittest.TestCase):

    def test_load(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        self.assertEqual('small_model_001', res.name)
        self.assertTrue(res.has_reference_time)

    def test_times(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        times = res.times()
        self.assertEqual(13, len(times))

    def test_data_types(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        dtypes = res.data_types()
        self.assertEqual(11, len(dtypes))
        dtypes = res.data_types('3d')
        self.assertEqual(0, len(dtypes))

    def test_time_series(self):
        p = './tests/nc_grid/small_model_001.nc'
        pnt = './tests/nc_grid/time_series_point.shp'
        res = NCGrid(p)
        df = res.time_series(pnt, 'wl')
        self.assertEqual((13, 1), df.shape)

    def test_section_horiz(self):
        p = './tests/nc_grid/small_model_001.nc'
        line = './tests/nc_grid/section_line_horiz.shp'
        res = NCGrid(p)
        df = res.section(line, 'h', 0)
        self.assertEqual((6, 2), df.shape)
        df = res.section(line, ['water level', 'max water level'], 0.5)
        self.assertEqual((6, 4), df.shape)

    def test_section_vert(self):
        p = './tests/nc_grid/small_model_001.nc'
        line = './tests/nc_grid/section_line_vert.shp'
        res = NCGrid(p)
        df = res.section(line, 'h', 0)
        self.assertEqual((6, 2), df.shape)

    def test_section_diag_x(self):
        p = './tests/nc_grid/small_model_001.nc'
        line = './tests/nc_grid/section_line_diag_x.shp'
        res = NCGrid(p)
        df = res.section(line, 'h', 0)
        self.assertEqual((10, 2), df.shape)

    def test_section_diag_y(self):
        p = './tests/nc_grid/small_model_001.nc'
        line = './tests/nc_grid/section_line_diag_y.shp'
        res = NCGrid(p)
        df = res.section(line, 'h', 0)
        self.assertEqual((12, 2), df.shape)

    def test_section_horiz_long(self):
        p = './tests/nc_grid/small_model_001.nc'
        line = './tests/nc_grid/section_line_horiz_long.shp'
        res = NCGrid(p)
        df = res.section(line, 'h', 0)
        self.assertEqual((14, 2), df.shape)

    def test_section_polyline(self):
        p = './tests/nc_grid/small_model_001.nc'
        line = './tests/nc_grid/section_polyline.shp'
        res = NCGrid(p)
        df = res.section(line, 'h', 0)
        self.assertEqual((18, 2), df.shape)


def load_comparison_data(path):
    with open(path, 'rb') as f:
        buf = f.read()
    return np.frombuffer(buf)


class TestMeshRegression(unittest.TestCase):

    def test_qgis_vertex_mesh(self):
        p = './tests/xmdf/EG00_001.xmdf'
        point = './tests/xmdf/xmdf_point.shp'
        line = './tests/xmdf/xmdf_line.shp'
        line_outside_mesh = './tests/xmdf/xmdf_line_outside_mesh.shp'
        comp = './tests/regression_test_comparisons/test_qgis_vertex_mesh'
        with pyqgis():
            res = XMDF(p)

            # time series
            a = res.time_series(point, 'water level').reset_index().to_numpy()
            b = load_comparison_data(f'{comp}_time_series.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # time series vector
            a = res.time_series(point, 'vector velocity').reset_index().to_numpy()
            # with open(f'{comp}_time_series_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
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
            # with open(f'{comp}_section_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_vec.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # section lines that start/end outside the mesh
            a = res.section(line_outside_mesh, 'water level', 1.).reset_index().to_numpy()
            b = load_comparison_data(f'{comp}_section_outside_mesh.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # section lines that start/end outside the mesh - vector
            a = res.section(line_outside_mesh, 'vector velocity', 1.).reset_index().to_numpy()
            # with open(f'{comp}_section_outside_mesh_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
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
            # with open(f'{comp}_profile_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_profile_vec.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # curtain scalar
            a = res.curtain(line, 'z0', 1.).reset_index().to_numpy()
            b = load_comparison_data(f'{comp}_curtain.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # curtain vector
            a = res.curtain(line, 'velocity', 1.).reset_index().to_numpy()
            a = np.column_stack((a[...,:3], np.vstack(a[...,3]), np.vstack(a[...,4]))).astype('f8')
            b = load_comparison_data(f'{comp}_curtain_vec.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
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
            # with open(f'{comp}_curtain_outside_mesh_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_curtain_outside_mesh_vec.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

    def test_qgis_dat_mesh(self):
        p = './tests/dat/EG00_001.ALL.sup'
        point = './tests/xmdf/xmdf_point.shp'
        line = './tests/xmdf/xmdf_line.shp'
        comp = './tests/regression_test_comparisons/test_qgis_dat_mesh'
        with pyqgis():
            res = DAT(p)

            # time series
            a = res.time_series(point, 'water level').reset_index().to_numpy()
            # with open(f'{comp}_time_series.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # section
            a = res.section(line, 'water level', 1.).reset_index().to_numpy()
            # with open(f'{comp}_section.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

    def test_qgis_cell_mesh_latlong(self):
        p = './tests/nc_mesh/EST000_3D_001.nc'
        point = './tests/nc_mesh/ncmesh_point_longlat.shp'
        line = './tests/nc_mesh/ncmesh_line_longlat.shp'
        line_outside_mesh = './tests/nc_mesh/ncmesh_line_longlat_outside_mesh.shp'
        comp = './tests/regression_test_comparisons/test_qgis_cell_mesh_latlong'
        with pyqgis():
            res = NCMesh(p)

            # time series
            a = res.time_series(point, 'salinity').reset_index().to_numpy()
            # with open(f'{comp}_time_series.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # time series level
            a = res.time_series(point, 'h').reset_index().to_numpy()
            # with open(f'{comp}_time_series_h.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series_h.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # time series with depth averaging
            a = res.time_series(point, 'salinity', averaging_method='singlelevel?dir=top&4').reset_index().to_numpy()
            # with open(f'{comp}_time_series_single_top_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series_single_top_4.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.time_series(point, 'salinity', averaging_method='singlelevel?dir=bottom&2').reset_index().to_numpy()
            # with open(f'{comp}_time_series_single_bottom_2.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series_single_bottom_2.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.time_series(point, 'salinity', averaging_method='multilevel?dir=top&2&4').reset_index().to_numpy()
            # with open(f'{comp}_time_series_multi_top_2_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series_multi_top_2_4.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.time_series(point, 'salinity', averaging_method='multilevel?dir=bottom&2&4').reset_index().to_numpy()
            # with open(f'{comp}_time_series_multi_bottom_2_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series_multi_bottom_2_4.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.time_series(point, 'salinity', averaging_method='depth&0.5&2.0').reset_index().to_numpy()
            # with open(f'{comp}_time_series_depth_05_2.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series_depth_05_2.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.time_series(point, 'salinity', averaging_method='height&0.5&2.0').reset_index().to_numpy()
            # with open(f'{comp}_time_series_height_05_2.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series_height_05_2.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.time_series(point, 'salinity', averaging_method='elevation&-5&0').reset_index().to_numpy()
            # with open(f'{comp}_time_series_elevation_5_0.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series_elevation_5_0.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.time_series(point, 'salinity', averaging_method='sigma&0.1&0.9').reset_index().to_numpy()
            # with open(f'{comp}_time_series_sigma_01_09.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series_sigma_01_09.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # section
            a = res.section(line, 'salinity', 186969).reset_index().to_numpy()
            # with open(f'{comp}_section.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # section level
            a = res.section(line, 'h', 186969).reset_index().to_numpy()
            # with open(f'{comp}_section_h.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_h.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # section with depth averaging
            a = res.section(line, 'salinity', 186969, averaging_method='singlelevel?dir=top&4').reset_index().to_numpy()
            # with open(f'{comp}_section_single_top_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_single_top_4.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.section(line, 'salinity', 186969, averaging_method='singlelevel?dir=bottom&4').reset_index().to_numpy()
            # with open(f'{comp}_section_single_bottom_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_single_bottom_4.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.section(line, 'salinity', 186969, averaging_method='multilevel?dir=top&2&4').reset_index().to_numpy()
            # with open(f'{comp}_section_multi_top_2_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_multi_top_2_4.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.section(line, 'salinity', 186969,averaging_method='multilevel?dir=bottom&2&4').reset_index().to_numpy()
            # with open(f'{comp}_section_multi_bottom_2_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_multi_bottom_2_4.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.section(line, 'salinity', 186969, averaging_method='depth&0.5&2.0').reset_index().to_numpy()
            # with open(f'{comp}_section_depth_05_2.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_depth_05_2.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.section(line, 'salinity', 186969, averaging_method='height&0.5&2.0').reset_index().to_numpy()
            # with open(f'{comp}_section_height_05_2.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_height_05_2.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.section(line, 'salinity', 186969, averaging_method='elevation&-5&0').reset_index().to_numpy()
            # with open(f'{comp}_section_elevation_5_0.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_elevation_5_0.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            a = res.section(line, 'salinity', 186969, averaging_method='sigma&0.1&0.9').reset_index().to_numpy()
            # with open(f'{comp}_section_sigma_01_09.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_sigma_01_09.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # section outside mesh
            a = res.section(line_outside_mesh, 'salinity', 186969).reset_index().to_numpy()
            # with open(f'{comp}_section_outside_mesh.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_outside_mesh.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # section outside mesh vector
            a = res.section(line_outside_mesh, 'velocity', 186969).reset_index().to_numpy()
            # with open(f'{comp}_section_outside_mesh_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_outside_mesh_vec.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # profile
            a = res.profile(point, 'salinity', 186969).reset_index().to_numpy()
            # with open(f'{comp}_profile.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_profile.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # profile linear interpolation
            a = res.profile(point, 'salinity', 186969, 'linear').reset_index().to_numpy()
            # with open(f'{comp}_profile_linear.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_profile_linear.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # curtain
            a = res.curtain(line, 'salinity', 186969).reset_index().to_numpy()
            # with open(f'{comp}_curtain.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_curtain.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # curtain vector
            a = res.curtain(line, 'velocity', 186969).reset_index().to_numpy()
            a = np.column_stack((a[...,:3], np.vstack(a[...,3]), np.vstack(a[...,4]))).astype('f8')
            # with open(f'{comp}_curtain_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_curtain_vec.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # curtain outside mesh
            a = res.curtain(line_outside_mesh, 'salinity', 186969).reset_index().to_numpy()
            # with open(f'{comp}_curtain_outside_mesh.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_curtain_outside_mesh.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

    def test_qgis_quadtree(self):
        p = './tests/quadtree/EG13_001.xmdf'
        point = './tests/quadtree/qdt_point.shp'
        line = './tests/quadtree/qdt_line.shp'
        point_outside = './tests/quadtree/qdt_point_outside.shp'
        comp = './tests/regression_test_comparisons/test_qgis_quadtree'
        with pyqgis():
            res = XMDF(p)

            # time series
            a = res.time_series(point, 'water level').reset_index().to_numpy()
            # with open(f'{comp}_time_series.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_time_series.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # point outside mesh
            a = res.time_series(point_outside, 'water level').reset_index().to_numpy()
            self.assertTrue(a.size == 0)

            # section
            a = res.section(line, 'water level', 1.).reset_index().to_numpy()
            with open(f'{comp}_section.data', 'wb') as f:
                f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # profile
            a = res.profile(point, 'velocity', 1.).reset_index().to_numpy()
            # with open(f'{comp}_profile.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_profile.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

            # curtain
            a = res.curtain(line, 'z0', 1.).reset_index().to_numpy()
            with open(f'{comp}_curtain.data', 'wb') as f:
                f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_curtain.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())
