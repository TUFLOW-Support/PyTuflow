import typing
from pathlib import Path

import numpy as np
import pandas as pd
try:
    import vtk
except ImportError:
    from ..stubs import vtk
try:
    import pyvista as pv
except ImportError:
    from ..stubs import pyvista as pv

from .. import barycentric_coord, Bbox2D, Transform2D, PointMixin, PointLike, LineStringMixin, LineStringLike


class PyMeshGeometry(PointMixin, LineStringMixin):
    """Base class for mesh geometry."""

    def __init__(self, fpath: Path | str):
        # Path: File path to the mesh
        self.fpath = Path(fpath)
        #: np.ndarray: Mesh Vertex information (Nx3 array of x,y,z)
        self.vertices = np.array([])
        #: np.ndarray: Mesh Vertex information in local coordinates (Nx3 array of x,y,z)
        self.vertices_local = np.array([])
        #: np.ndarray: Cell information (flat array [nvert, v1, v3, v3, nvert, v1, v2, v3,...])
        self.cells = np.array([])
        #: pd.DataFrame: Cell information kept in a DataFrame for easy access (Nx5 - cell_id, v1, v2, v3, v4, where v4 is -1 for triangles)
        self.cells_df = pd.DataFrame()
        #: np.ndarray: Triangle IDs connected to each cell (Nx2 array of triangle IDs, the second ID is -1 if the cell is a triangle)
        self.cell2triangle = np.array([])
        #: np.ndarray: Mesh triangle information (Nx4 array of cell_id, n1, n2, n3). This is a triangle representation of the mesh, where quads are converted if needed.
        self.triangles = np.array([])
        #: Bbox: Mesh bounding box using global coordinates
        self.global_bbox = Bbox2D()
        #: Bbox: Mesh bounding box using local coordinates
        self.local_bbox = Bbox2D()
        #: Transform2D: transform settings for global to local coordinates
        self.trans = None
        #: pyvista.PolyData: pyvista mesh representation
        self.mesh = None
        #: bool: whether the mesh geometry contains elevation information
        self.has_z = False
        #: bool: whether the mesh is in spherical coordinates
        self.spherical = False
        #: vtk.vtkCellLocator: the cell locator for fast spatial searches
        self.locator = vtk.vtkStaticCellLocator()
        #: np.dtype: the data type used for coordinates
        self.dtype = np.float64

    def load(self):
        pass

    @staticmethod
    def create_triangles(quads: np.ndarray, tris: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Creates triangles from cells - quad cells will be split into 2 triangles, triangle cells will remain the same.

        Parameters
        ----------
        quads : np.ndarray
            The quad cell array.
        tris : np.ndarray
            The triangle cell array

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            Array of triangles Nx4 [cell_id, n1, n2, n3].
            Array of cell_id to triangle mapping Nx2 [tri1, tri2] unless them mesh only consists of triangles,
            in which case it is Nx1 [tri1].
        """
        triangles = np.array([])
        cell_id_to_tri = np.array([])
        if quads.size:
            triangles = np.append(
                quads[:, [0, 1, 2, 3]], quads[:, [0, 3, 4, 1]], axis=1
            ).reshape((-1, 4))
            cell_id_to_tri = np.append(quads[:, [0]], np.arange(triangles.shape[0]).reshape((-1, 2)), axis=1)

        if tris.size:
            if triangles.size:
                quad_tri_size = triangles.shape[0]
                triangles = np.append(triangles, tris, axis=0)
                cell_id_to_tri = np.append(
                    cell_id_to_tri,
                    np.append(
                        tris[:, [0]],
                        np.append(
                            np.arange(quad_tri_size, quad_tri_size + tris.shape[0]).reshape((-1, 1)),
                            np.full((tris.shape[0], 1), -1),
                            axis=1
                        ),
                        axis=1
                    ),
                    axis=0
                )
            else:
                triangles = tris
                cell_id_to_tri = np.append(tris[:, [0]], np.arange(triangles.shape[0]).reshape((-1, 1)), axis=1)

        return triangles, cell_id_to_tri[np.argsort(cell_id_to_tri[:, 0])][:, 1:]

    def cell_vertices(self, cell_id: int) -> list[int]:
        """Returns the vertex ids connected to the given cell.

        Parameters
        ----------
        cell_id : int
            The cell ID to return connected vertices.

        Returns
        -------
        list[int]
            The vertex IDs connected to the given cell.
        """
        vertex_ids = vtk.vtkIdList()
        self.mesh.GetCellPoints(cell_id, vertex_ids)
        return [vertex_ids.GetId(i) for i in range(vertex_ids.GetNumberOfIds())]

    def cell_triangles(self, cell_id: int) -> list[int]:
        """Returns the triangles that make up the given cell.

        Parameters
        ----------
        cell_id : int
            The cell ID to return connected triangles.

        Returns
        -------
        list[int]
            The triangle IDs that make up the given cell.
        """
        return [x for x in self.cell2triangle[cell_id].tolist() if x != -1]

    def cell_edges(self, cell_id: int) -> np.ndarray:
        """Returns the edges of the given cell as pairs of vertex IDs.

        Parameters
        ----------
        cell_id : int
            The cell ID to return edges for.

        Returns
        -------
        list[tuple[int, int]]
            A list of edges represented as tuples of vertex IDs.
        """
        vert_ids = self.cell_vertices(cell_id)
        return np.array([(vert_ids[i], vert_ids[(i + 1) % len(vert_ids)]) for i in range(len(vert_ids))])

    def cell_edge_neighbour(self, cell_id: int, edge: typing.Iterable[int]) -> int | None:
        """Returns the neighbouring cell id for the given cell edge.

        Parameters
        ----------
        cell_id : int
            The cell ID to get the neighbour for.
        edge : typing.Iterable[int]
            The edge to get the neighbour for as a list of two vertex IDs.

        Returns
        -------
        int | None
            The neighbouring cell ID, or None if there is no neighbour.
        """
        if isinstance(edge, (pd.Series, np.ndarray)):
            edge = edge.tolist()
        cell_ids = vtk.vtkIdList()
        self.mesh.GetCellEdgeNeighbors(cell_id, edge[0], edge[1], cell_ids)
        cells = [cell_ids.GetId(i) for i in range(cell_ids.GetNumberOfIds())]
        if cells:
            return cells[0]
        return None

    def vertex_cells(self, vertex_id: int) -> list[int]:
        """Returns the cell ids connected to the given vertex.

        Parameters
        ----------
        vertex_id : int
            The vertex to get the primitives connected to.

        Returns
        -------
        list[int]
            List of ``cell_ids`` connected to the given vertex.
        """
        cell_ids = vtk.vtkIdList()
        self.mesh.GetPointCells(vertex_id, cell_ids)
        return [cell_ids.GetId(i) for i in range(cell_ids.GetNumberOfIds())]

    def vertex_position(self, vertex_id: int | typing.Iterable[int] | slice, scope: str = 'global', *args, **kwargs) -> np.ndarray:
        """Returns the x,y position of the vertex ID(s).

        Parameters
        ----------
        vertex_id : int | typing.Iterable[int]
            The vertex ID(s) to return the position for.
        scope : str, optional
            The coordinate scope to return the position in. Options are ``"global"`` or ``"local"``.

        Returns
        -------
        pd.DataFrame
            The x,y,z positions of the vertex IDs.
        """
        if scope == 'global':
            return self.vertices[vertex_id]
        else:
            return self.vertices_local[vertex_id]

    def triangle_vertices(self, triangle_id: int) -> np.ndarray:
        """Returns the vertex ids connected to the given triangle.

        Parameters
        ----------
        triangle_id : int
            The triangle ID to return connected vertices.

        Returns
        -------
        list[int]
            The vertex IDs connected to the given triangle.
        """
        return self.triangles[triangle_id, 1:4]

    def triangle_cell(self, triangle_id: int) -> int:
        """Returns the cell that the triangle is a part of.

        Parameters
        ----------
        triangle_id : int | typing.Iterable[int]
            The triangle ID to return the cell for.

        Returns
        -------
        int
            The cell ID for the given triangle.
        """
        return int(self.triangles[triangle_id, 0])

    def barycentric_factors(self, point: PointLike, triangle: int, scope: str = 'global') -> np.ndarray:
        """Calculate the barycentric coordinates of a point within a triangle.

        Parameters
        ----------
        point : typing.Iterable[float]
            The global x,y position to calculate the barycentric coordinates for.
        triangle : int
            The triangle ID to calculate the barycentric coordinates within.
        scope : str, optional
            The coordinate scope of the point. Options are ``"global"`` or ``"local"``.

        Returns
        -------
        np.ndarray
            The barycentric coordinates (u, v, w) of the point within the triangle.
        """
        pos = self.vertex_position(self.triangle_vertices(triangle), 'local')
        p = self._coerce_into_point(point)
        if scope == 'global':
            p = self.trans.transform(p)

        u, v, w = barycentric_coord(
            p,
            pos[0, :2],
            pos[1, :2],
            pos[2, :2]
        )
        return np.array([u, v, w]).reshape((1, 3))

    def find_containing_cell(self, point: PointLike, scope: str = 'global') -> int:
        """Find the cell that contains the given point.

        Parameters
        ----------
        point : typing.Iterable[float]
            The x,y position to find the containing cell for.
        scope : str, optional
            The coordinate scope of the point. Options are ``"global"`` or ``"local"``.

        Returns
        -------
        int
            The cell ID that contains the given point, or -1 if no cell contains the point.
        """
        p = self._coerce_into_point(point)
        if scope == 'global':
            p = self.trans.transform(p)
        if p.size < 3:
            p = np.append(p, 0.0)
        return self.locator.FindCell(p.tolist())

    def find_containing_triangle(self, point: PointLike, scope: str = 'global', cell_id: int = -1) -> int:
        """Find the triangle that contains the given point.

        Parameters
        ----------
        point : typing.Iterable[float]
            The x,y position to find the containing triangle for.
        scope : str, optional
            The coordinate scope of the point. Options are ``"global"`` or ``"local"``.

        Returns
        -------
        int
            The triangle ID that contains the given point, or -1 if no triangle contains the point.
        """
        cell_id = self.find_containing_cell(point, scope=scope) if cell_id == -1 else cell_id
        if cell_id == -1:
            return -1
        p = self._coerce_into_point(point)
        if scope == 'global':
            p = self.trans.transform(p)

        def sign(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - \
                (p2[0] - p3[0]) * (p1[1] - p3[1])

        def point_in_triangle(pt, v1, v2, v3):
            b1 = sign(pt, v1, v2) < 0.0
            b2 = sign(pt, v2, v3) < 0.0
            b3 = sign(pt, v3, v1) < 0.0
            return (b1 == b2) and (b2 == b3)

        for tri_id in self.cell_triangles(cell_id):
            if point_in_triangle(p, *self.vertex_position(self.triangle_vertices(tri_id), 'local')[:,:2]):
                return tri_id

        return -1

    def cell_edge_intersections(self, cell_id: int, p0: np.ndarray, p1: np.ndarray, scope: str = 'global') -> np.ndarray:
        """Returns the intersection points between a line (p0, p1) and the edges of the given cell.

        Parameters
        ----------
        cell_id : int
            The cell ID to get edge intersections for.
        p0 : np.ndarray
            The start point of the line. Point can be 2D or 3D.
        p1 : np.ndarray
            The end point of the line. Point can be 2D or 3D.
        scope : str, optional
            The coordinate scope of the line points. Options are ``"global"`` or ``"local"``.

        Returns
        -------
        np.ndarray
            An array of intersection points between the line and the cell edges. Points are 2D (x,y).
        """
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

        if scope == 'global':
            p0 = self.trans.transform(p0)
            p1 = self.trans.transform(p1)
        edges = self.cell_edges(cell_id)
        pts = self.vertex_position(edges, scope='local').reshape((-1, 3))
        intersections = []
        for i in range(0, pts.shape[0], 2):
            p0_ = pts[i, :2]
            p1_ = pts[i+1, :2]
            pt = intersection(p0[:2], p1[:2], p0_, p1_)
            if pt is not None:
                intersections.append(pt)
        return np.array(intersections)

    def convert_bbox_to_local_coordinates(self, extents: typing.Iterable[float] | Bbox2D) -> Bbox2D:
        if not isinstance(extents, Bbox2D):
            pts = pd.DataFrame(np.array(extents).reshape(-1, 2))
            extents = Bbox2D(pts)
        trans = Transform2D(translate=[-self.global_bbox.x.min, -self.global_bbox.y.min])
        return extents.transform(trans)

    def distance(self, p2: np.ndarray, p1: np.ndarray) -> np.ndarray:
        n1 = 1 if p1.ndim == 1 else p1.shape[0]
        n2 = 1 if p2.ndim == 1 else p2.shape[0]
        if n1 != n2:
            p1 = np.repeat(p1.reshape(1, -1), n2, axis=0)
        return np.linalg.norm(p2.reshape(n2, -1) - p1.reshape(n2, -1), axis=1).reshape(n2,)

    def mesh_line(self,
                  line: LineStringLike,
                  scope: str = 'global',
                  ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Calculates the mesh intersections along a line. The line is broken into parts separated
        by where the mesh edges intersect the line.

        Returns 6 numpy arrays:

        1. ``N,`` - ``[cell ID]`` - The cell ids intersected by the line.
        2. ``Nx3`` - ``[offset, x, y]`` - Intersection points + start and end points
        3. ``Nx2`` - ``[dir-x, dir-y]`` - Direction vectors for each segment between intersections.
        4. ``N,`` - ``[cell ID]`` - The cell ids at mid-points between intersections.
        5. ``Nx3`` - ``[offset, x, y]`` - Mid-points between intersections + start and end points.
        6. ``Nx2`` - ``[dir-x, dir-y]`` - Direction vectors for each mid-segment between intersections.

        Uses float32 since coordinates have all been converted to local space. Does this to try and make
        this method as fast as possible.

        Parameters
        ----------
        line : LineStringLike
            The line to calculate the mesh intersections for. Format should be
            some vector of floats or a shapely.LineString.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            Returns 6 numpy arrays:

            1. ``N,`` - ``[cell ID]`` - The cell ids intersected by the line.
            2. ``Nx3`` - ``[offset, x, y]`` - Intersection points + start and end point.
            3. ``Nx2`` - ``[dir-x, dir-y]`` - Direction vectors for each segment between intersections.
            4. ``N,`` - ``[cell ID]`` - The cell ids at mid-points between intersections.
            5. ``Nx3`` - ``[offset, x, y]`` - Mid-points between intersections + start and end points.
            6. ``Nx2`` - ``[dir-x, dir-y]`` - Direction vectors for each mid-segment between intersections.
        """
        line = self._coerce_into_line(line)
        if scope == 'global':
            line = self.trans.transform(line).astype(self.dtype)

        cell_ids = np.array([])
        mid_cell_ids = np.array([])
        acell = np.array([])
        amid = np.array([])
        dir_ = np.array([])
        dir_mid = np.array([])
        for i in range(1, line.shape[0]):
            seg = line[i-1:i+1,:2]
            d  = (seg[1] - seg[0]) / np.linalg.norm(seg[1] - seg[0])
            c1, a1, c2, a2 = self._mesh_line_segment(seg)
            if cell_ids.size == 0:
                cell_ids = c1
                acell = a1
                mid_cell_ids = c2
                amid = a2
                dir_ = np.full((c1.shape[0], 2), d)
                dir_mid = np.full((c2.shape[0], 2), d)
            else:
                cell_ids = np.append(cell_ids[:-1], c1)
                mid_cell_ids = np.append(mid_cell_ids[:-1], c2[1:])
                a1[:,0] += acell[-1, 0]
                a2[:,0] += acell[-1, 0]
                acell = np.append(acell[:-1,...], a1, axis=0)
                amid = np.append(amid[:-1,...], a2[1:,...], axis=0)
                dir_ = np.append(dir_[:-1,...], np.full((c1.shape[0], 2), d), axis=0)
                dir_mid = np.append(dir_mid[:-1,...], np.full((c2.shape[0] - 1, 2), d), axis=0)

        return cell_ids, acell, dir_, mid_cell_ids, amid, dir_mid

    def _mesh_line_segment(self, line: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """The workhorse for the above routine. Calculates per line segment information."""
        p1 = np.append(line[0], self.dtype(0))
        p2 = np.append(line[1], self.dtype(0))
        points, cell_ids = self._mesh_intersects(p1, p2)

        length = self.distance(p2, p1).astype(self.dtype)[0]
        if cell_ids.size == 0:
            mid_point = (p1 + p2) / 2.
            return (
                np.array([-1, -1]),
                np.array([[0., p1[0], p1[1]], [length, p2[0], p2[1]]]),
                np.array([-1, -1, -1]),
                np.array([[0., p1[0], p1[1]], [length / 2, mid_point[0], mid_point[1]], [length, p2[0], p2[1]]])
            )

        # unique points with tolerance
        k = 4
        eps = np.finfo(self.dtype).eps
        atol = rtol = k * eps
        unique = [points[0]]
        idx = [0]
        nudged = []
        for i, p in enumerate(points[1:]):
            if not np.all(np.isclose(p, unique[-1], atol=atol, rtol=rtol)):
                unique.append(p)
                idx.append(i + 1)
            elif idx[-1] not in nudged:
                # nudge point in direction of line to find the correct cell
                j = idx[-1]
                nudged.append(j)
                dir_ = ((p2 - p1) / np.linalg.norm(p2 - p1))[:2]
                p = p + dir_ * atol * k
                id_ = self.find_containing_cell(p, scope='local')
                if id_ != -1:
                    cell_ids[j] = id_

        points = np.array(unique, dtype=self.dtype)
        cell_ids = cell_ids[idx]

        # figure out if the line leaves the mesh and then re-enters
        offsets = self.distance(points, p1[:2]).astype(self.dtype)
        mid_offsets = np.append(self.dtype(0), offsets + np.append(np.diff(offsets) / 2., self.dtype(0)))
        dir_ = (p2 - p1)[:2].astype(self.dtype).reshape((1, 2)) / length
        p0 = p1[:2].reshape((1, 2))
        mid_points = p0 + dir_ * mid_offsets.reshape((-1, 1))
        mid_cell_ids = np.array([self.find_containing_cell(pt, scope='local') for pt in mid_points])
        outside_idx = np.flatnonzero(np.diff(np.diff((np.array(mid_cell_ids) == -1).astype(int))) == -2)
        if outside_idx.size:
            polyline = [p1[:2]] + mid_points[outside_idx + 1].tolist() + [p2[:2]]
            cell_ids, points, _, mid_cell_ids, mid_points, _ = self.mesh_line(polyline, scope='local')
            mask = np.flatnonzero(np.diff(np.diff((np.array(cell_ids) == -1).astype(int))) == -2)
            cell_ids[mask] = -1
            mask = np.arange(cell_ids.size) != mask + 1
            return cell_ids[mask], points[mask], mid_cell_ids, mid_points

        # test if p1 or p2 are outside the mesh
        p1_outside = self.find_containing_cell(p1, scope='local') == -1
        p2_outside = self.find_containing_cell(p2, scope='local') == -1

        # if p2 is outside the mesh append the last intersection point, else append p2
        if p2_outside:
            last_cell = cell_ids[-1]
            last_point = points[-1]
            intersections = self.cell_edge_intersections(last_cell, p1, p2, scope='local')
            atol_ = rtol_ = 4 * np.finfo(np.float32).eps if isinstance(self._mesh, pv.PolyData) else atol
            for pt in intersections:
                if not np.isclose(last_point, pt, atol=atol_, rtol=rtol_).all():
                    points = np.append(points, pt.reshape((-1, 2)), axis=0)
                    break
            else:
                raise RuntimeError('Unexpected condition: p2 is outside but no final intersection found.')
        else:
            points = np.append(points, p2[:2].reshape((-1, 2)), axis=0)

        cell_ids = np.append(cell_ids, cell_ids[-1])
        offsets = self.distance(points, p1[:2]).astype(self.dtype)

        if p1_outside:
            cell_ids = np.append([-1], cell_ids)
            points = np.append(p1[:2].reshape((-1, 2)), points, axis=0)
            offsets = np.append(self.dtype(0), offsets)
        mid_offsets = np.append(self.dtype(0), offsets + np.append(np.diff(offsets) / 2., self.dtype(0)))
        if p2_outside:
            cell_ids = np.append(cell_ids, [-1])
            points = np.append(points, p2[:2].reshape((-1, 2)), axis=0)
            offsets = np.append(offsets, length)
            mid_offsets = np.append(mid_offsets, length)
            mid_offsets[-2] = (mid_offsets[-1] + mid_offsets[-2]) / 2.

        mid_cell_ids = np.append(cell_ids[0], cell_ids)

        p0 = p1[:2].reshape((1, 2))
        dir_ = (p2 - p1)[:2].astype(self.dtype).reshape((1, 2)) / length
        mid_points = p0 + dir_ * mid_offsets.reshape((-1, 1))

        return (
            cell_ids, np.append(offsets.reshape((-1, 1)), points, axis=1),
            mid_cell_ids, np.append(mid_offsets.reshape((-1, 1)), mid_points, axis=1)
        )

    def _mesh_intersects(self, p1: np.ndarray, p2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Checks if a line segment intersects the mesh."""
        points = vtk.vtkPoints()
        cell_ids = vtk.vtkIdList()
        tol = 1e-6
        self.locator.IntersectWithLine(p1, p2, tol, points, cell_ids)
        if points.GetNumberOfPoints() > 0:
            points = np.array([points.GetPoint(i) for i in range(points.GetNumberOfPoints())], dtype=self.dtype)[:, :2]
            cell_ids = np.array([cell_ids.GetId(i) for i in range(cell_ids.GetNumberOfIds())])
        else:
            points, cell_ids = np.array([]), np.array([])
        return points, cell_ids

    def _build_locator(self, mesh: pv.PolyData) -> vtk.vtkStaticCellLocator:
        locator = vtk.vtkStaticCellLocator()
        locator.SetDataSet(mesh)
        locator.BuildLocator()
        return locator
