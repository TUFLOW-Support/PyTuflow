from datetime import datetime
from pathlib import Path
from typing import Generator

import numpy as np
import pandas as pd

from .mesh_driver import MeshDriver, DatasetGroup
from ..output import Output

try:
    from qgis.core import QgsMeshDatasetIndex, QgsMesh, QgsMeshSpatialIndex, QgsPointXY
    from .scalar_mesh_result import ScalarMeshResult
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

    def time_series(self, name: str, point: Point, data_type: str, averaging_method: str | None = None) -> pd.DataFrame:
        self.init_spatial_index()
        igrp = -1
        for i in range(self.lyr.datasetGroupCount()):
            ind = QgsMeshDatasetIndex(i, 0)
            ds_name = self.lyr.datasetGroupMetadata(ind).name()
            stnd_name = Output._get_standard_data_type_name(ds_name)
            if stnd_name == data_type:
                igrp = i
                break

        if igrp == -1:
            raise ValueError(f'Dataset group not found for data type {data_type}')

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

        return pd.DataFrame(data, columns=['time', f'{name}/{stnd_name}']) if valid else pd.DataFrame()
