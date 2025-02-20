from datetime import datetime
from pathlib import Path
from typing import Generator

import numpy as np
import pandas as pd

from .mesh_driver import MeshDriver, DatasetGroup
from ..._pytuflow_types import TimeLike

try:
    from qgis.core import (QgsMeshDatasetIndex, QgsMesh, QgsMeshSpatialIndex, QgsPointXY, QgsInterval,
                           QgsGeometry, QgsLineString, QgsApplication, QgsMeshLayer)
    from .scalar_mesh_result import ScalarMeshResult
    from .vector_mesh_result import VectorMeshResult
    from .mesh_result import MeshResult
    from .mesh_geom import mesh_intersects, IntersectResult

    has_qgis = True
except ImportError:
    has_qgis = False
    MeshResult = 'MeshResult'
    IntersectResult = 'IntersectResult'


Point = tuple[float, float]


class QgisMeshDriver(MeshDriver):

    def __init__(self, mesh: Path):
        super().__init__(mesh)
        self.lyr = None
        self.dp = None
        self.si = None
        self.qgsmesh = None
        self.reference_time = datetime(1990, 1, 1)
        self._point_results = []
        self._linestrings = []
        self._line_results = []

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.mesh.stem}>'

    def data_groups(self) -> Generator[DatasetGroup, None, None]:
        if not self.lyr:
            raise RuntimeError('Layer not loaded.')

        for i in range(self.lyr.datasetGroupCount()):
            ind = QgsMeshDatasetIndex(i, 0)
            grp = self.lyr.datasetGroupMetadata(ind)
            name = grp.name()
            type_ = 'vector' if grp.isVector() else 'scalar'
            times = [self.lyr.datasetMetadata(QgsMeshDatasetIndex(ind.group(), i)).time() for i in range(self.lyr.datasetCount(ind))]
            yield DatasetGroup(name, type_, times)

    def init_mesh_layer(self, name: str):
        if not has_qgis:
            raise ImportError('QGIS python libraries are not installed or cannot be imported.')
        if not QgsApplication.instance():
            raise RuntimeError('QGIS application instance not found.')

        self.lyr = QgsMeshLayer(str(self.mesh), name, 'mdal')
        if not self.lyr.isValid():
            raise RuntimeError(f'Failed to load mesh layer {self.mesh}')

        self.dp = self.lyr.dataProvider()

    def load(self):
        if not has_qgis:
            raise ImportError('QGIS python libraries are not installed or cannot be imported.')

        for i in range(self.lyr.datasetGroupCount()):
            ind = QgsMeshDatasetIndex(i, 0)
            grp = self.lyr.datasetGroupMetadata(ind)
            if grp.isTemporal():
                if grp.referenceTime().isValid():
                    self.reference_time = grp.referenceTime().toPyDateTime()
                    break

    def init_spatial_index(self):
        if self.si:
            return

        if not self.lyr:
            raise RuntimeError('Layer not loaded.')

        self.qgsmesh = QgsMesh()
        self.dp.populateMesh(self.qgsmesh)
        self.si = QgsMeshSpatialIndex(self.qgsmesh)

    def group_index_from_name(self, data_type: str) -> int:
        from ..mesh import Mesh  # import here to avoid circular import
        igrp = -1
        for i in range(self.lyr.datasetGroupCount()):
            ind = QgsMeshDatasetIndex(i, 0)
            ds_name = self.lyr.datasetGroupMetadata(ind).name()
            stnd_name = Mesh._get_standard_data_type_name(ds_name)
            if stnd_name == data_type:
                igrp = i
                break

        if igrp == -1:
            raise ValueError(f'Dataset group not found for data type {data_type}')

        return igrp

    def time_series(self, name: str, point: Point, data_type: str, averaging_method: str | None = None) -> pd.DataFrame:
        from ..mesh import Mesh  # import here to avoid circular import
        self.init_spatial_index()
        igrp = self.group_index_from_name(data_type)
        stnd_name = Mesh._get_standard_data_type_name(data_type)

        res = ScalarMeshResult(self.lyr, self.qgsmesh, self.dp, self.si, QgsPointXY(*point))
        if res in self._point_results:
            res = self._point_results[self._point_results.index(res)]
        else:
            self._point_results.append(res)

        data = []
        valid = False
        for i in range(self.dp.datasetCount(igrp)):
            index = QgsMeshDatasetIndex(igrp, i)
            ds = self.dp.datasetMetadata(index)
            value = res.value(index, averaging_method)
            time = ds.time()
            data.append((time, value))
            if not np.isnan(value):
                valid = True

        if not valid:
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=['time', f'{name}/{stnd_name}'])
        df.set_index('time', inplace=True)
        return df

    def section(self, linestring: list[Point], data_type: str, time: TimeLike,
                averaging_method: str | None = None) -> pd.DataFrame:
        mesh_line = MeshLine(self, linestring, data_type, time, return_magnitude=True)
        # loop along line and get data
        data_ = []
        valid = False
        for location, mesh_result in mesh_line.results_along_line():
            # get value from mesh
            value = mesh_result.value(mesh_line.index, averaging_method)
            data_.append((location.dist1, value))
            if location.type == 'face':
                data_.append((location.dist2, value))

            # check if the returned data will have something valid in it
            if not np.isnan(value):
                valid = True

        if valid:
            df = pd.DataFrame(np.array(data_), columns=['offset', data_type])
            df.set_index('offset', inplace=True)
        else:
            df = pd.DataFrame()

        return df

    def curtain(self, linestring: list[Point], data_type: str, time: TimeLike) -> pd.DataFrame:
        mesh_line = MeshLine(self, linestring, data_type, time)
        # loop through points and extract results
        data_ = []
        valid = False
        for i, (location, mesh_result) in enumerate(mesh_line.results_along_line()):
            if location.type == 'vertex' and (i == 0 or i == len(mesh_line.intersects.intersects)):  # ignore first and last points
                continue
            order_switch = False
            for z, value in mesh_result.vertical_values(mesh_line.index, 'stepped'):
                if order_switch:
                    data_.append((location.end_side, z, value))
                    data_.append((location.start_side, z, value))
                else:
                    data_.append((location.start_side, z, value))
                    data_.append((location.end_side, z, value))

                order_switch = not order_switch

                # check if the returned data will have something valid in it
                if isinstance(value, tuple):
                    value = value[0]
                if not np.isnan(value):
                    valid = True

        data = pd.DataFrame()
        if valid:
            data = pd.DataFrame(data_, columns=['x', 'y', data_type])

        return data

    def profile(self, point: Point, data_type: str, time: TimeLike, interpolation: str) -> pd.DataFrame:
        self.init_spatial_index()

        # get dataset index based on the time
        igrp = self.group_index_from_name(data_type)
        if isinstance(time, datetime):
            reltime = (time - self.reference_time).total_seconds()
        else:
            reltime = time * 3600  # convert to seconds
        time_interval = QgsInterval(reltime)
        index = self.lyr.datasetIndexAtRelativeTime(time_interval, igrp)

        res = ScalarMeshResult(self.lyr, self.qgsmesh, self.dp, self.si, QgsPointXY(*point))
        if res in self._point_results:
            res = self._point_results[self._point_results.index(res)]
        else:
            self._point_results.append(res)

        data_ = []
        valid = False
        for z, value in res.vertical_values(index, interpolation):
            data_.append((value, z))
            if not np.isnan(value):
                valid = True

        df = pd.DataFrame()
        if valid:
            df = pd.DataFrame(data_, columns=[data_type, 'elevation'])
            df.set_index('elevation', inplace=True)

        return df


