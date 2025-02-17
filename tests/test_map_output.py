import unittest
from contextlib import contextmanager

from qgis.core import QgsApplication

from pytuflow import XMDF


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
            self.assertEqual(6, len(dtypes))

    def test_data_types_filter(self):
        xmdf = './tests/xmdf/run.xmdf'
        with pyqgis():
            res = XMDF(xmdf)
            dtypes = res.data_types('max')
            self.assertEqual(4, len(dtypes))
            dtypes = res.data_types('temporal')
            self.assertEqual(4, len(dtypes))
            dtypes = res.data_types('vector')
            self.assertEqual(1, len(dtypes))

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
