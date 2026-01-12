import typing
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import PyDataExtractor

try:
    from qgis.core import QgsMeshLayer, QgsMeshDatasetIndex, QgsMeshDatasetGroupMetadata
except ImportError:
    from ..stubs.qgis.core import QgsMeshLayer, QgsMeshDatasetIndex, QgsMeshDatasetGroupMetadata


MAX_BLOCK_SIZE = 100_000


class QgisDataExtractor(PyDataExtractor):
    NAME = 'QgisDataExtractor'

    def __init__(self, mesh: str | Path, extra_datasets: list[str | Path]):
        self.lyr = QgsMeshLayer(str(mesh), Path(mesh).stem, 'mdal')
        self._3d_grp_idx = -1
        self._is_dat = False
        for dataset in extra_datasets:
            if Path(dataset).suffix.lower() == '.dat':
                self._is_dat = True
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
        data_types = [
            self.lyr.datasetGroupMetadata(QgsMeshDatasetIndex(i)).name() for i in range(self.lyr.datasetGroupCount())
            if self.lyr.datasetGroupMetadata(QgsMeshDatasetIndex(i)).name() != 'Bed Elevation'
        ]
        if self._is_dat:
            return [self.translate_dat_data_type(x) for x in data_types]
        return data_types

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
        return self._is_3d(grp_idx)

    def _is_3d(self, grp_idx: int) -> bool:
        idx = QgsMeshDatasetIndex(grp_idx)
        return self.lyr.datasetGroupMetadata(idx).dataType() == QgsMeshDatasetGroupMetadata.DataOnVolumes

    def on_vertex(self, data_type: str) -> bool:
        grp_idx = self.find_group_index(data_type)
        if grp_idx == -1:
            raise ValueError(f'Data type not found: {data_type}')
        idx = QgsMeshDatasetIndex(grp_idx)
        return self.lyr.datasetGroupMetadata(idx).dataType() == QgsMeshDatasetGroupMetadata.DataOnVertices

    def zlevel_count(self, cell_idx2: int | np.ndarray | list[int]) -> int | np.ndarray | list[int]:
        _3d_grp_idx = self._3d_dataset_index()
        if _3d_grp_idx == -1:
            return 1
        if isinstance(cell_idx2, int):
            cell_idx2 = [cell_idx2]
        elif isinstance(cell_idx2, np.ndarray):
            cell_idx2 = cell_idx2.tolist()
        result = []
        cell_idx2 = np.array(cell_idx2) if isinstance(cell_idx2, list) else cell_idx2
        for cid, count, idx in self.clump_indexes(cell_idx2):
            levels = np.array(self.lyr.dataProvider().dataset3dValues(_3d_grp_idx, cid, count).verticalLevelsCount())
            result.append(levels[idx])
        return np.array(result).flatten()

    def zlevels(self, time_index: PyDataExtractor.SliceType, nlevels: int, cell_idx2: int | np.ndarray,
                cell_idx3: int | np.ndarray) -> np.ndarray:
        _3d_grp_idx = self._3d_dataset_index()
        if _3d_grp_idx == -1:
            raise ValueError('No 3D dataset found in mesh output')
        if isinstance(cell_idx2, int):
            cell_idx2 = np.array([cell_idx2])
        elif isinstance(cell_idx2, list):
            cell_idx2 = np.array(cell_idx2)
        result = []
        time_idx = self.expand_index(time_index, max_=self.lyr.dataProvider().datasetCount(QgsMeshDatasetIndex(_3d_grp_idx)))
        sum_nlevels = np.array([nlevels]) if isinstance(nlevels, (int, np.int32, np.int64)) else np.asarray(nlevels)
        sum_nlevels = np.sum(sum_nlevels + 1)
        shape = (sum_nlevels,) if isinstance(time_index, int) else (len(time_idx), sum_nlevels)
        for time_idx in time_idx:
            for cid, count, idx in self.clump_indexes(cell_idx2):
                qgsidx = QgsMeshDatasetIndex(_3d_grp_idx.group(), time_idx)
                data_blocks = self.lyr.dataProvider().dataset3dValues(qgsidx, cid, count)
                nlevels = np.array(data_blocks.verticalLevelsCount()) + 1
                vertical_levels = np.array(data_blocks.verticalLevels())
                extracted = np.full((count, nlevels.max()), np.nan)
                k = 0
                for i in range(count):
                    levels = nlevels[i]
                    extracted[i, :levels] = vertical_levels[k:k + levels]
                    k += levels
                vals = extracted[idx].flatten()
                vals = vals[~np.isnan(vals)]
                result.append(vals)
        return np.array(result).reshape(shape)

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
        vector = self.is_vector(data_type)
        if isinstance(time_index, int):
            shape = (-1, 2) if vector else (-1,)
        elif isinstance(elem_index, (int, np.int32, np.int64)):
            shape = (-1, 2) if vector else (n,)
        else:
            shape = (n, -1, 2) if vector else (n, -1)
        values = []
        a_elem_idx = np.array(elem_idx)
        for tidx in time_idx:
            for vert_id, count, idx in self.clump_indexes(a_elem_idx):
                if self._is_3d(grp_idx):
                    data_blocks = (
                        self.lyr.dataProvider().dataset3dValues(QgsMeshDatasetIndex(grp_idx, tidx), vert_id, count)
                    )
                    nlevels = np.array(data_blocks.verticalLevelsCount())
                    values_ = np.array(data_blocks.values()).flatten()
                    if vector:
                        nlevels *= 2
                    extracted = np.full((count, nlevels.max()), np.nan)
                    k = 0
                    for i in range(count):
                        levels = nlevels[i]
                        extracted[i, :levels] = values_[k:k + levels]
                        k += levels
                else:
                    extracted = np.array(
                        self.lyr.dataProvider().datasetValues(QgsMeshDatasetIndex(grp_idx, tidx), vert_id, count).values()
                    )
                    extracted = extracted.reshape((count, -1) if vector else (count,))
                vals = extracted[idx].flatten()
                vals = vals[~np.isnan(vals)]
                values.append(vals)
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
        a_elem_array = np.array(elem_idx)
        for tidx in time_idx:
            for face_id, count, idx in self.clump_indexes(a_elem_array):
                extracted = np.array(
                    self.lyr.dataProvider().areFacesActive(QgsMeshDatasetIndex(grp_idx, tidx), face_id, count).active()
                )
                wd.append(extracted[idx].flatten())
        return np.array(wd).reshape(shape)

    def find_group_index(self, data_type: str, source: str = 'layer') -> int:
        from ...map_output import MapOutput
        data_type = MapOutput._get_standard_data_type_name(data_type)
        data_source = self.lyr if source == 'layer' else self.lyr.dataProvider()
        for i in range(data_source.datasetGroupCount()):
            group_meta = data_source.datasetGroupMetadata(QgsMeshDatasetIndex(i))
            if self._is_dat:
                name = self.translate_dat_data_type(group_meta.name())
            else:
                name = group_meta.name()
            name = MapOutput._get_standard_data_type_name(name)
            if name == data_type:
                return i
        return -1

    def expand_index(self, idx: int | slice, max_: int) -> list[int]:
        if isinstance(idx, (list, np.ndarray)):
            return idx.tolist() if isinstance(idx, np.ndarray) else idx
        elif isinstance(idx, (int, np.int32, np.int64)):
            start = idx
            end = idx + 1
        else:
            start = idx.start or 0
            end = idx.stop if isinstance(idx.stop, int) else max_
        return list(range(start, end))

    def clump_indexes(self, idx: np.ndarray) -> typing.Generator[tuple[int, int, np.ndarray], None, None]:
        i = 0
        stop = idx.size
        while i < stop:
            start = idx[i]
            end = min(idx[-1], start + MAX_BLOCK_SIZE)
            range_ = end - start + 1
            mask = np.flatnonzero(idx <= end)
            yield start, range_, idx[mask] - start
            next_ = np.flatnonzero(idx > end)
            if next_.size == 0:
                break
            i = next_[0]

    @staticmethod
    def translate_dat_data_type(data_type: str) -> str:
        from ...map_output import MapOutput
        from .dat_data_extractor import PyDATDataExtractor
        dtype, is_max, is_min = PyDATDataExtractor.strip_data_type(data_type)
        dtype, _ = dtype.split(' ', 1)
        dtype = MapOutput._get_standard_data_type_name(dtype)
        if is_max:
            return f'max {dtype}'
        elif is_min:
            return f'min {dtype}'
        else:
            return dtype

    def _3d_dataset_index(self) -> QgsMeshDatasetIndex | int:
        if self._3d_grp_idx == -1:
            for i in range(self.lyr.dataProvider().datasetGroupCount()):
                if self._is_3d(i):
                    self._3d_grp_idx = QgsMeshDatasetIndex(i, 0)
                    break
        return self._3d_grp_idx
