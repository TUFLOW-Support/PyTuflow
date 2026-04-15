import typing
from datetime import datetime

import numpy as np

from . import PyDataExtractor

if typing.TYPE_CHECKING:
    from ...grid import Grid


class GridMeshDataExtractor(PyDataExtractor):

    def __init__(self, grid: 'Grid', direction_convention: str):
        super().__init__()
        self.direction_convention = direction_convention
        self.fpath = grid.fpath
        self._grid = grid
        self.cell_reindex = None
        self.vertex_reindex = None

    def times(self, data_type: str) -> np.ndarray:
        if not self.is_static(data_type):
            return np.array(self._grid.times(data_type))
        return np.array([])

    def data_types(self) -> list[str]:
        data_types = []
        for dtype in self._grid.data_types():
            if dtype.endswith(' direction'):
                dtype, _ = dtype.rsplit(' ', 1)
                prefix = ''
                if dtype.startswith('max '):
                    dtype = dtype[4:]
                    prefix = 'max '
                elif dtype.startswith('min '):
                    dtype = dtype[4:]
                    prefix = 'min '
                dtype = f'{prefix}vector {dtype}'
            data_types.append(dtype)
        return data_types

    def reference_time(self, data_type: str) -> datetime:
        return self._grid.reference_time

    def is_vector(self, data_type: str) -> bool:
        return data_type.endswith(' direction')

    def is_static(self, data_type: str) -> bool:
        return self._grid._is_static(data_type)

    def on_vertex(self, data_type: str) -> bool:
        return False

    def data(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> np.ndarray:
        if self.is_static(data_type):
            if self.is_vector(data_type):
                data = self._grid.surface(
                    data_type, direction_to_vector=True, direction_convention=self.direction_convention
                    )[['value-x', 'value-y']].to_numpy()
                data = data[self.cell_reindex].reshape(-1, 1, 2)
            else:
                data = self._grid.surface(data_type)['value'].to_numpy()
                data = data[self.cell_reindex].flatten()
        else:
            vals = []
            for timestep in self._time_index(data_type, index):
                if self.is_vector(data_type):
                    val = self._grid.surface(
                        data_type, timestep, direction_to_vector=True, direction_convention=self.direction_convention
                        )[['value-x', 'value-y']].to_numpy()
                else:
                    val = self._grid.surface(data_type, timestep)['value'].to_numpy()
                vals.append(val)
            if self.is_vector(data_type):
                data = np.stack(vals, axis=0)                    # (T, n_grid, 2)
                data = data[:, self.cell_reindex, :]
            else:
                data = np.hstack(vals).reshape(len(vals), -1)
                data = data[:, self.cell_reindex]
            if not self._is_multi_time_index(index) and not self.is_vector(data_type):
                data = data.flatten()
            index = self._time_index_leftover(index, self.is_vector(data_type))
        return data[index]

    def wd_flag(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> np.ndarray:
        if self.is_static(data_type):
            data = self._grid.surface(data_type)['active'].to_numpy()
            data = data[self.cell_reindex].flatten()
        else:
            vals = []
            for timestep in self._time_index(data_type, index):
                val = self._grid.surface(data_type, timestep)['active'].to_numpy()
                vals.append(val)
            data = np.hstack(vals).reshape(len(vals), -1)
            data = data[:, self.cell_reindex]
            if not self._is_multi_time_index(index):
                data = data.flatten()
            index = self._time_index_leftover(index, False)
        return data[index]

    def zlevel_count(self, cell_idx2: int | np.ndarray | list[int]) -> int | np.ndarray | list[int]:
        if isinstance(cell_idx2, (int, np.int32, np.int64)):
            return np.array([0])
        return np.full(len(cell_idx2), 0)

    def _time_index(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> list[int]:
        times = self.times(data_type)
        if isinstance(index, (int, np.int32, np.int64)):
            return times[index:index+1].tolist()
        elif isinstance(index, slice):
            return times[index].tolist()
        elif isinstance(index, tuple):
            if isinstance(index[0], (int, np.int32, np.int64)):
                return times[index[0]:index[0]+1].tolist()
            elif isinstance(index[0], slice):
                return times[index[0]].tolist()
        return times[index].tolist()

    def _is_multi_time_index(self, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> bool:
        if isinstance(index, (int, np.int32, np.int64)):
            return False
        elif isinstance(index, slice):
            return True
        elif isinstance(index, tuple):
            if isinstance(index[0], (int, np.int32, np.int64)):
                return False
        return True

    def _time_index_leftover(self,
                             index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType,
                             is_vector: bool
                             ) -> PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType:
        if isinstance(index, tuple):
            if self._is_multi_time_index(index) or is_vector:
                return tuple([slice(None)] + list(index[1:]))
            return tuple(index[1:])
        return slice(None)
