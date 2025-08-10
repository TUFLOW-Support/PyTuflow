from typing import TYPE_CHECKING, Any, Union, Generator

import numpy as np
# noinspection PyUnresolvedReferences
from qgis.core import (QgsGeometry, QgsMeshDatasetGroupMetadata, QgsMesh3dAveragingMethod, QgsMeshDataBlock,
                       QgsMeshLayer, QgsMeshDatasetValue, QgsMeshMultiLevelsAveragingMethod,
                       QgsMeshSigmaAveragingMethod, QgsMeshRelativeHeightAveragingMethod,
                       QgsMeshDatasetIndex, QgsMesh3dDataBlock, QgsPointXY, QgsMesh, QgsMeshDataProvider,
                       QgsMeshSpatialIndex)

from .mesh_geom import vertex_indices_to_polygon, calculate_barycentric_weightings, closest_face_indexes
from .averaging_method import AveragingMethod

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from qgis.core import (QgsPointXY, QgsMesh, QgsMeshDataProvider, QgsMeshSpatialIndex)


class MeshResult:
    """Class for helping extract data from a mesh layer."""

    def __init__(self,
                 lyr: 'QgsMeshLayer' = None,
                 mesh: 'QgsMesh' = None,
                 dp: 'QgsMeshDataProvider' = None,
                 si: 'QgsMeshSpatialIndex' = None,
                 point: 'QgsPointXY' = None,
                 mesh_result: 'MeshResult' = None):
        if not mesh_result:
            self.lyr = lyr
            self.mesh = mesh
            self.dp = dp
            self.si = si
            self.face = None
            self.triangle = []
            self.vertex = None
            self.weightings = []
            self.point = point
            self.active = True
            self._bed_elevation = None
            self._results = {}  # keep record for fast lookup next time
        else:
            for attr in dir(mesh_result):
                if not callable(getattr(mesh_result, attr)) and not attr.startswith('__'):
                    setattr(self, attr, getattr(mesh_result, attr))

    def __repr__(self):
        return f'<MeshResult> {self.lyr.name()}-{self.point}'

    def __eq__(self, other: Any) -> bool:
        """Check the layer and point are the same."""
        if isinstance(other, MeshResult):
            return self.lyr == other.lyr and self.point is not None and self.point == other.point
        return False

    def _key(self, dataset_index: 'QgsMeshDatasetIndex', averaging_method: QgsMesh3dAveragingMethod) -> tuple[Any, ...]:
        """Returns a key for the results dictionary."""
        if self.dp.datasetGroupMetadata(dataset_index.group()).dataType() == QgsMeshDatasetGroupMetadata.DataOnVertices:
            return dataset_index.group(), dataset_index.dataset()

        method = averaging_method

        if isinstance(method, QgsMeshMultiLevelsAveragingMethod):
            string = f'multilvl_{method.startVerticalLevel()}_{method.endVerticalLevel()}_{method.countedFromTop()}'
        elif isinstance(method, QgsMeshSigmaAveragingMethod):
            string = f'sigma_{method.startFraction()}_{method.endFraction()}'
        elif isinstance(method, QgsMeshRelativeHeightAveragingMethod):
            string = f'relative_{method.startHeight()}_{method.endHeight()}_{method.countedFromTop()}'
        else:  # QgsMeshElevationAveragingMethod
            string = f'absolute_{method.startElevation()}_{method.endElevation()}'
        return dataset_index.group(), dataset_index.dataset(), string

    def _triangle_from_mesh_vertices(self, point: 'QgsPointXY', vertices: list[int]) -> list[int]:
        """
        Returns the triangle vertices.
        Input vertices are the mesh node ids that make up the quad/triangle mesh.

        The return value is the list of triangle vertex ids that the point falls in.

        Quad meshes are split into triangles and returns the triangle that the point falls in.

        The vertex ids are returned such that the first 2 vertexes are one after the other e.g. [10, 11, x].
        This means that these values can be queried at the same time from the layer
        (i.e. only requires 2 queries in total rather than 3).
        """
        triangles = []
        if len(vertices) == 4:  # quad mesh
            # split into triangles and determine which
            # triangle point falls in
            triangle1 = vertices[:3]
            ftri1 = vertex_indices_to_polygon(self.mesh, triangle1)
            geom = QgsGeometry()
            geom.fromWkb(ftri1.asWkb())
            if geom.contains(point):
                triangles = vertices[1::-1] + vertices[2:3]  # reorder so first 2 vertexes are one after the other e.g. [10, 11, x]
            else:
                triangle2 = vertices[2:] + vertices[0:1]
                ftri2 = vertex_indices_to_polygon(self.mesh, triangle2)
                geom = QgsGeometry()
                geom.fromWkb(ftri2.asWkb())
                if geom.contains(point):
                    triangles = triangle2
                else:  # check if point falls exactly on a vertex
                    return []
        elif len(vertices) == 3:
            if vertices[1] + 1 == vertices[0]:
                triangles = vertices[1::-1] + vertices[2:3]  # reorder so first 2 vertexes are one after the other e.g. [10, 11, x]
            else:
                triangles = vertices

        return triangles

    # noinspection PyTypeHints
    def _2d_vertex_values(self,
                          triangle: list[int],
                          dataset_index: 'QgsMeshDatasetIndex') -> list['QgsMeshDatasetValue']:
        """Returns values from triangle vertices as list of QgsMeshDataBlock (2d result)."""
        if triangle[0] + 1 == triangle[1] and triangle[1] + 1 == triangle[2]:  # can extract all at once
            db = self.dp.datasetValues(dataset_index, triangle[0], 3)
            data_blocks = [db.value(x) for x in range(3)]
        elif triangle[0] + 1 != triangle[1]:  # none are in order (can happen with quadtree mesh)
            data_blocks = [self.dp.datasetValue(dataset_index, triangle[0]),
                           self.dp.datasetValue(dataset_index, triangle[1]),
                           self.dp.datasetValue(dataset_index, triangle[2])]
        else:  # first 2 are in order
            db = self.dp.datasetValues(dataset_index, triangle[0], 2)
            data_blocks = [db.value(x) for x in range(2)]
            data_blocks.extend([self.dp.datasetValue(dataset_index, triangle[2])])

        return data_blocks

    # noinspection PyTypeHints
    def _value_from_weightings(self,
                               data_blocks: list['QgsMeshDatasetValue'],
                               weightings: tuple[float, float, float]) -> float:
        """Extracts the scalar value from a list of QgsMeshDataBlock and applies interpolation weightings."""
        raise NotImplementedError

    def _value_from_vertex(self, data_block: 'QgsMeshDatasetValue') -> float:
        """Returns the value from a mesh vertex."""
        raise NotImplementedError

    def _interpolate_from_mesh_vertices(self,
                                        point: 'QgsPointXY',
                                        dataset_group_index: 'QgsMeshDatasetIndex',
                                        vertices: list[int]) -> float:
        """
        Returns the interpolated value from a mesh face from the surrounding vertex values.

        The method uses the vertex ids of the mesh face the point falls within and uses barycentric interpolation
        to calculate the value. If the point falls inside a quad mesh, the quad will be split into 2 triangles.
        """
        # get triangle
        if self.vertex:  # point is on a vertex
            return self.dp.datasetValue(dataset_group_index, self.vertex)
        if not self.triangle:
            self.triangle = self._triangle_from_mesh_vertices(point, vertices)
        if not self.triangle:  # check to see if it falls exactly on one of the vertices
            for v in vertices:
                if np.isclose([self.mesh.vertex(v).x(), self.mesh.vertex(v).y()], [point.x(), point.y()]).all():
                    self.vertex = v
                    data_block = self.dp.datasetValue(dataset_group_index, self.vertex)
                    return self._value_from_vertex(data_block)
        if not self.triangle:
            return np.nan

        # get data blocks
        data_blocks = self._2d_vertex_values(self.triangle, dataset_group_index)

        # get triangle vertex weightings
        try:
            if not self.weightings:
                self.weightings = calculate_barycentric_weightings(self.mesh, self.triangle, point)
        except AssertionError:
            return np.nan

        # is_vector = self.dp.datasetGroupMetadata(dataset_group_index).isVector()

        # calculate value
        return self._value_from_weightings(data_blocks, self.weightings)

    def _value_from_mesh_face(self,
                  dataset_index: 'QgsMeshDatasetIndex',
                  face_index: int,
                  averaging_method: 'QgsMesh3dAveragingMethod') -> float:
        """
        Returns the QgsMeshXXX class from a mesh face. 2D results return
        QgsMeshDatasetValue, 3D results return QgsMeshDataBlock.
        """
        if not self.lyr.isFaceActive(dataset_index, face_index):
            return np.nan

        value = None
        if self.lyr.datasetGroupMetadata(dataset_index).maximumVerticalLevelsCount():
            dataset_3d = self.dp.dataset3dValues(dataset_index, face_index, 1)
            if dataset_3d.isValid():  # 3d result
                value = averaging_method.calculate(dataset_3d)

        if value is None:
            value = self.dp.datasetValue(dataset_index, face_index)

        return self._value_from_face_block(value)

    def _value_from_face_block(self, value_blocks: Union['QgsMeshDatasetValue', 'QgsMeshDataBlock']) -> float:
        """Returns the value from a mesh face."""
        raise NotImplementedError

    def _convert_vector_values(self, values: list[float]) -> list[float] | list[tuple[float, float]]:
        raise NotImplementedError

    def _vertical_iter(self, dataset_3d: 'QgsMesh3dDataBlock', interpolation: str) -> Generator[tuple[float, float], None, None]:
        vertical_levels = dataset_3d.verticalLevels()
        values = dataset_3d.values()
        x_, y_ = [], []
        if (len(vertical_levels) - 1) * 2 == len(values):  # vector
            values = self._convert_vector_values(values)
        if interpolation == 'stepped':
            x_ = sum([[x, x] for x in values], [])
            y_ = sum([[y, y] for y in vertical_levels], [])[1:-1]
        elif interpolation == 'linear':
            x_ = values
            y_ = [(vertical_levels[i] + x) / 2. for i, x in enumerate(vertical_levels[1:])]
        for x, y in zip(x_, y_):
            yield y, x

    def _2d_elevations(self, dataset_index: 'QgsMeshDatasetIndex') -> Generator[float, None, None]:
        yield self.result_from_name(dataset_index, ['water level', 'water surface elevation'])
        yield self.bed_elevation()

    def _get_face(self, point: 'QgsPointXY') -> int:
        """
        Work out which face the point is in and save the value
        for later use so it doesn't have to be calculated again.
        """
        if self.face is None:
            faces = closest_face_indexes([point], self.si, self.mesh)
            if faces:
                self.face = faces[0]
            else:
                self.face = -1
        return self.face

    def bed_elevation(self) -> float:
        if self._bed_elevation is not None:
            return self._bed_elevation

        if self._get_face(self.point) == -1:
            return np.nan

        if not self.triangle:
            self.triangle = self._triangle_from_mesh_vertices(self.point, self.mesh.face(self.face))

        # get triangle vertex weightings
        try:
            if not self.weightings:
                self.weightings = calculate_barycentric_weightings(self.mesh, self.triangle, self.point)
        except AssertionError:
            return np.nan

        value = 0
        for vertex, w in zip(self.triangle, self.weightings):
            point = self.mesh.vertex(vertex)  # QgsPoint
            value += point.z() * w
        self._bed_elevation = value
        return self._bed_elevation

    def result_from_name(self, dataset_index: 'QgsMeshDatasetIndex', name: list[str]) -> float:
        from .vector_mesh_result import VectorMeshResult
        from .scalar_mesh_result import ScalarMeshResult
        # find water level group
        igrp = None
        for i in range(self.dp.datasetGroupCount()):
            if self.dp.datasetGroupMetadata(i).name().lower() in [x.lower() for x in name]:
                igrp = i
                break
        if igrp is None:
            return np.nan

        index = QgsMeshDatasetIndex(igrp, dataset_index.dataset())
        if isinstance(self, VectorMeshResult) and not self.dp.datasetGroupMetadata(igrp).isVector():
            mesh_result = ScalarMeshResult(self.lyr, self.mesh, self.dp, self.si, self.point)
            return mesh_result.value(index, None)
        elif isinstance(self, ScalarMeshResult) and self.dp.datasetGroupMetadata(igrp).isVector():
            mesh_result = VectorMeshResult(self.lyr, self.mesh, self.dp, self.si, self.point)
            return mesh_result.value(index, None)
        return self.value(index, None)

    def value(self,
              dataset_index: 'QgsMeshDatasetIndex',
              averaging_method: str | None) -> float:
        """Returns the scalar value at a point for a given QgsMeshDatasetIndex (result group and timestep)."""
        avg_method = AveragingMethod(averaging_method)
        if avg_method.valid:
            avg_method = avg_method.to_qgis()
        else:
            avg_method = self.lyr.rendererSettings().averagingMethod()

        key = self._key(dataset_index, avg_method)
        if key in self._results:
            return self._results[key]

        value = None
        if self._get_face(self.point) == -1:
            self.active = False
            return np.nan

        if not self.dp.isFaceActive(dataset_index, self.face):
            return np.nan

        # if value is on vertices, interpolate using barycentric coordinates (triangle interpolation)
        if self.dp.datasetGroupMetadata(dataset_index.group()).dataType() == QgsMeshDatasetGroupMetadata.DataOnVertices:
            value = self._interpolate_from_mesh_vertices(self.point, dataset_index, self.mesh.face(self.face))

        # if value is on faces, use face value without interpolation - use averaging method if 3d
        if self.dp.datasetGroupMetadata(dataset_index.group()).dataType() in \
                [QgsMeshDatasetGroupMetadata.DataOnFaces, QgsMeshDatasetGroupMetadata.DataOnVolumes]:
            value = self._value_from_mesh_face(dataset_index, self.face, avg_method)

        self._results[key] = value
        return self._results[key]

    def vertical_values(self, dataset_index: 'QgsMeshDatasetIndex', interpolation: str) -> Generator[tuple[float, float], None, None]:
        """Yields z and value."""
        if self._get_face(self.point) == -1:
            self.active = False
            return None

        if not self.dp.isFaceActive(dataset_index, self.face):
            return None

        # if value is on vertices, then 2d result - return bed and water surface and the 2d value
        if self.dp.datasetGroupMetadata(dataset_index.group()).dataType() == QgsMeshDatasetGroupMetadata.DataOnVertices:
            value = self._interpolate_from_mesh_vertices(self.point, dataset_index, self.mesh.face(self.face))
            for z in self._2d_elevations(dataset_index):
                yield z, value
            return None

        if self.dp.datasetGroupMetadata(dataset_index.group()).dataType() in \
                [QgsMeshDatasetGroupMetadata.DataOnFaces, QgsMeshDatasetGroupMetadata.DataOnVolumes]:
            dataset_3d = self.dp.dataset3dValues(dataset_index, self.face, 1)
            if dataset_3d.isValid():  # 3d result
                for z, value in self._vertical_iter(dataset_3d, interpolation):
                    yield z, value
            else:  # 2d result
                value = self._value_from_mesh_face(dataset_index, self.face, None)
                for z in self._2d_elevations(dataset_index):
                    yield z, value
                return None
        return None
