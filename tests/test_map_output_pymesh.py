import unittest

import numpy as np

from pytuflow import XMDF


def load_comparison_data(path):
    with open(path, 'rb') as f:
        buf = f.read()
    return np.frombuffer(buf)


class TestPyMeshRegression(unittest.TestCase):

    def test_pymesh_vertex_mesh(self):
        p = './tests/xmdf/EG00_001.xmdf'
        point = './tests/xmdf/xmdf_point.shp'
        line = './tests/xmdf/xmdf_line.shp'
        line_outside_mesh = './tests/xmdf/xmdf_line_outside_mesh.shp'
        comp = './tests/regression_test_comparisons/test_qgis_vertex_mesh'

        res = XMDF(p)

        # time series
        a = res.time_series(point, 'water level').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())
