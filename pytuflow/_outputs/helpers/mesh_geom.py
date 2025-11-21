from math import pi, cos, sin
from typing import TYPE_CHECKING, Union, Any, Generator

import numpy as np
# noinspection PyUnresolvedReferences
from qgis.core import (QgsPolygon, QgsLineString, QgsPoint, QgsPointXY, QgsGeometry, QgsMeshLayer, QgsProject,
                       QgsCoordinateReferenceSystem, QgsRectangle, QgsVectorLayer, QgsFeature,
                       QgsGeometryUtils, QgsMeshDatasetGroupMetadata)

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from qgis.core import QgsMesh, QgsMeshSpatialIndex


def mid_point(p1: 'QgsPointXY', p2: 'QgsPointXY') -> 'QgsPointXY':
    return QgsPointXY(QgsGeometryUtils.interpolatePointOnLine(QgsPoint(p1), QgsPoint(p2), 0.5))


def vertex_indices_to_polygon(mesh: 'QgsMesh', vertex_indices: list[int]) -> QgsPolygon:
    """Convert the mesh face to a polygon geometry."""
    return QgsPolygon(QgsLineString([QgsPointXY(mesh.vertex(x).x(), mesh.vertex(x).y()) for x in vertex_indices]))


# noinspection PyTypeHints
def closest_face_indexes(
        points: list['QgsPointXY'],
        si: 'QgsMeshSpatialIndex',
        mesh: 'QgsMesh',
        count: int = 1) -> list[int]:
    """
    Calculates the closest mesh face for the first point in the points list. If a second point is provided, it will
    be used to help calculate the closest face with the assumption that it is part of a line segment.
    Always returns a list of up to the 'count' (if possible) and checks for mesh containment, and side intersection.
    """

    face_indexes = []
    if not points:
        return face_indexes

    for p in points:
        neigh_indexes = si.nearestNeighbor(p, count)
        if neigh_indexes:
            for ind in neigh_indexes:
                polygon = vertex_indices_to_polygon(mesh, mesh.face(ind))
                geom = QgsGeometry()
                geom.fromWkb(polygon.asWkb())
                if (geom.contains(p) or geom.intersects(QgsGeometry.fromPointXY(p)) or
                        (len(points) > 1 and geom.contains(QgsGeometry.fromPointXY(mid_point(p, points[1]))))):
                    face_indexes.append(ind)
                    if 0 < count == len(face_indexes):
                        break

    return face_indexes


def calculate_barycentric_weightings(mesh: 'QgsMesh',
                                     triangle: list[int],
                                     point: 'QgsPointXY') -> tuple[float, float, float]:
    """Returns barycentric interpolation weightings for a point in a triangle"""
    v1x = mesh.vertex(triangle[0]).x()  # vertex 1 x coord
    v1y = mesh.vertex(triangle[0]).y()  # vertex 1 y coord
    v2x = mesh.vertex(triangle[1]).x()  # vertex 2 x
    v2y = mesh.vertex(triangle[1]).y()  # vertex 2 y
    v3x = mesh.vertex(triangle[2]).x()  # vertex 3 x
    v3y = mesh.vertex(triangle[2]).y()  # vertex 3 y
    px = point.x()  # point x
    py = point.y()  # point y

    # weighting vertex 1
    # noinspection DuplicatedCode
    w1numer = (v2y - v3y) * (px - v3x) + (v3x - v2x) * (py - v3y)
    w1denom = (v2y - v3y) * (v1x - v3x) + (v3x - v2x) * (v1y - v3y)
    w1 = w1numer / w1denom
    assert w1 >= 0, "barycentric weighting cannot be negative"

    # weighting vertex 2
    # noinspection DuplicatedCode
    w2numer = (v3y - v1y) * (px - v3x) + (v1x - v3x) * (py - v3y)
    w2denom = (v2y - v3y) * (v1x - v3x) + (v3x - v2x) * (v1y - v3y)
    w2 = w2numer / w2denom
    assert w2 >= 0, "barycentric weighting cannot be negative"

    # weighting vertex 3
    w3 = 1.0 - w1 - w2
    assert w3 >= 0, "barycentric weighting cannot be negative"

    return w1, w2, w3


