import typing
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import PyDataExtractor

try:
    from qgis.core import QgsMeshLayer, QgsMeshDatasetIndex
except ImportError:
    from ..stubs.qgis.core import QgsMeshLayer, QgsMeshDatasetIndex


class QgisDataExtractor(PyDataExtractor):
    Name = 'QgisDataExtractor'

    def __init__(self, mesh: str | Path, extra_datasets: list[str | Path]):
        self.lyr = QgsMeshLayer(str(mesh), Path(mesh).stem, 'mdal')
        for dataset in extra_datasets:
            success = self.lyr.dataProvider().addDataset(str(dataset))
            if not success:
                raise ValueError(f'Failed to load results onto mesh: {dataset}')

    def times(self, data_type: str) -> np.ndarray:
        grp_idx = self.find_group_index(data_type)
        if grp_idx == -1:
            raise ValueError(f'Data type not found: {data_type}')
        idx = QgsMeshDatasetIndex(grp_idx)
        return np.array([
            self.lyr.datasetMetadata(QgsMeshDatasetIndex(grp_idx, x)).time() for x in range(self.lyr.datasetCount(idx))
        ])

    def data_types(self) -> list[str]:
        return [
            self.lyr.datasetGroupMetadata(QgsMeshDatasetIndex(i)).name() for i in range(self.lyr.datasetGroupCount())
            if self.lyr.datasetGroupMetadata(QgsMeshDatasetIndex(i)).name() != 'Bed Elevation'
        ]

    def reference_time(self, data_type: str) -> datetime:
        grp_idx = self.find_group_index(data_type)
        if grp_idx == -1:
            raise ValueError(f'Data type not found: {data_type}')
        idx = QgsMeshDatasetIndex(grp_idx)
        ref_time = self.lyr.datasetGroupMetadata(idx).referenceTime()
        if ref_time and ref_time.isValid():
            ref_time = ref_time.toPyDateTime()
            return ref_time.replace(tzinfo=timezone.utc)

    def is_vector(self, data_type: str) -> bool:
        grp_idx = self.find_group_index(data_type)
        if grp_idx == -1:
            raise ValueError(f'Data type not found: {data_type}')
        idx = QgsMeshDatasetIndex(grp_idx)
        return self.lyr.datasetGroupMetadata(idx).isVector()

    def is_static(self, data_type: str) -> bool:
        return self.times(data_type).size <= 1

    def is_3d(self, data_type: str) -> bool:
        grp_idx = self.find_group_index(data_type)
        if grp_idx == -1:
            raise ValueError(f'Data type not found: {data_type}')
        idx = QgsMeshDatasetIndex(grp_idx)
        return self.lyr.datasetGroupMetadata(idx).maximumVerticalLevelsCount() > 1

    def maximum(self, data_type: str) -> float:
        idx = self.find_group_index(data_type)
        if idx == -1:
            raise ValueError(f'Data type {data_type} not found in mesh output {self.mesh.stem}')
        return self.lyr.datasetGroupMetadata(QgsMeshDatasetIndex(idx)).maximum()

    def minimum(self, data_type: str) -> float:
        idx = self.find_group_index(data_type)
        if idx == -1:
            raise ValueError(f'Data type {data_type} not found in mesh output {self.mesh.stem}')
        return self.lyr.datasetGroupMetadata(QgsMeshDatasetIndex(idx)).minimum()

    def data(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> np.ndarray:
        if isinstance(index, tuple) and len(index) == 2:
            time_index, elem_index = index
        else:
            time_index = index
            elem_index = slice(None)
        grp_idx = self.find_group_index(data_type, 'dataProvider')
        if grp_idx == -1:
            raise ValueError(f'Data type not found: {data_type}')
        time_idx = self.expand_index(time_index, max_=self.lyr.dataProvider().datasetCount(QgsMeshDatasetIndex(grp_idx)))
        elem_idx = self.expand_index(elem_index, max_=self.lyr.dataProvider().vertexCount())
        n, m = len(time_idx), len(elem_idx)
        if isinstance(time_index, int):
            shape = (m, 2) if self.is_vector(data_type) else (m,)
        else:
            shape = (n, m, 2) if self.is_vector(data_type) else (n, m)
        values = []
        for tidx in time_idx:
            for vert_id, count in self.clump_indexes(elem_idx.copy()):
                values.extend(
                    self.lyr.dataProvider().datasetValues(QgsMeshDatasetIndex(grp_idx, tidx), vert_id, count).values()
                )
        return np.array(values).reshape(shape)

    def wd_flag(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> np.ndarray:
        if isinstance(index, tuple) and len(index) == 2:
            time_index, elem_index = index
        else:
            time_index = index
            elem_index = slice(None)
        grp_idx = self.find_group_index(data_type, 'dataProvider')
        if grp_idx == -1:
            raise ValueError(f'Data type not found: {data_type}')
        time_idx = self.expand_index(time_index, max_=self.lyr.dataProvider().datasetCount(QgsMeshDatasetIndex(grp_idx)))
        elem_idx = self.expand_index(elem_index, max_=self.lyr.dataProvider().faceCount())
        n, m = len(time_idx), len(elem_idx)
        shape = (m,) if isinstance(time_index, int) else (n, m)
        wd = []
        for tidx in time_idx:
            wd.extend([
                self.lyr.dataProvider().isFaceActive(QgsMeshDatasetIndex(grp_idx, tidx), x) for x in elem_idx
            ])
        return np.array(wd).reshape(shape)

    def find_group_index(self, data_type: str, source: str = 'layer') -> int:
        from ...map_output import MapOutput
        data_type = MapOutput._get_standard_data_type_name(data_type)
        data_source = self.lyr if source == 'layer' else self.lyr.dataProvider()
        for i in range(data_source.datasetGroupCount()):
            group_meta = data_source.datasetGroupMetadata(QgsMeshDatasetIndex(i))
            name = MapOutput._get_standard_data_type_name(group_meta.name())
            if name == data_type:
                return i
        return -1

    def expand_index(self, idx: int | slice, max_: int) -> list[int]:
        if isinstance(idx, (list, np.ndarray)):
            return idx.tolist() if isinstance(idx, np.ndarray) else idx
        elif isinstance(idx, int):
            start = idx
            end = idx + 1
        else:
            start = idx.start or 0
            end = idx.stop if isinstance(idx.stop, int) else max_
        return list(range(start, end))

    def clump_indexes(self, idxs: list[int]) -> typing.Generator[tuple[int, int], None, None]:
        while idxs:
            idx = idxs.pop(0)
            count = 1
            while idxs and idxs[0] == idx + count:
                count += 1
                idxs.pop(0)
            yield idx, count
