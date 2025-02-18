from datetime import datetime
from pathlib import Path
from typing import Generator

import numpy as np
import pandas as pd

from .mesh_driver import MeshDriver, DatasetGroup
from ..._pytuflow_types import TimeLike

try:
    from qgis.core import (QgsMeshDatasetIndex, QgsMesh, QgsMeshSpatialIndex, QgsPointXY, QgsInterval,
                           QgsGeometry, QgsLineString)
    from .scalar_mesh_result import ScalarMeshResult
    from .mesh_geom import mesh_intersects
    has_qgis = True
except ImportError:
    has_qgis = False

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
        self.init_spatial_index()
        igrp = self.group_index_from_name(data_type)

        # get dataset index based on the time
        if isinstance(time, datetime):
            reltime = (time - self.reference_time).total_seconds()
        else:
            reltime = time * 3600  # convert to seconds
        time_interval = QgsInterval(reltime)
        index = self.lyr.datasetIndexAtRelativeTime(time_interval, igrp)
        linestring = QgsLineString([QgsPointXY(*pnt) for pnt in linestring])

        # get mesh intersections
        if linestring in self._linestrings:
            intersects = self._line_results[self._linestrings.index(linestring)]
        else:
            intersects = mesh_intersects(self.qgsmesh, self.si, linestring)
            self._linestrings.append(linestring)
            self._line_results.append(intersects)

        # loop through points and extract results
        data_ = []
        valid = False
        active = False
        start_end_locs = []
        start_loc, end_loc = None, None
        for location in intersects.iter(self.dp.datasetGroupMetadata(igrp)):
            # mesh result class
            mesh_result = ScalarMeshResult(self.lyr, self.qgsmesh, self.dp, self.si, location.point)
            if mesh_result in self._point_results:
                mesh_result = self._point_results[self._point_results.index(mesh_result)]
            else:
                self._point_results.append(mesh_result)

            # get value from mesh
            value = mesh_result.value(index, averaging_method)
            data_.append((location.dist1, value))
            if location.type == 'face':
                data_.append((location.dist2, value))

            # check if the returned data will have something valid in it
            if not np.isnan(value):
                valid = True

            # check if mesh is active so start / end locations can be determined
            if mesh_result.active and not active:
                active = True
                start_loc = location.start_side
            elif not mesh_result.active and active:
                active = False
                end_loc = location.start_side
                start_end_locs.append((start_loc, end_loc))

        # check if mesh is active at the end of the line (close it off if it is still active)
        if active:  # location should be assigned if active is True
            end_loc = location.end_side
            start_end_locs.append((start_loc, end_loc))

        if valid:
            df = pd.DataFrame(np.array(data_), columns=['offset', data_type])
            df.set_index('offset', inplace=True)
        else:
            df = pd.DataFrame()

        return df