class PolyLine:
    """
    Helper class for polylines/linestrings to allow easy iteration of line segments as well as slicing line to get
    points at index.
    """

    def __init__(self, linestring: Any):
        self.linestring = linestring

    def __getitem__(self, item: Any):
        return [x for x in self.linestring][item]

    def __iter__(self):
        if len(self.linestring) > 1:
            for i, p2 in enumerate(self.linestring):
                if i == 0:
                    continue
                p1 = self.linestring[i-1]
                yield p1, p2


intersect_counter = -1


class Intersect:
    """
    Intersect class to storing intersecting line segments and information about the intersection.

    Initialisation parameters:
        p1: QgsPoint - start point of first line segment
        p2: QgsPoint - end point of first line segment
        p3: QgsPoint - start point of second line segment
        p4: QgsPoint - end point of second line segment
        v1: int - mesh vertex index of first line segment
        v2: int - mesh vertex index of second line segment
        face: Face - mesh face that contain v1, v2
        segment_start: bool - True if p1, p2 is the first line segment in a polyline, False otherwise
    """

    def __init__(
            self,
            p1: QgsPoint,
            p2: QgsPoint,
            p3: QgsPoint,
            p4: QgsPoint,
            v1: int | None,
            v2: int | None,
            face: 'Face | None',
            segment_start: bool = False):
        self.p1 = QgsPointXY(p1)
        self.p2 = QgsPointXY(p2)
        self.p3 = QgsPointXY(p3)
        self.p4 = QgsPointXY(p4)
        self.v1 = v1
        self.v2 = v2
        self.face = face
        self.pline1 = QgsGeometry.fromPolylineXY([self.p1, self.p2])
        self.pline2 = QgsGeometry.fromPolylineXY([self.p3, self.p4])
        self.dist = None
        self.segment_start = segment_start
        self._point = None
        if self.p1 == self.p2 == self.p3 == self.p4:
            self._point = self.p1
        global intersect_counter
        intersect_counter += 1
        self.uid = f'{self.v1}-{self.v2}-{self.face}-{intersect_counter}'

    def __repr__(self):
        return f'<Intersect: {self._point}>'

    def __bool__(self):
        """bool operator. True if intersecting, False otherwise."""
        return self.intersects()

    def __eq__(self, other: Any):
        """
        Equality checker. Equal if v1 and v2 (which form the second intersecting line from the mesh element)
        are the same and the intersection point is the same.
        """
        if isinstance(other, Intersect):
            if self.v1 is None or self.v2 is None or other.v1 is None or other.v2 is None:
                return False
            return sorted([self.v1, self.v2]) == sorted([other.v1, other.v2]) and self.point() == other.point()
        return False

    def __gt__(self, other):
        """Greater than operator to help sorting. Uses linear distance along the polyline."""
        if isinstance(other, Intersect):
            return self.dist > other.dist
        return NotImplemented

    def __hash__(self):
        return hash(self.uid)

    def intersects(self):
        """Check if the two line segments intersect."""
        return self.pline1.intersects(self.pline2)

    def point(self):
        """Return the intersection point. Should really only be called if intersects() returns True."""
        if self._point is None:
            try:
                self._point = self.pline1.intersection(self.pline2).asPoint()
            except TypeError:
                self._point = self.p1 if self.segment_start else self.p2
        return self._point

    def calc_distance(self, linestring: QgsLineString):
        """Calculate the distance along the linestring to the intersection point."""
        geom = QgsGeometry()
        geom.fromWkb(linestring.asWkb())
        ret = geom.closestSegmentWithContext(self.point())
        i_vert_after = ret[2]
        if i_vert_after == 0:
            return
        p1 = QgsPointXY(PolyLine(linestring)[i_vert_after-1])
        geom_ = QgsGeometry.fromPolylineXY([p1, self.point()])
        self.dist = geom_.length()
        if i_vert_after > 1:
            self.dist += geom.distanceToVertex(i_vert_after-1)

    def intersect_vector(self) -> np.ndarray:
        """Returns the normalized intersecting line segment vector as a numpy array."""
        a = np.array([[self.p2.x() - self.p1.x()], [self.p2.y() - self.p1.y()]])
        norm = np.linalg.norm(a)
        if norm == 0:
            return a
        return a / norm

    def intersect_vector_perp(self) -> np.ndarray:
        """Returns the normalized vector that is perpendicular to the intersecting line segment as a numpy array."""
        a = self.intersect_vector()
        r = np.array([[0, -1], [1, 0]])  # 90 degree rotation matrix
        return np.dot(r, a)


