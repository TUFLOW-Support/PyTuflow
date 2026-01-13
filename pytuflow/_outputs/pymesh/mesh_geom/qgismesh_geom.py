import typing
from pathlib import Path

import numpy as np

try:
    from qgis.core import (QgsApplication, QgsMesh, QgsMeshLayer, QgsMeshSpatialIndex, QgsPoint,
                           QgsPointXY, QgsGeometry, QgsMeshDatasetIndex, QgsProject, QgsDistanceArea)
except ImportError:
    from ..stubs.qgis.core import (QgsApplication, QgsMesh, QgsMeshLayer, QgsMeshSpatialIndex, QgsPoint,
                                   QgsPointXY, QgsGeometry, QgsMeshDatasetIndex, QgsProject, QgsDistanceArea)

from . import PyMeshGeometry
from .. import ellipsoid_distance, Transform2D, PointMixin, PointLike


class PointMixinQgis(PointMixin):

    @staticmethod
    def _coerce_into_point(value: PointLike) -> np.ndarray:
        if isinstance(value, (QgsPoint, QgsPointXY)):
            return np.array([value.x(), value.y()])
        return PointMixin._coerce_into_point(value)

    @staticmethod
    def _coerce_into_qgs_point(value: PointLike) -> QgsPointXY:
        p = PointMixinQgis._coerce_into_point(value)
        return QgsPointXY(*p.tolist()[:2])



