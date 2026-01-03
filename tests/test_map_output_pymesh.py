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

        # time series vector
        a = res.time_series(point, 'vector velocity').reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_time_series_vec.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # # section
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
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())

        # curtain vector - current wrong in pytuflow qgis implementation
        # a = res.curtain(line, 'velocity', 1.).reset_index().to_numpy()
        # a = np.column_stack((a[..., :3], np.vstack(a[..., 3]), np.vstack(a[..., 4]))).astype('f8')
        # b = load_comparison_data(f'{comp}_curtain_vec.data').reshape(a.shape)
        # is_close = np.isclose(a, b, equal_nan=True, atol=0.0001)
        # self.assertTrue(is_close.all())

        # curtain outside mesh
        a = res.curtain(line_outside_mesh, 'z0', 1.).reset_index().to_numpy()
        b = load_comparison_data(f'{comp}_curtain_outside_mesh.data').reshape(a.shape)
        is_close = np.isclose(a, b, equal_nan=True)
        self.assertTrue(is_close.all())