class Faces:
    """
    Helper class to hold a list of faces. Helps with iteration and generating faces along intersecting line segments.

    Initialisation parameters:
        faces: list[Union[int, Face]] - list of mesh faces as either integer indexes or Face objects
        mesh: QgsMesh - mesh object
        si: QgsMeshSpatialIndex - spatial index of mesh
    """

    def __init__(self, faces: list[Union[int, 'Face']], mesh: 'QgsMesh', si: 'QgsMeshSpatialIndex'):
        self._faces = faces
        if self._faces and isinstance(self._faces[0], int):
            self.faces = self._faces[:]
        else:
            self.faces = [x.face for x in self._faces]
        self.mesh = mesh
        self.si = si

    def __repr__(self):
        return f'<Faces>'

    def __next__(self):
        for face in self.faces:
            yield Face(face, self.mesh)

    def __iter__(self):
        return next(self)

    def get_faces_along_intersects(self, intersects):
        """walks through the points and generates a list of mesh Face objects in order."""
        faces = []
        faces_for_checking = []
        points = [x.point() for x in intersects]
        for i, intersect in enumerate(intersects):
            point = intersect.point()
            if intersect.segment_start and i > 0:
                faces_for_checking.clear()
            if i + 1 == len(intersects):
                faces_ = closest_face_indexes([point], self.si, self.mesh, 2)
            else:
                faces_ = closest_face_indexes(points[i:i+2], self.si, self.mesh, 2)
            for face in faces_:
                if face not in faces_for_checking and (not intersect.segment_start or face not in faces):
                    faces.append(face)
                    faces_for_checking.append(face)
        return [Face(x, self.mesh) for x in faces]


face_counter = -1


class Face:
    """
    Helper class to store mesh face information. Helps with iteration vertexes and intersections.

    Initialisation parameters:
        face: int - face index
        mesh: QgsMesh - mesh object
    """

    def __init__(self, face: int, mesh: 'QgsMesh'):
        self.face = face
        self.mesh = mesh
        self.verts = mesh.face(face)
        global face_counter
        face_counter += 1
        self.uid = f'{self.face}-{face_counter}'

    def __repr__(self):
        return f'<Face {self.face}>'

    def __iter__(self):
        for i, v2 in enumerate(self.verts[1:]):
            v1 = self.verts[i]
            yield v1, v2
        yield self.verts[-1], self.verts[0]

    def __hash__(self):
        return hash(self.uid)

    def __eq__(self, other):
        if isinstance(other, Face):
            return self.face == other.face
        return False

    def intersect(self, p1: QgsPoint, p2: QgsPoint) -> Generator[Intersect, None, None]:
        """Yields intersect objects for each intersection between the mesh and the line segment p1-p2."""
        for v1, v2 in self:
            p3 = self.mesh.vertex(v1)
            p4 = self.mesh.vertex(v2)
            intersect = Intersect(p1, p2, p3, p4, v1, v2, self)
            if intersect:
                intersect.point()
                yield intersect