class MeshLine:
    """Class to represent extracting mesh results along a line-string. This class is used to perform
    common tasks for extracting mesh results along a line-string, such as finding the intersections and initialising
    the mesh result class.
    """

    def __init__(self, driver: QgisMeshDriver, linestring: list[Point], data_type: str, time: TimeLike,
                 return_magnitude: bool = False):
        self.driver = driver  # parent class
        self.linestring = QgsLineString([QgsPointXY(*pnt) for pnt in linestring])
        self.data_type = data_type
        self.time = time
        self.return_magnitude = return_magnitude

        self.driver.init_spatial_index()
        self.lyr = self.driver.lyr
        self.dp = self.driver.dp
        self.si = self.driver.si
        self.qgsmesh = self.driver.qgsmesh
        self.igrp = self.driver.group_index_from_name(data_type)

        # get dataset index based on the time
        if isinstance(time, datetime):
            reltime = (time - self.driver.reference_time).total_seconds()
        else:
            reltime = time * 3600  # convert to seconds
        time_interval = QgsInterval(reltime)
        self.index = self.lyr.datasetIndexAtRelativeTime(time_interval, self.igrp)
        linestring = QgsLineString([QgsPointXY(*pnt) for pnt in linestring])

        # get mesh intersections
        if linestring in self.driver._linestrings:
            self.intersects = self.driver._line_results[self.driver._linestrings.index(linestring)]
        else:
            self.intersects = mesh_intersects(self.qgsmesh, self.si, linestring)
            self.driver._linestrings.append(linestring)
            self.driver._line_results.append(self.intersects)

    def results_along_line(self) -> Generator[tuple[IntersectResult, MeshResult], None, None]:
        """Generator to yield the locations along the line-string."""
        grp = self.lyr.datasetGroupMetadata(self.index)
        for location in self.intersects.iter(self.dp.datasetGroupMetadata(self.igrp)):
            # mesh result class
            if grp.isVector() and not self.return_magnitude:
                mesh_result = VectorMeshResult(self.lyr, self.qgsmesh, self.dp, self.si, location.point)
            else:
                mesh_result = ScalarMeshResult(self.lyr, self.qgsmesh, self.dp, self.si, location.point)
            if mesh_result in self.driver._point_results:
                mesh_result = self.driver._point_results[self.driver._point_results.index(mesh_result)]
            else:
                self.driver._point_results.append(mesh_result)
            yield location, mesh_result
