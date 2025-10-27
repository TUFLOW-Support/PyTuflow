import unittest
from contextlib import contextmanager
from datetime import datetime

from qgis.core import QgsApplication

from pytuflow import XMDF, NCMesh, CATCHJson, DAT, NCGrid


@contextmanager
def pyqgis():
    app = QgsApplication.instance()
    if not app:
        app = QgsApplication([], False)
        app.initQgis()

    yield app

    # let QGIS be destroyed when the process ends, exitQgis() causes a crash if the providers are initialised again


class TestXMDF(unittest.TestCase):

    def test_load(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            self.assertEqual(res.name, 'run')

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
            self.assertEqual((7, 2), df.shape)

    def test_section_long(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.section(shp, 'max h', 0)
            self.assertEqual((8, 2), df.shape)

    def test_curtain(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((28, 3), df.shape)

    def test_curtain_2(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_multi_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((28, 6), df.shape)

    def test_curtain_3(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, ['vel', 'depth'], 0)
            self.assertEqual((28, 4), df.shape)

    def test_curtain_vector(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, 'vector velocity', 0)
            self.assertEqual((28, 3), df.shape)

    def test_curtain_long(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((16, 3), df.shape)

    def test_profile(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = XMDF(xmdf)
            df = res.profile(shp, 'vel', 0)
            self.assertEqual((2, 2), df.shape)


class TestNCMesh(unittest.TestCase):

    def test_load(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            self.assertEqual('fv_res', res.name)

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

    def test_curtain(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc)
            line = [(1.4, 4.5), (3.6, 4.2)]
            df = res.curtain(line, 'v', 0)
            self.assertEqual((24, 3), df.shape)

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
            self.assertEqual((24, 3), df.shape)

    def test_curtain_2(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((40, 3), df.shape)

    def test_curtain_3(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook_reversed.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((32, 3), df.shape)

    def test_curtain_4(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((24, 3), df.shape)

    def test_curtain_5(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/catch_json/section_line_ugly.shp'
        with pyqgis():
            res = CATCHJson(p)
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((64, 3), df.shape)

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


class TestNCGrid(unittest.TestCase):

    def test_load(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        self.assertEqual('small_model_001', res.name)

    def test_times(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        times = res.times()
        self.assertEqual(13, len(times))

    def test_data_types(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        dtypes = res.data_types()
        self.assertEqual(8, len(dtypes))
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