class IntersectResult:
    """
    Helper class for storing information when an intersection is returned for result extraction.
    Class will hold information on chainage(s), face, point. The stored values
    will depend on whether results should be extracted from faces or vertices.
    """

    def __init__(self,
                 type_: str,
                 dist1: float,
                 dist2: float,
                 point: QgsPointXY,
                 start_side: float,
                 end_side: float,
                 start_point: QgsPointXY,
                 end_point: QgsPointXY,
                 intersect_vector: np.ndarray,
                 intersect_vector_perp: np.ndarray,
                 ):
        self.type = type_
        self.dist1 = dist1
        self.dist2 = dist2
        self.point = point
        self.start_side = start_side
        self.end_side = end_side
        self.mid_dist = (start_side + end_side) / 2.
        self.start_point = start_point
        self.end_point = end_point
        self.intersect_vector = intersect_vector
        self.intersect_vector_perp = intersect_vector_perp

    def __repr__(self):
        return f'<IntersectResult {self.type}-{self.dist1}>'


class MeshIntersects:
    """Class to hold mesh intersect information and to help process it (calculate chainages etc.)."""

    def __init__(self, mesh, si, linestring: 'QgsLineString'):
        self.mesh = mesh
        self.si = si
        self.linestring = linestring
        self.intersects = []
        self.faces = []
        self._sorted = False

    def __repr__(self):
        return '<MeshIntersects>'

    def __bool__(self):
        return bool(self.intersects)

    def count(self, group_metadata: 'QgsMeshDatasetGroupMetadata') -> int:
        len_ = len(self.intersects)
        if group_metadata.dataType() == QgsMeshDatasetGroupMetadata.DataOnVertices:
            len_ += 2
        return len_

    def sort(self):
        self.intersects.sort()
        faces = Faces(self.faces, self.mesh, self.si)
        self.faces = faces.get_faces_along_intersects(self.intersects)

    def iter(self, group_metadata: 'QgsMeshDatasetGroupMetadata') -> Generator[IntersectResult, None, None]:
        """Yields intersect result objects used for result plotting."""
        # sort points in order if they haven't been sorted already
        if not self._sorted:
            self.intersects.sort()
            self._sorted = True

        # dataset type
        if group_metadata.dataType() == QgsMeshDatasetGroupMetadata.DataOnVertices:
            type_ = 'vertex'
        else:
            type_ = 'face'

        if len(self.intersects) < 2:
            return

        # yield first point for vertex result data
        if type_ == 'vertex' and self.intersects:
            yield IntersectResult(
                type_,
                0,
                0,
                self.intersects[0].point(),
                0,
                0,
                self.intersects[0].point(),
                self.intersects[1].point(),
                self.intersects[0].intersect_vector(),
                self.intersects[0].intersect_vector_perp(),
            )

        # iterate through intersects and yield mid-points
        for inter1, inter2 in PolyLine(self.intersects):  # loop through segments between intersections
            mid_point_ = mid_point(inter1.point(), inter2.point())
            if type_ == 'vertex':
                dist1 = QgsGeometry.fromPointXY(inter1.point()).distance(QgsGeometry.fromPointXY(mid_point_))
                dist1 += inter1.dist
                dist2 = dist1
            else:
                dist1 = inter1.dist
                dist2 = inter2.dist
            yield IntersectResult(
                type_,
                dist1,
                dist2,
                mid_point_,
                inter1.dist,
                inter2.dist,
                inter1.point(),
                inter2.point(),
                inter1.intersect_vector(),
                inter1.intersect_vector_perp(),
            )

        # yield last point for vertex result data
        if type_ == 'vertex' and self.intersects:
            yield IntersectResult(
                type_,
                self.intersects[-1].dist,
                self.intersects[-1].dist,
                self.intersects[-1].point(),
                self.intersects[-1].dist,
                self.intersects[-1].dist,
                self.intersects[-2].point(),
                self.intersects[-1].point(),
                self.intersects[-1].intersect_vector(),
                self.intersects[-1].intersect_vector_perp(),
            )

    def iter_polyline(self) -> Generator[tuple[QgsPoint, QgsPoint], None, None]:
        for p1, p2 in PolyLine(self.linestring):
            yield p1, p2

    def add(self, intersect: Intersect) -> None:
        if intersect not in self.intersects:
            intersect.calc_distance(self.linestring)
            self.intersects.append(intersect)
        if intersect.face and intersect.face not in self.faces:
            self.faces.append(intersect.face)

    def write_faces(self, crs: QgsCoordinateReferenceSystem) -> QgsVectorLayer:
        """Routine to help debug. Writes out the selected faces to a memory layer."""
        lyr = QgsVectorLayer(f'polygon?crs=epsg:{crs.authid()}&field=face_index:integer', "faces", "memory")
        dp = lyr.dataProvider()
        lyr.startEditing()
        for face in self.faces:
            feat = QgsFeature(lyr.fields())
            poly = vertex_indices_to_polygon(self.mesh, self.mesh.face(face.face))
            geometry = QgsGeometry()
            geometry.fromWkb(poly.asWkb())
            feat.setGeometry(geometry)
            feat.setAttributes([face.face])
            dp.addFeature(feat)
        lyr.commitChanges()
        lyr.updateExtents()
        return lyr

    def write_intersects(self, crs: QgsCoordinateReferenceSystem) -> QgsVectorLayer:
        """Routine to help debug. Writes out the selected intersect points to a memory layer."""
        lyr = QgsVectorLayer(f'point?crs=epsg:{crs.authid()}&field=dist:double', "intersects", "memory")
        dp = lyr.dataProvider()
        lyr.startEditing()
        for intersect in self.intersects:
            feat = QgsFeature(lyr.fields())
            feat.setGeometry(QgsGeometry.fromPointXY(intersect.point()))
            feat.setAttributes([intersect.dist])
            dp.addFeature(feat)
        lyr.commitChanges()
        lyr.updateExtents()
        return lyr