class QgisMeshGeometry(PyMeshGeometry, PointMixinQgis):

    def __init__(self, fpath: Path | str):
        super().__init__(fpath)
        self.has_z = True
        self.trans = Transform2D()
        self.lyr = None
        self._mesh = QgsMesh()
        self._si = None
        self._loaded = False

        self._cell2triangle = {}
        self._triangle2cell = {}
        self._triangles = {}
        self._tri_count = 0
        self._ibed = -1
        self.dtype = np.float64

    def load(self):
        if not QgsApplication.instance():
            raise RuntimeError('QGIS application instance not found.')
        if not self._loaded:
            if self.lyr is None:
                self.lyr = QgsMeshLayer(str(self.fpath), self.fpath.stem, 'mdal')
            if self._si is None:
                dp = self.lyr.dataProvider()
                dp.populateMesh(self._mesh)
                self._si = QgsMeshSpatialIndex(self._mesh)
            if self._ibed == -1:
                for i in range(self.lyr.dataProvider().datasetGroupCount()):
                    if self.lyr.dataProvider().datasetGroupMetadata(i).name().lower() == 'bed elevation':
                        self._ibed = i
                        break
            self._loaded = True

    def cell_vertices(self, cell_id: int) -> list[int]:
        return list(self._mesh.face(cell_id))

    def vertex_position(self, vertex_id: int | typing.Iterable[int], get_z: bool = True, *args, **kwargs) -> np.ndarray:
        if isinstance(vertex_id, (list, tuple)):
            vertex_id = np.array(vertex_id).flatten().tolist()
        if isinstance(vertex_id, int):
            vertex_id = [vertex_id]
        if isinstance(vertex_id, np.ndarray):
            vertex_id = vertex_id.flatten().tolist()
        a = np.full((len(vertex_id), 3), -1, dtype=np.float64)
        for i, vid in enumerate(vertex_id):
            v = self._mesh.vertex(vid)
            a[i, 0] = v.x()
            a[i, 1] = v.y()
            if get_z:
                a[i, 2] = self.lyr.dataProvider().datasetValue(QgsMeshDatasetIndex(self._ibed, 0), vid).scalar()
            else:
                a[i, 2] = 0.
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
            vert_ids = np.array(self.cell_vertices(cell_id))
            if len(vert_ids) == 3:
                if self.point_in_triangle(p_, *self.vertex_position(vert_ids, get_z=False).tolist()):
                    if cell_id not in self._cell2triangle:
                        self._cell2triangle[cell_id] = [self._tri_count]
                        self._tri_count += 1
                    return cell_id
            elif len(vert_ids) == 4:
                if cell_id not in self._cell2triangle:
                    self._cell2triangle[cell_id] = [self._tri_count, self._tri_count + 1]
                    self._tri_count += 2
                for tri_idx in [[0, 1, 2], [2, 3, 0]]:
                    if self.point_in_triangle(p_, *self.vertex_position(vert_ids[tri_idx], get_z=False).tolist()):
                        return cell_id
        return -1

    def find_containing_triangle(self, point: PointLike, *args, **kwargs) -> int:
        p = self._coerce_into_qgs_point(point)
        p_ = self._coerce_into_point(point)  # numpy array
        cell_ids = self._si.nearestNeighbor(p, 2)
        for cell_id in cell_ids:
            vert_ids = np.array(self._mesh.face(cell_id))
            if len(vert_ids) == 3:
                if self.point_in_triangle(p_, *self.vertex_position(vert_ids, get_z=False).tolist()):
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
                    if self.point_in_triangle(p_, *self.vertex_position(vert_ids[tri_idx], get_z=False).tolist()):
                        return tri_id
        return -1

    def cell_edge_intersections(self, cell_id: int, p0: np.ndarray, p1: np.ndarray, scope: str = 'global') -> np.ndarray:
        def cross2d(x: np.ndarray, y: np.ndarray) -> np.ndarray:
            """2D cross product. Numpy 2.0 deprecates np.cross for 2D arrays."""
            return x[..., 0] * y[..., 1] - x[..., 1] * y[..., 0]

        def intersection(p1: np.ndarray, p2: np.ndarray, q1: np.ndarray, q2: np.ndarray) -> np.ndarray | None:
            """Finds the intersection between 2 lines (p1, p2) and (q1, q2)."""
            r = p2 - p1
            s = q2 - q1
            denom = cross2d(r, s)
            if abs(denom) < 1e-12:
                return None  # parallel
            t = cross2d((q1 - p1), s) / denom
            u = cross2d((q1 - p1), r) / denom
            if 0 <= t <= 1 and 0 <= u <= 1:
                return p1 + t * r
            return None

        edges = self.cell_edges(cell_id)
        pts = self.vertex_position(edges, get_z=False).reshape((-1, 3))
        intersections = []
        for i in range(0, pts.shape[0], 2):
            p0_ = pts[i, :2]
            p1_ = pts[i+1, :2]
            pt = intersection(p0[:2], p1[:2], p0_, p1_)
            if pt is not None:
                intersections.append(pt)
        return np.array(intersections)

    @staticmethod
    def point_in_triangle(pt, v1, v2, v3):
        def sign(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - \
                (p2[0] - p3[0]) * (p1[1] - p3[1])
        b1 = sign(pt, v1, v2) < 0.0
        b2 = sign(pt, v2, v3) < 0.0
        b3 = sign(pt, v3, v1) < 0.0
        return (b1 == b2) and (b2 == b3)

    def distance(self, p2: np.ndarray, p1: np.ndarray) -> np.ndarray:
        if not self.spherical:
            return super().distance(p2, p1)
        n1 = 1 if p1.ndim == 1 else p1.shape[0]
        n2 = 1 if p2.ndim == 1 else p2.shape[0]
        if n1 != n2:
            p1 = np.repeat(p1.reshape(1, -1), n2, axis=0)
        return ellipsoid_distance(p2.reshape(n2, -1), p1.reshape(n1, -1))

    def _mesh_intersects(self, p1: np.ndarray, p2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Returns points and cell_ids where the line segment intersects the mesh. Last point is not returned."""
        tol = 1e-6
        interval = 1
        geom = QgsGeometry.fromPolylineXY([QgsPointXY(*p1.tolist()[:2]), QgsPointXY(*p2.tolist()[:2])])
        dense = geom.densifyByDistance(interval)
        first_cell = self.find_containing_cell(p1)
        ret_points, ret_cell_ids = [], []
        if first_cell != -1:
            ret_points = [p1[:2]]
            ret_cell_ids = [first_cell]
        last_cell_id = first_cell
        for i, p_start in enumerate(dense.vertices()):
            try:
                p_end = dense.vertexAt(i + 1)
                if p_end.isEmpty():
                    break
            except Exception:
                break
            points = {}
            cell_ids = self._si.intersects(QgsGeometry.fromPolylineXY([QgsPointXY(p_start), QgsPointXY(p_end)]).boundingBox())
            for cell_id in cell_ids:
                intersects = self.cell_edge_intersections(cell_id, self._coerce_into_point(p_start), self._coerce_into_point(p_end))
                for p in intersects:
                    vec = np.array([p[0] - p_start.x(), p[1] - p_start.y()])
                    offset = np.linalg.norm(vec)
                    if offset == 0:
                        continue
                    dir_ = vec / offset
                    nudge = p + dir_ * tol
                    cell_id = self.find_containing_cell(nudge)
                    if cell_id != -1 and cell_id not in points and cell_id != last_cell_id:
                        points[cell_id] = (offset, self._coerce_into_point(p)[:2])
            if points:
                sorted_points = sorted(points.items(), key=lambda x: x[1][0])
                for cell_id, (offset, p) in sorted_points:
                    ret_points.append(p)
                    ret_cell_ids.append(cell_id)
                    last_cell_id = cell_id

        return np.array(ret_points).reshape(-1, 2), np.array(ret_cell_ids)
