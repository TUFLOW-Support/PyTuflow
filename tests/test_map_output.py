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

    def test_load_2dm_only_netcdf4_driver(self):
        twodm = './tests/xmdf/run.2dm'
        with pyqgis():
            res = XMDF(twodm, driver='qgis geometry netcdf4')
            self.assertEqual('run', res.name)
            self.assertEqual(['bed level'], res.data_types())
            df = res.section('./tests/xmdf/section_line.shp', 'bed level', 0)
            self.assertFalse(df.empty)

    def test_load_2dm_only_qgis_driver(self):
        twodm = './tests/xmdf/run.2dm'
        with pyqgis():
            res = XMDF(twodm, driver='qgis geometry data extractor')
            self.assertEqual('run', res.name)
            self.assertEqual(['bed level'], res.data_types())
            df = res.section('./tests/xmdf/section_line.shp', 'bed level', 0)
            self.assertFalse(df.empty)

    def test_load_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            self.assertEqual( 'run', res.name)
            self.assertFalse(res.has_reference_time)

    def test_load_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            self.assertEqual('run', res.name)
            self.assertFalse(res.has_reference_time)

    def test_times_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            times = res.times()
            self.assertEqual(7, len(times))

    def test_times_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            times = res.times()
            self.assertEqual(7, len(times))

    def test_times_filter_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            times = res.times('depth')
            self.assertEqual(7, len(times))

    def test_times_filter_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            times = res.times('depth')
            self.assertEqual(7, len(times))

    def test_data_types_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            dtypes = res.data_types()
            self.assertEqual(10, len(dtypes))

    def test_data_types_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            dtypes = res.data_types()
            self.assertEqual(10, len(dtypes))

    def test_data_types_filter_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            dtypes = res.data_types('max')
            self.assertEqual(4, len(dtypes))
            dtypes = res.data_types('temporal')
            self.assertEqual(4, len(dtypes))
            dtypes = res.data_types('vector')
            self.assertEqual(2, len(dtypes))

    def test_data_types_filter_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            dtypes = res.data_types('max')
            self.assertEqual(4, len(dtypes))
            dtypes = res.data_types('temporal')
            self.assertEqual(4, len(dtypes))
            dtypes = res.data_types('vector')
            self.assertEqual(2, len(dtypes))

    def test_data_point_v1_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='v1.0')
            point = (1.0, 1.0)
            df = res.data_point(point, 'max h', 0)
            self.assertTrue(isinstance(df, float))
            df = res.data_point(point, 'max vector velocity', 0)
            self.assertTrue(isinstance(df, tuple))
            df = res.data_point(point, ['max h', 'max vector velocity'], 0)
            self.assertEqual((1, 2), df.shape)

    def test_data_point_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            point = (1.0, 1.0)
            df = res.data_point(point, 'max h', 0)
            self.assertTrue(isinstance(df, float))
            df = res.data_point(point, 'max vector velocity', 0)
            self.assertTrue(isinstance(df, tuple))
            df = res.data_point(point, ['max h', 'max vector velocity'], 0)
            self.assertEqual((1, 2), df.shape)

    def test_data_point_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            point = (1.0, 1.0)
            df = res.data_point(point, 'max h', 0)
            self.assertTrue(isinstance(df, float))
            df = res.data_point(point, 'max vector velocity', 0)
            self.assertTrue(isinstance(df, tuple))
            df = res.data_point(point, ['max h', 'max vector velocity'], 0)
            self.assertEqual((1, 2), df.shape)

    def test_data_point_datetime_netcdf4_driver(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            point = './tests/xmdf/xmdf_point.shp'
            time = datetime(1990, 1, 1, 1)
            val = res.data_point(point, 'h', time)
            self.assertTrue(isinstance(val, float))

    def test_data_point_datetime_qgis_driver(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            point = './tests/xmdf/xmdf_point.shp'
            time = datetime(1990, 1, 1, 1)
            val = res.data_point(point, 'h', time)
            self.assertTrue(isinstance(val, float))

    def test_time_series_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.time_series((1, 1), 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.time_series((1, 1), 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_2_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.time_series({'test name': 'POINT (1.5 3.2)'}, 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_2_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.time_series({'test name': 'POINT (1.5 3.2)'}, 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_3_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.time_series(shp, 'vel')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_3_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.time_series(shp, 'vel')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_4_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_multi_point.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.time_series(shp, 'vel')
            self.assertEqual((7, 2), df.shape)

    def test_time_series_4_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_multi_point.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.time_series(shp, 'vel')
            self.assertEqual((7, 2), df.shape)

    def test_time_series_vec_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_multi_point.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.time_series(shp, 'vector velocity')
            self.assertEqual((7, 2), df.shape)

    def test_time_series_vec_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_multi_point.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.time_series(shp, 'vector velocity')
            self.assertEqual((7, 2), df.shape)

    def test_section_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.section(shp, 'h', 0)
            self.assertEqual((9, 2), df.shape)

    def test_section_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.section(shp, 'h', 0)
            self.assertEqual((9, 2), df.shape)

    def test_section_2_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            line = 'LINESTRING (0.697468354430381 0.633670886075949,3.27063291139241 3.34506329113924)'
            df = res.section(line, 'h', 0)
            self.assertEqual((9, 2), df.shape)

    def test_section_2_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            line = 'LINESTRING (0.697468354430381 0.633670886075949,3.27063291139241 3.34506329113924)'
            df = res.section(line, 'h', 0)
            self.assertEqual((9, 2), df.shape)

    def test_section_3_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_multi_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.section(shp, 'h', 0)
            self.assertEqual((9, 4), df.shape)

    def test_section_3_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_multi_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.section(shp, 'h', 0)
            self.assertEqual((9, 4), df.shape)

    def test_section_4_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.section(shp, ['h', 'v'], 0)
            self.assertEqual((9, 3), df.shape)

    def test_section_4_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry enginer')
            df = res.section(shp, ['h', 'v'], 0)
            self.assertEqual((9, 3), df.shape)

    def test_section_5_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_multi_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.section(shp, ['h', 'v'], 0)
            self.assertEqual((9, 6), df.shape)

    def test_section_5_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_multi_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.section(shp, ['h', 'v'], 0)
            self.assertEqual((9, 6), df.shape)

    def test_section_6_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.section(shp, ['bed level', 'h'], 0)
            self.assertEqual((9, 3), df.shape)

    def test_section_6_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.section(shp, ['bed level', 'h'], 0)
            self.assertEqual((9, 3), df.shape)

    def test_section_7_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            line = [(0.5, 0.5), (1.5, 1.5)]
            df = res.section(line, 'max h', 0)
            self.assertEqual((4, 2), df.shape)

    def test_section_7_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            line = [(0.5, 0.5), (1.5, 1.5)]
            df = res.section(line, 'max h', 0)
            self.assertEqual((4, 2), df.shape)

    def test_section_vec_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            line = [(0.5, 0.5), (1.5, 1.5)]
            df = res.section(line, 'vector velocity', 0)
            self.assertEqual((4, 2), df.shape)

    def test_section_vec_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            line = [(0.5, 0.5), (1.5, 1.5)]
            df = res.section(line, 'vector velocity', 0)
            self.assertEqual((4, 2), df.shape)

    def test_section_long_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.section(shp, 'max h', 0)
            self.assertEqual((8, 2), df.shape)

    def test_section_long_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.section(shp, 'max h', 0)
            self.assertEqual((8, 2), df.shape)

    def test_section_quadtree_netcdf4_driver(self):
        xmdf = './tests/quadtree/EG13_001.xmdf'
        shp = './tests/quadtree/simple_line_3.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.section(shp, 'h', 1.)
            self.assertEqual((6, 2), df.shape)

    def test_section_quadtree_qgis_driver(self):
        xmdf = './tests/quadtree/EG13_001.xmdf'
        shp = './tests/quadtree/simple_line_3.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.section(shp, 'h', 1.)
            self.assertEqual((6, 2), df.shape)

    def test_curtain_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((28, 4), df.shape)

    def test_curtain_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((28, 4), df.shape)

    def test_curtain_2_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_multi_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((28, 8), df.shape)

    def test_curtain_2_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_multi_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((28, 8), df.shape)

    def test_curtain_3_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.curtain(shp, ['vel', 'depth'], 0)
            self.assertEqual((28, 5), df.shape)

    def test_curtain_3_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.curtain(shp, ['vel', 'depth'], 0)
            self.assertEqual((28, 5), df.shape)

    def test_curtain_vector_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.curtain(shp, 'vector velocity', 0)
            self.assertEqual((28, 4), df.shape)

    def test_curtain_vector_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.curtain(shp, 'vector velocity', 0)
            self.assertEqual((28, 4), df.shape)

    def test_curtain_long_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((16, 4), df.shape)

    def test_curtain_long_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.curtain(shp, 'vel', 0)
            self.assertEqual((16, 4), df.shape)

    def test_curtain_maximums_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.curtain(shp, 'max vel', 0)
            self.assertEqual((28, 4), df.shape)

    def test_curtain_maximums_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.curtain(shp, 'max vel', 0)
            self.assertEqual((28, 4), df.shape)

    def test_curtain_maximums_2_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.curtain(shp, 'max depth', 0)
            self.assertEqual((28, 3), df.shape)

    def test_curtain_maximums_2_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/section_line.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.curtain(shp, 'max depth', 0)
            self.assertEqual((28, 3), df.shape)

    def test_profile_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.profile(shp, 'vel', 0)
            self.assertEqual((2, 2), df.shape)

    def test_profile_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.profile(shp, 'vel', 0)
            self.assertEqual((2, 2), df.shape)

    def test_profile_vec_netcdf4_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            df = res.profile(shp, 'vector velocity', 0)
            self.assertEqual((2, 2), df.shape)

    def test_profile_vec_qgis_driver(self):
        xmdf = './tests/xmdf/run.xmdf'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            df = res.profile(shp, 'vector velocity', 0)
            self.assertEqual((2, 2), df.shape)

    def test_maximum_level_netcdf4_driver(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            mx = res.maximum('h')
            self.assertTrue(np.isclose(50.42428207, mx).all())

    def test_maximum_level_qgis_driver(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            mx = res.maximum('h')
            self.assertTrue(np.isclose(50.42428207, mx).all())

    def test_maximum_multiple_result_types_netcdf4_driver(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            mx = res.maximum(['h', 'd', 'v'])
            self.assertEqual((3, 1), mx.shape)
            self.assertTrue(np.isclose([50.42428, 3.03354, 3.03524], mx.to_numpy().flatten()).all())

    def test_maximum_multiple_result_types_qgis_driver(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            mx = res.maximum(['h', 'd', 'v'])
            self.assertEqual((3, 1), mx.shape)
            self.assertTrue(np.isclose([50.42428, 3.03354, 3.03524], mx.to_numpy().flatten()).all())

    def test_minimum_level_netcdf4_driver(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            mn = res.minimum('h')
            self.assertTrue(np.isclose(35.9343795, mn).all())

    def test_minimum_level_qgis_driver(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            mn = res.minimum('h')
            self.assertTrue(np.isclose(35.9343795, mn).all())

    def test_minimum_multiple_result_types_netcdf4_driver(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry netcdf4')
            mn = res.minimum(['h', 'd', 'v'])
            self.assertEqual((3, 1), mn.shape)
            self.assertTrue(np.isclose([35.9343795, 0., 0.], mn.to_numpy().flatten()).all())

    def test_minimum_multiple_result_types_qgis_driver(self):
        xmdf = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(xmdf, driver='qgis geometry data extractor')
            mn = res.minimum(['h', 'd', 'v'])
            self.assertEqual((3, 1), mn.shape)
            self.assertTrue(np.isclose([35.9343795, 0., 0.], mn.to_numpy().flatten()).all())

    def test_flux_netcdf4_driver(self):
        p = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(p, driver='qgis geometry netcdf4')
            df = res.flux('./tests/xmdf/xmdf_flux_line.shp', '')
            self.assertEqual((7, 1), df.shape)
            self.assertAlmostEqual(76.108, float(df.iloc[:,0].max()), places=3)

    def test_flux_qgis_driver(self):
        p = './tests/xmdf/EG00_001.xmdf'
        with pyqgis():
            res = XMDF(p, driver='qgis geometry data extractor')
            df = res.flux('./tests/xmdf/xmdf_flux_line.shp', '')
            self.assertEqual((7, 1), df.shape)
            self.assertAlmostEqual(76.108, float(df.iloc[:,0].max()), places=3)


class TestNCMesh(unittest.TestCase):

    def test_load_netcdf4_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            self.assertEqual('fv_res', res.name)
            self.assertFalse(res.has_reference_time)

    def test_load_qgis_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            self.assertEqual('fv_res', res.name)
            self.assertTrue(res.has_reference_time)  # different from above - QGIS seems to assume 1990-01-01 if none is set

    def test_times_netcdf4_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            times = res.times()
            self.assertEqual(7, len(times))

    def test_times_qgis_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            times = res.times()
            self.assertEqual(7, len(times))

    def test_data_types_netcdf4_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            dtypes = res.data_types()
            self.assertEqual(3, len(dtypes))

    def test_data_types_qgis_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            dtypes = res.data_types()
            self.assertEqual(3, len(dtypes))

    def test_data_types_filter_netcdf4_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            dtypes = res.data_types('static')
            self.assertEqual(1, len(dtypes))

    def test_data_types_filter_qgis_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            dtypes = res.data_types('static')
            self.assertEqual(1, len(dtypes))

    def test_time_series_netcdf4_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            df = res.time_series((1.5, 4.5), 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_qgis_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            df = res.time_series((1.5, 4.5), 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_averaging_netcdf4_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            df = res.time_series((1.5, 4.5), 'vel', averaging_method='singlelevel?dir=top&1')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_averaging_qgis_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            df = res.time_series((1.5, 4.5), 'vel', averaging_method='singlelevel?dir=top&1')
            self.assertEqual((7, 1), df.shape)

    def test_section_netcdf4_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            line = [(1.4, 4.5), (3.6, 4.2)]
            df = res.section(line, 'h', 0)
            self.assertEqual((6, 2), df.shape)

    def test_section_qgis_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            line = [(1.4, 4.5), (3.6, 4.2)]
            df = res.section(line, 'h', 0)
            self.assertEqual((6, 2), df.shape)

    def test_section_averaging_netcdf4_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            line = [(1.4, 4.5), (3.6, 4.2)]
            df = res.section(line, 'v', 0, averaging_method='sigma&0.1&0.9')
            self.assertEqual((6, 2), df.shape)

    def test_section_averaging_qgis_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            line = [(1.4, 4.5), (3.6, 4.2)]
            df = res.section(line, 'v', 0, averaging_method='sigma&0.1&0.9')
            self.assertEqual((6, 2), df.shape)

    def test_section_long_lat_netcdf4_driver(self):
        nc = './tests/nc_mesh/EST001_3D_002.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            line = [(159.07617177, -31.36419353), (159.07704259, -31.36703514), (159.07855506, -31.36937259)]
            df = res.section(line, 'salinity', 186961)
            self.assertTrue(np.isclose(df.iloc[:,0].max(), 622.208, atol=0.001))

    def test_section_long_lat_qgis_driver(self):
        nc = './tests/nc_mesh/EST001_3D_002.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            res.spherical = True
            line = [(159.07617177, -31.36419353), (159.07704259, -31.36703514), (159.07855506, -31.36937259)]
            df = res.section(line, 'salinity', 186961)
            self.assertTrue(np.isclose(df.iloc[:,0].max(), 622.208, atol=0.001))

    def test_curtain_netcdf4_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            line = [(1.4, 4.5), (3.6, 4.2)]
            df = res.curtain(line, 'v', 0)
            self.assertEqual((24, 4), df.shape)

    def test_curtain_qgis_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            line = [(1.4, 4.5), (3.6, 4.2)]
            df = res.curtain(line, 'v', 0)
            self.assertEqual((24, 4), df.shape)

    def test_profile_netcdf4_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            df = res.profile((1.5, 4.5), 'v', 0)
            self.assertEqual((4, 2), df.shape)

    def test_profile_qgis_driver(self):
        nc = './tests/nc_mesh/fv_res.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            df = res.profile((1.5, 4.5), 'v', 0)
            self.assertEqual((4, 2), df.shape)

    def test_maximum_water_level_netcdf4_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            mx = res.maximum('h')
            self.assertTrue(np.isclose(mx, 0.185768127).all())

    def test_maximum_water_level_qgis_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            mx = res.maximum('h')
            self.assertTrue(np.isclose(mx, 0.185768127).all())

    def test_maximum_salinity_netcdf4_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            mx = res.maximum('sal', averaging_method=None)
            self.assertTrue(np.isclose(mx, 34.9937744).all())

    def test_maximum_salinity_qgis_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            mx = res.maximum('sal', averaging_method=None)
            self.assertTrue(np.isclose(mx, 34.9937744).all())

    def test_maximum_velocity_netcdf4_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            mx = res.maximum('V', averaging_method=None)
            self.assertTrue(np.isclose(mx, 0.42056167).all())

    def test_maximum_velocity_qgis_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            mx = res.maximum('V', averaging_method=None)
            self.assertTrue(np.isclose(mx, 0.42056167).all())

    def test_maximum_salinity_depth_averaged_qgis_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            mx = res.maximum('sal', averaging_method='sigma&0.0&1.0')
            self.assertTrue(np.isclose(mx, 34.9360265569985).all())
            mx = res.maximum('sal', averaging_method='singlelevel?dir=top&1')
            self.assertTrue(np.isclose(mx, 34.6935348510742).all())

    def test_maximum_velocity_depth_averaged_netcdf4_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            mx = res.maximum('V', averaging_method='sigma&0.0&1.0')
            self.assertTrue(np.isclose(mx, 0.419554057591823).all())
            mx = res.maximum('V', averaging_method='singlelevel?dir=bottom&1')
            self.assertTrue(np.isclose(mx, 0.419554057591823).all())

    def test_maximum_velocity_depth_averaged_qgis_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            mx = res.maximum('V', averaging_method='sigma&0.0&1.0')
            self.assertTrue(np.isclose(mx, 0.419554057591823).all())
            mx = res.maximum('V', averaging_method='singlelevel?dir=bottom&1')
            self.assertTrue(np.isclose(mx, 0.419554057591823).all())

    def test_minimum_salinity_netcdf4_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            mn = res.minimum('sal', averaging_method=None)
            self.assertTrue(np.isclose(mn, 0., atol=0.0001).all())

    def test_minimum_salinity_qgis_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            mn = res.minimum('sal', averaging_method=None)
            self.assertTrue(np.isclose(mn, 0., atol=0.0001).all())

    def test_flux_2d_netcdf4_driver(self):
        nc = './tests/nc_mesh/Trap_Steady_000.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            df = res.flux('./tests/nc_mesh/fv_steady_2d_flux_line.shp', '')
            self.assertEqual((37, 1), df.shape)
            self.assertAlmostEqual(446.486, float(df.iloc[:,0].max()), places=3)

    def test_flux_2d_qgis_driver(self):
        nc = './tests/nc_mesh/Trap_Steady_000.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
            df = res.flux('./tests/nc_mesh/fv_steady_2d_flux_line.shp', '')
            self.assertEqual((37, 1), df.shape)
            self.assertAlmostEqual(446.486, float(df.iloc[:,0].max()), places=3)

    def test_flux_3d_netcdf4_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry netcdf4')
            df = res.flux('./tests/nc_mesh/fv_estuary_flux_line.shp', '')
            self.assertEqual((5, 1), df.shape)
            self.assertAlmostEqual(85.971, float(df.iloc[:,0].max()), places=1)
            self.assertAlmostEqual(-39.142, float(df.iloc[:,0].min()), places=1)
            df_r = res.flux('./tests/nc_mesh/fv_estuary_flux_line_reversed.shp', '')
            is_close = np.isclose(df.iloc[:,0], df_r.iloc[:,0] * -1)
            self.assertTrue(is_close.all())

            df2 = res.flux('./tests/nc_mesh/fv_estuary_flux_line_2.shp', '')
            df2_r = res.flux('./tests/nc_mesh/fv_estuary_flux_line_2_reversed.shp', '')
            is_close = np.isclose(df.iloc[:,0], df_r.iloc[:,0] * -1)
            self.assertTrue(is_close.all())
            self.assertAlmostEqual(85.970, float(df2.iloc[:,0].max()), places=3)
            self.assertAlmostEqual(-39.141, float(df2.iloc[:,0].min()), places=3)

    def test_flux_3d_qgis_driver(self):
        nc = './tests/nc_mesh/EST000_3D_001.nc'
        with pyqgis():
            res = NCMesh(nc, driver='qgis geometry data extractor')
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


class TestCATCHJson(unittest.TestCase):

    def test_load_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        res = CATCHJson(p, driver='qgis geometry netcdf4')
        self.assertEqual('res', res.name)
        self.assertTrue(res.has_reference_time)

    def test_load_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            self.assertEqual('res', res.name)
            self.assertTrue(res.has_reference_time)

    def test_times_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        res = CATCHJson(p, driver='qgis geometry netcdf4')
        times = res.times()
        self.assertEqual(7, len(times))

    def test_times_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            times = res.times()
            self.assertEqual(7, len(times))

    def test_data_types_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        res = CATCHJson(p, driver='qgis geometry netcdf4')
        dtypes = res.data_types()
        self.assertEqual(10, len(dtypes))

    def test_data_types_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            dtypes = res.data_types()
            self.assertEqual(10, len(dtypes))

    def test_data_point_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        with pyqgis():
            point = (1.5, 4.5)
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.data_point(point, 'water level', 0.)
            self.assertTrue(isinstance(df, float))

    def test_data_point_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        with pyqgis():
            point = (1.5, 4.5)
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.data_point(point, 'water level', 0.)
            self.assertTrue(isinstance(df, float))

    def test_data_point_2_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        with pyqgis():
            point = (1.5, 3.5)
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.data_point(point, 'vector velocity', 0.)
            self.assertTrue(isinstance(df, tuple))

    def test_data_point_2_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        with pyqgis():
            point = (1.5, 3.5)
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.data_point(point, 'vector velocity', 0.)
            self.assertTrue(isinstance(df, tuple))

    def test_data_point_3_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        points = [(1.5, 4.5), (1.5, 3.5)]
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.data_point(points, ['h', 'v'], 0.)
            self.assertTrue(isinstance(df, pd.DataFrame))
            self.assertEqual((2, 2), df.shape)
            self.assertEqual(0, np.flatnonzero(df.isna()).size)

    def test_data_point_3_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        points = [(1.5, 4.5), (1.5, 3.5)]
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.data_point(points, ['h', 'v'], 0.)
            self.assertTrue(isinstance(df, pd.DataFrame))
            self.assertEqual((2, 2), df.shape)
            self.assertEqual(0, np.flatnonzero(df.isna()).size)

    def test_time_series_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.time_series(point, 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.time_series(point, 'water level')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_2_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.time_series(point, 'water level', time_fmt='absolute')
            self.assertEqual((7, 1), df.shape)

    def test_time_series_2_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.time_series(point, 'water level', time_fmt='absolute')
            self.assertEqual((7, 1), df.shape)

    def test_section_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.section(line, 'water level', 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.section(line, 'water level', 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_2_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.section(line, ['water level', 'velocity'], 0.)
            self.assertEqual((9, 3), df.shape)

    def test_section_2_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.section(line, ['water level', 'velocity'], 0.)
            self.assertEqual((9, 3), df.shape)

    def test_section_3_netcdf4_driver(self):
        p = './tests/catch_json/res_reversed.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_3_qgis_driver(self):
        p = './tests/catch_json/res_reversed.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_4_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_reversed.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_4_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_reversed.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_5_netcdf4_driver(self):
        p = './tests/catch_json/res_reversed.tuflow.json'
        line = './tests/catch_json/section_line_reversed.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_5_qgis_driver(self):
        p = './tests/catch_json/res_reversed.tuflow.json'
        line = './tests/catch_json/section_line_reversed.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_6_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((12, 2), df.shape)

    def test_section_6_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((12, 2), df.shape)

    def test_section_7_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook_reversed.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((8, 2), df.shape)

    def test_section_7_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook_reversed.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((8, 2), df.shape)

    def test_section_8_netcdf4_driver(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_8_qgis_driver(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((9, 2), df.shape)

    def test_section_9_netcdf4_driver(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/catch_json/section_line_ugly.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((16, 2), df.shape)

    def test_section_9_qgis_driver(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/catch_json/section_line_ugly.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.section(line, ['water level'], 0.)
            self.assertEqual((16, 2), df.shape)

    def test_curtain_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((24, 4), df.shape)

    def test_curtain_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((24, 4), df.shape)

    def test_curtain_2_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((40, 4), df.shape)

    def test_curtain_2_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((40, 4), df.shape)

    def test_curtain_3_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook_reversed.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((32, 4), df.shape)

    def test_curtain_3_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        line = './tests/catch_json/section_line_hook_reversed.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((32, 4), df.shape)

    def test_curtain_4_netcdf4_driver(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((24, 4), df.shape)

    def test_curtain_4_qgis_driver(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/xmdf/section_line_long.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((24, 4), df.shape)

    def test_curtain_5_netcdf4_driver(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/catch_json/section_line_ugly.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((64, 4), df.shape)

    def test_curtain_5_qgis_driver(self):
        p = './tests/catch_json/res_shifted.tuflow.json'
        line = './tests/catch_json/section_line_ugly.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.curtain(line, 'velocity', 0.)
            self.assertEqual((64, 4), df.shape)

    def test_profile_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.profile(point, 'v', 0)
            self.assertEqual((4, 2), df.shape)

    def test_profile_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        point = (1.5, 4.5)
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.profile(point, 'v', 0)
            self.assertEqual((4, 2), df.shape)

    def test_profile_2_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            df = res.profile(shp, 'v', 0)
            self.assertEqual((2, 2), df.shape)

    def test_profile_2_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        shp = './tests/xmdf/time_series_point.shp'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            df = res.profile(shp, 'v', 0)
            self.assertEqual((2, 2), df.shape)
            
    def test_maximum_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            mx = res.maximum('h')
            self.assertTrue(np.isclose(mx, 1.0).all())

    def test_maximum_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            mx = res.maximum('h')
            self.assertTrue(np.isclose(mx, 1.0).all())

    def test_minimum_netcdf4_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry netcdf4')
            mn = res.minimum('h')
            self.assertTrue(np.isclose(mn, 0.).all())

    def test_minimum_qgis_driver(self):
        p = './tests/catch_json/res.tuflow.json'
        with pyqgis():
            res = CATCHJson(p, driver='qgis geometry data extractor')
            mn = res.minimum('h')
            self.assertTrue(np.isclose(mn, 0.).all())


class TestDAT(unittest.TestCase):

    def test_load_python_driver(self):
        p = './tests/dat/small_model_001.ALL.sup'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            self.assertEqual('small_model_001', res.name)
            self.assertFalse(res.has_reference_time)

    def test_load_qgis_driver(self):
        p = './tests/dat/small_model_001.ALL.sup'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            self.assertEqual('small_model_001', res.name)
            self.assertFalse(res.has_reference_time)

    def test_load_2_python_driver(self):
        p = ['./tests/dat/small_model_001_d.dat', './tests/dat/small_model_001_V.dat',
             './tests/dat/small_model_001_h.dat', './tests/dat/small_model_001_q.dat',
             './tests/dat/small_model_001_Times.dat']
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            self.assertEqual('small_model_001', res.name)

    def test_load_2_qgis_driver(self):
        p = ['./tests/dat/small_model_001_d.dat', './tests/dat/small_model_001_V.dat',
             './tests/dat/small_model_001_h.dat', './tests/dat/small_model_001_q.dat',
             './tests/dat/small_model_001_Times.dat']
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            self.assertEqual('small_model_001', res.name)

    def test_times_python_driver(self):
        p = './tests/dat/small_model_001.ALL.sup'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            times = res.times()
            self.assertEqual(13, len(times))

    def test_times_qgis_driver(self):
        p = './tests/dat/small_model_001.ALL.sup'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            times = res.times()
            self.assertEqual(13, len(times))

    def test_data_types_python_driver(self):
        p = './tests/dat/small_model_001.ALL.sup'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            dtypes = res.data_types()
            self.assertEqual(8, len(dtypes))

    def test_data_types_qgis_driver(self):
        p = './tests/dat/small_model_001.ALL.sup'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            dtypes = res.data_types()
            self.assertEqual(8, len(dtypes))

    def test_newer_format_python_driver(self):
        p = './tests/dat/small_model_002_h.dat'  # model name is now 80 characters long rather than 40
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            dtypes = res.data_types()
            self.assertEqual(sorted(['bed level', 'water level', 'max water level']), sorted(dtypes))

    def test_newer_format_qgis_driver(self):
        p = './tests/dat/small_model_002_h.dat'  # model name is now 80 characters long rather than 40
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            dtypes = res.data_types()
            self.assertEqual(sorted(['bed level', 'water level', 'max water level']), sorted(dtypes))

    def test_time_series_python_driver(self):
        p = './tests/dat/small_model_002_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            df = res.time_series((1.0, 1.0), 'water level')
            self.assertEqual((13, 1), df.shape)

    def test_time_series_qgis_driver(self):
        p = './tests/dat/small_model_002_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            df = res.time_series((1.0, 1.0), 'water level')
            self.assertEqual((13, 1), df.shape)

    def test_section_python_driver(self):
        p = './tests/dat/small_model_002_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            df = res.section([(1.5, 1.2), (2.5, 1.2)], 'water level', 1.0)
            self.assertEqual((4, 2), df.shape)

    def test_section_qgis_driver(self):
        p = './tests/dat/small_model_002_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            df = res.section([(1.5, 1.2), (2.5, 1.2)], 'water level', 1.0)
            self.assertEqual((4, 2), df.shape)

    def test_maximum_level_netcdf4_driver(self):
        p = './tests/dat/EG00_001_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            mx = res.maximum('water level')
            self.assertTrue(np.isclose(mx, 50.4242821).all())

    def test_maximum_level_qgis_driver(self):
        p = './tests/dat/EG00_001_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            mx = res.maximum('water level')
            self.assertTrue(np.isclose(mx, 50.4242821).all())

    def test_maximum_velocity_vector_netcdf4_driver(self):
        p = './tests/dat/EG00_001_V.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            mx = res.maximum('velocity')
            self.assertTrue(np.isclose(mx, 3.03523898).all())

    def test_maximum_velocity_vector_qgis_driver(self):
        p = './tests/dat/EG00_001_V.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            mx = res.maximum('velocity')
            self.assertTrue(np.isclose(mx, 3.03523898).all())

    def test_maximum_max_level_netcdf4_driver(self):
        p = './tests/dat/EG00_001_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            mx = res.maximum('max water level')
            self.assertTrue(np.isclose(mx, 50.42952346801758).all())

    def test_maximum_max_level_qgis_driver(self):
        p = './tests/dat/EG00_001_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            mx = res.maximum('max water level')
            self.assertTrue(np.isclose(mx, 50.42952346801758).all())

    def test_maximum_bed_level_netcdf4_driver(self):
        p = './tests/dat/EG00_001_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            mx = res.maximum('bed level')
            self.assertTrue(np.isclose(mx, 100.).all())

    def test_maximum_bed_level_qgis_driver(self):
        p = './tests/dat/EG00_001_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            mx = res.maximum('bed level')
            self.assertTrue(np.isclose(mx, 100.).all())

    def test_minimum_level_netcdf4_driver(self):
        p = './tests/dat/EG00_001_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            mn = res.minimum('water level')
            self.assertTrue(np.isclose(mn, 35.9343795).all())

    def test_minimum_level_qgis_driver(self):
        p = './tests/dat/EG00_001_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            mn = res.minimum('water level')
            self.assertTrue(np.isclose(mn, 35.9343795).all())

    def test_minimum_bed_level_netcdf4_driver(self):
        p = './tests/dat/EG00_001_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')
            mn = res.minimum('bed level')
            self.assertTrue(np.isclose(mn, 36.01).all())

    def test_minimum_bed_level_qgis_driver(self):
        p = './tests/dat/EG00_001_h.dat'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')
            mn = res.minimum('bed level')
            self.assertTrue(np.isclose(mn, 36.01).all())


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

    def test_data_point(self):
        p = './tests/nc_grid/small_model_001.nc'
        pnt = './tests/nc_grid/time_series_point.shp'
        res = NCGrid(p)
        val = res.data_point(pnt, 'h', 1.5)
        self.assertTrue(isinstance(val, float))

    def test_data_point_2(self):
        p = './tests/nc_grid/small_model_001.nc'
        pnt = './tests/nc_grid/time_series_point.shp'
        res = NCGrid(p)
        val = res.data_point(pnt, ['h', 'd'], 1.5)
        self.assertTrue(isinstance(val, pd.DataFrame))
        self.assertEqual((1, 2), val.shape)

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
        self.assertEqual((6, 3), df.shape)

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

    def test_maximum(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        mx = res.maximum('h')
        self.assertTrue(np.isclose(mx, 1.0).all())

    def test_maximum_dataframe(self):
        p = './tests/nc_grid/small_model_001.nc'
        res = NCGrid(p)
        mx = res.maximum(['h', 'v'])
        self.assertEqual((2, 1), mx.shape)
        self.assertTrue(np.isclose(mx.to_numpy().flatten(), [1.0, 0.]).all())


def load_comparison_data(path):
    with open(path, 'rb') as f:
        buf = f.read()
    return np.frombuffer(buf)


class TestMeshRegression(unittest.TestCase):

    def test_qgis_vertex_mesh_netcdf4_driver(self):
        p = './tests/xmdf/EG00_001.xmdf'
        point = './tests/xmdf/xmdf_point.shp'
        line = './tests/xmdf/xmdf_line.shp'
        line_outside_mesh = './tests/xmdf/xmdf_line_outside_mesh.shp'
        comp = './tests/regression_test_comparisons/test_qgis_vertex_mesh'
        with pyqgis():
            res = XMDF(p, driver='qgis geometry netcdf4')

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
            # with open(f'{comp}_curtain_outside_mesh_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_curtain_outside_mesh_vec.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

    def test_qgis_vertex_mesh_qgis_driver(self):
        p = './tests/xmdf/EG00_001.xmdf'
        point = './tests/xmdf/xmdf_point.shp'
        line = './tests/xmdf/xmdf_line.shp'
        line_outside_mesh = './tests/xmdf/xmdf_line_outside_mesh.shp'
        comp = './tests/regression_test_comparisons/test_qgis_vertex_mesh'
        with pyqgis():
            res = XMDF(p, driver='qgis geometry data extractor')

            # data point
            a = res.data_point(point, 'water level', 1.)
            b = load_comparison_data(f'{comp}_time_series.data').reshape(-1, 2)[2, 1]
            is_close = np.isclose(a, b)

            # time series
            a = res.time_series(point, 'water level').reset_index().to_numpy()
            b = load_comparison_data(f'{comp}_time_series.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())
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
            # with open(f'{comp}_curtain_outside_mesh_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_curtain_outside_mesh_vec.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

    def test_qgis_dat_mesh_python_driver(self):
        p = './tests/dat/EG00_001.ALL.sup'
        point = './tests/xmdf/xmdf_point.shp'
        line = './tests/xmdf/xmdf_line.shp'
        comp = './tests/regression_test_comparisons/test_qgis_dat_mesh'
        with pyqgis():
            res = DAT(p, driver='qgis geometry python')

            # data point
            a = res.data_point(point, 'water level', 1.)
            b = load_comparison_data(f'{comp}_time_series.data').reshape(-1, 2)[2, 1]
            is_close = np.isclose(a, b)
            self.assertTrue(is_close.all())

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

    def test_qgis_dat_mesh_qgis_driver(self):
        p = './tests/dat/EG00_001.ALL.sup'
        point = './tests/xmdf/xmdf_point.shp'
        line = './tests/xmdf/xmdf_line.shp'
        comp = './tests/regression_test_comparisons/test_qgis_dat_mesh'
        with pyqgis():
            res = DAT(p, driver='qgis geometry data extractor')

            # data point
            a = res.data_point(point, 'water level', 1.)
            b = load_comparison_data(f'{comp}_time_series.data').reshape(-1, 2)[2, 1]
            is_close = np.isclose(a, b)
            self.assertTrue(is_close.all())

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

    def test_qgis_cell_mesh_latlong_netcdf4_driver(self):
        p = './tests/nc_mesh/EST000_3D_001.nc'
        point = './tests/nc_mesh/ncmesh_point_longlat.shp'
        line = './tests/nc_mesh/ncmesh_line_longlat.shp'
        line_outside_mesh = './tests/nc_mesh/ncmesh_line_longlat_outside_mesh.shp'
        line_outside_mesh_2 = './tests/nc_mesh/ncmesh_line_longlat_outside_mesh_2.shp'
        comp = './tests/regression_test_comparisons/test_qgis_cell_mesh_latlong'
        with pyqgis():
            res = NCMesh(p, driver='qgis geometry netcdf4')

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
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            # section level
            a = res.section(line, 'h', 186969).reset_index().to_numpy()
            # with open(f'{comp}_section_h.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_h.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            # section with depth averaging
            a = res.section(line, 'salinity', 186969, averaging_method='singlelevel?dir=top&4').reset_index().to_numpy()
            # with open(f'{comp}_section_single_top_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_single_top_4.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='singlelevel?dir=bottom&4').reset_index().to_numpy()
            # with open(f'{comp}_section_single_bottom_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_single_bottom_4.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='multilevel?dir=top&2&4').reset_index().to_numpy()
            # with open(f'{comp}_section_multi_top_2_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_multi_top_2_4.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969,averaging_method='multilevel?dir=bottom&2&4').reset_index().to_numpy()
            # with open(f'{comp}_section_multi_bottom_2_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_multi_bottom_2_4.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='depth&0.5&2.0').reset_index().to_numpy()
            # with open(f'{comp}_section_depth_05_2.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_depth_05_2.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='height&0.5&2.0').reset_index().to_numpy()
            # with open(f'{comp}_section_height_05_2.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_height_05_2.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='elevation&-5&0').reset_index().to_numpy()
            # with open(f'{comp}_section_elevation_5_0.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_elevation_5_0.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='sigma&0.1&0.9').reset_index().to_numpy()
            # with open(f'{comp}_section_sigma_01_09.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_sigma_01_09.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            # section outside mesh
            a = res.section(line_outside_mesh, 'salinity', 186969).reset_index().to_numpy()
            # with open(f'{comp}_section_outside_mesh.data', 'wb') as f:
            #     f.write(a.tobytes())
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
            # with open(f'{comp}_section_outside_mesh_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
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
            # with open(f'{comp}_section_outside_mesh_reenters.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_outside_mesh_reenters.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

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
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2:], b[:, 2:], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            # curtain vector
            a = res.curtain(line, 'velocity', 186969).reset_index().to_numpy()
            a = np.column_stack((a[...,:3], np.vstack(a[...,3]), np.vstack(a[...,4]))).astype('f8')
            # with open(f'{comp}_curtain_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_curtain_vec.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2:5], b[:, 2:5], equal_nan=True)
            is_close_local_vec = np.isclose(a[:, 5:], b[:, 5:], atol=0.1, equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())
            self.assertTrue(is_close_local_vec.all())

            # curtain outside mesh
            a = res.curtain(line_outside_mesh, 'salinity', 186969).reset_index().to_numpy()
            # with open(f'{comp}_curtain_outside_mesh.data', 'wb') as f:
            #     f.write(a.tobytes())
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

    def test_qgis_cell_mesh_latlong_qgis_driver(self):
        p = './tests/nc_mesh/EST000_3D_001.nc'
        point = './tests/nc_mesh/ncmesh_point_longlat.shp'
        line = './tests/nc_mesh/ncmesh_line_longlat.shp'
        line_outside_mesh = './tests/nc_mesh/ncmesh_line_longlat_outside_mesh.shp'
        line_outside_mesh_2 = './tests/nc_mesh/ncmesh_line_longlat_outside_mesh_2.shp'
        comp = './tests/regression_test_comparisons/test_qgis_cell_mesh_latlong'
        with pyqgis():
            res = NCMesh(p, driver='qgis geometry data extractor')
            res.spherical = True

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
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            # section level
            a = res.section(line, 'h', 186969).reset_index().to_numpy()
            # with open(f'{comp}_section_h.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_h.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            # section with depth averaging
            a = res.section(line, 'salinity', 186969, averaging_method='singlelevel?dir=top&4').reset_index().to_numpy()
            # with open(f'{comp}_section_single_top_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_single_top_4.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='singlelevel?dir=bottom&4').reset_index().to_numpy()
            # with open(f'{comp}_section_single_bottom_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_single_bottom_4.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='multilevel?dir=top&2&4').reset_index().to_numpy()
            # with open(f'{comp}_section_multi_top_2_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_multi_top_2_4.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969,averaging_method='multilevel?dir=bottom&2&4').reset_index().to_numpy()
            # with open(f'{comp}_section_multi_bottom_2_4.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_multi_bottom_2_4.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='depth&0.5&2.0').reset_index().to_numpy()
            # with open(f'{comp}_section_depth_05_2.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_depth_05_2.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='height&0.5&2.0').reset_index().to_numpy()
            # with open(f'{comp}_section_height_05_2.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_height_05_2.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='elevation&-5&0').reset_index().to_numpy()
            # with open(f'{comp}_section_elevation_5_0.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_elevation_5_0.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            a = res.section(line, 'salinity', 186969, averaging_method='sigma&0.1&0.9').reset_index().to_numpy()
            # with open(f'{comp}_section_sigma_01_09.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_sigma_01_09.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            # section outside mesh
            a = res.section(line_outside_mesh, 'salinity', 186969).reset_index().to_numpy()
            # with open(f'{comp}_section_outside_mesh.data', 'wb') as f:
            #     f.write(a.tobytes())
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
            # with open(f'{comp}_section_outside_mesh_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
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
            # with open(f'{comp}_section_outside_mesh_reenters.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_section_outside_mesh_reenters.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2], b[:, 2], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

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
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2:], b[:, 2:], equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())

            # curtain vector
            a = res.curtain(line, 'velocity', 186969).reset_index().to_numpy()
            a = np.column_stack((a[...,:3], np.vstack(a[...,3]), np.vstack(a[...,4]))).astype('f8')
            # with open(f'{comp}_curtain_vec.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_curtain_vec.data').reshape(a.shape)
            is_close_offset = np.isclose(a[:, 1], b[:, 1], atol=1, equal_nan=True)
            is_close_val = np.isclose(a[:, 2:5], b[:, 2:5], equal_nan=True)
            is_close_local_vec = np.isclose(a[:, 5:], b[:, 5:], atol=0.1, equal_nan=True)
            self.assertTrue(is_close_offset.all())
            self.assertTrue(is_close_val.all())
            self.assertTrue(is_close_local_vec.all())

            # curtain outside mesh
            a = res.curtain(line_outside_mesh, 'salinity', 186969).reset_index().to_numpy()
            # with open(f'{comp}_curtain_outside_mesh.data', 'wb') as f:
            #     f.write(a.tobytes())
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

    def test_qgis_quadtree_netcdf4_driver(self):
        p = './tests/quadtree/EG13_001.xmdf'
        point = './tests/quadtree/qdt_point.shp'
        line = './tests/quadtree/qdt_line.shp'
        point_outside = './tests/quadtree/qdt_point_outside.shp'
        comp = './tests/regression_test_comparisons/test_qgis_quadtree'
        with pyqgis():
            res = XMDF(p, driver='qgis geometry netcdf4')

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
            # with open(f'{comp}_section.data', 'wb') as f:
            #     f.write(a.tobytes())
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
            # with open(f'{comp}_curtain.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_curtain.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())

    def test_qgis_quadtree_qgis_driver(self):
        p = './tests/quadtree/EG13_001.xmdf'
        point = './tests/quadtree/qdt_point.shp'
        line = './tests/quadtree/qdt_line.shp'
        point_outside = './tests/quadtree/qdt_point_outside.shp'
        comp = './tests/regression_test_comparisons/test_qgis_quadtree'
        with pyqgis():
            res = XMDF(p, driver='qgis geometry data extractor')

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
            # with open(f'{comp}_section.data', 'wb') as f:
            #     f.write(a.tobytes())
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
            # with open(f'{comp}_curtain.data', 'wb') as f:
            #     f.write(a.tobytes())
            b = load_comparison_data(f'{comp}_curtain.data').reshape(a.shape)
            is_close = np.isclose(a, b, equal_nan=True)
            self.assertTrue(is_close.all())