def mesh_intersects(mesh: 'QgsMesh',  si: 'QgsMeshSpatialIndex', linestring: 'QgsLineString'):
    """
    Function to find mesh intersections for a given polyline and QgsMesh.

    The returned class will contain a list of mesh faces and mesh side intersection points (QgsPointXY).
    Methods can be called on the class to return distances, faces, and mid-points between intersection points.
    """
    intersects = MeshIntersects(mesh, si, linestring)
    p2 = None
    for p1, p2 in intersects.iter_polyline():  # loop through polyline segments
        faces = si.intersects(QgsRectangle(QgsPointXY(p1), QgsPointXY(p2)))  # spatial grab of all faces in the bbox
        for face in Faces(faces, mesh, si):  # loop through each face and check for intersection with the segment
            for intersect in face.intersect(p1, p2):
                intersects.add(intersect)
        # add first segment point
        intersects.add(Intersect(p1, p2, p1, p1, None, None, None, segment_start=True))

    # add last linestring point
    if p2:
        intersects.add(Intersect(p1, p2, p2, p2, None, None, None))

    return intersects


def angle_correction(point1: QgsPointXY, point2: QgsPointXY, vector: tuple[float, float]) -> float:
    a = QgsGeometryUtils.lineAngle(point1.x(), point1.y(), point2.x(), point2.y())
    a = pi / 2 - a  # qgis is angle clockwise from north - need to adjust to be counter clockwise from horizontal
    vec = np.array([[vector[0]], [-vector[1]]])
    r = np.array([[cos(a), -sin(a)], [sin(a), cos(a)]])  # rotation matrix
    return np.dot(r, vec)[0, 0]
