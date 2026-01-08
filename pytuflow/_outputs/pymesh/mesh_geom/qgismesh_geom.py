import typing
from pathlib import Path

import numpy as np

try:
    from qgis.core import QgsApplication, QgsMesh, QgsMeshLayer, QgsMeshSpatialIndex, QgsPointXY
except ImportError:
    from ..stubs.qgis.core import QgsApplication, QgsMesh, QgsMeshLayer, QgsMeshSpatialIndex, QgsPointXY

from . import PyMeshGeometry
from .. import barycentric_coord, Bbox2D, Transform2D, PointMixin, PointLike, LineStringMixin, LineStringLike


class PointMixinQgis(PointMixin):

    @staticmethod
    def _coerce_into_qgs_point(value: PointLike) -> QgsPointXY:
        p = PointMixin._coerce_into_point(value)
        return QgsPointXY(*p.tolist()[:2])



class QgisMeshGeometry(PyMeshGeometry, PointMixinQgis):

    def __init__(self, fpath: Path | str):
        super().__init__(fpath)
        self.has_z = True
        self.trans = Transform2D()
        self._lyr = None
        self._mesh = QgsMesh()
        self._si = None
        self._loaded = False

        self._cell2triangle = {}
        self._triangle2cell = {}
        self._triangles = {}
        self._tri_count = 0

    def load(self):
        if not QgsApplication.instance():
            raise RuntimeError('QGIS application instance not found.')
        if not self._loaded:
            self._lyr = QgsMeshLayer(str(self.fpath), self.fpath.stem, 'mdal')
            dp = self._lyr.dataProvider()
            dp.populateMesh(self._mesh)
            self._si = QgsMeshSpatialIndex(self._mesh)
            self._loaded = True

    def vertex_position(self, vertex_id: int | typing.Iterable[int], *args, **kwargs) -> np.ndarray:
        if isinstance(vertex_id, int):
            vertex_id = [vertex_id]
        if isinstance(vertex_id, np.ndarray):
            vertex_id = vertex_id.tolist()
        a = np.full((len(vertex_id), 2), -1, dtype=int)
        for i, vid in enumerate(vertex_id):
            v = self._mesh.vertex(vid)
            a[i, 0] = v.x()
            a[i, 1] = v.y()
        return a

    def triangle_vertices(self, triangle_id: int) -> np.ndarray:
        if triangle_id in self._triangles:
            return self._triangles[triangle_id]
        raise RuntimeError(f'Triangle index not found in cache: {triangle_id}')

    def triangle_cell(self, triangle_id: int) -> int:
        if triangle_id in self._triangle2cell:
            return self._triangle2cell[triangle_id]
        raise RuntimeError(f'Triangle index not found in cache: {triangle_id}')

    def find_containing_cell(self, point: PointLike, *args, **kwargs) -> int:
        p = self._coerce_into_qgs_point(point)
        p_ = self._coerce_into_point(point)  # numpy array
        cell_ids = self._si.nearestNeighbor(p, 2)
        for cell_id in cell_ids:
            vert_ids = self._mesh.face(cell_id)
            if len(vert_ids) == 3:
                if self.point_in_triangle(p_, *self.vertex_position(vert_ids).tolist()):
                    if cell_id not in self._cell2triangle:
                        self._cell2triangle[cell_id] = [self._tri_count]
                        self._tri_count += 1
                    return cell_id
            elif len(vert_ids) == 4:
                if cell_id not in self._cell2triangle:
                    self._cell2triangle[cell_id] = [self._tri_count, self._tri_count + 1]
                    self._tri_count += 2
                for tri_idx in [(0, 1, 2), (2, 3, 0)]:
                    if self.point_in_triangle(p_, *self.vertex_position(p_[tri_idx]).tolist()):
                        return cell_id
        return -1

    def find_containing_triangle(self, point: PointLike, *args, **kwargs) -> int:
        p = self._coerce_into_qgs_point(point)
        p_ = self._coerce_into_point(point)  # numpy array
        cell_ids = self._si.nearestNeighbor(p, 2)
        for cell_id in cell_ids:
            vert_ids = np.array(self._mesh.face(cell_id))
            if len(vert_ids) == 3:
                if self.point_in_triangle(p_, *self.vertex_position(vert_ids).tolist()):
                    if cell_id in self._cell2triangle:
                        tri_id = self._cell2triangle[cell_id][0]
                    else:
                        tri_id = self._tri_count
                        self._cell2triangle[cell_id] = [tri_id]
                        self._tri_count += 1
                    if tri_id not in self._triangle2cell:
                        self._triangle2cell[tri_id] = cell_id
                    self._triangles[tri_id] = vert_ids.tolist()
                    return tri_id
            elif len(vert_ids) == 4:
                if cell_id in self._cell2triangle:
                    tri_ids = self._cell2triangle[cell_id]
                else:
                    tri_ids = [self._tri_count, self._tri_count + 1]
                    self._cell2triangle[cell_id] = tri_ids
                    self._tri_count += 2
                for tri_id, tri_idx in zip(tri_ids, [[0, 1, 2], [2, 3, 0]]):
                    if tri_id not in self._triangles:
                        self._triangles[tri_id] = vert_ids[tri_idx].tolist()
                    if tri_id not in self._triangle2cell:
                        self._triangle2cell[tri_id] = cell_id
                    if self.point_in_triangle(p_, *self.vertex_position(vert_ids[tri_idx]).tolist()):
                        return tri_id
        return -1

    @staticmethod
    def point_in_triangle(pt, v1, v2, v3):
        def sign(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - \
                (p2[0] - p3[0]) * (p1[1] - p3[1])
        b1 = sign(pt, v1, v2) < 0.0
        b2 = sign(pt, v2, v3) < 0.0
        b3 = sign(pt, v3, v1) < 0.0
        return (b1 == b2) and (b2 == b3)
