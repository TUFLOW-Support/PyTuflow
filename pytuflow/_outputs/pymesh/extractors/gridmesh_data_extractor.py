import typing
from datetime import datetime

import numpy as np

from . import PyDataExtractor

if typing.TYPE_CHECKING:
    from ...grid import Grid


class GridMeshDataExtractor(PyDataExtractor):

    def __init__(self, grid: 'Grid'):
        super().__init__()
        self.fpath = grid.fpath
        self._grid = grid
        self.cell_reindex = None
        self.vertex_reindex = None

    def times(self, data_type: str) -> np.ndarray:
        if not self.is_static(data_type):
            return np.array(self._grid.times(data_type))
        return np.array([])

    def data_types(self) -> list[str]:
        return self._grid.data_types()

    def reference_time(self, data_type: str) -> datetime:
        return self._grid.reference_time

    def is_vector(self, data_type: str) -> bool:
        return False

    def is_static(self, data_type: str) -> bool:
        return self._grid._is_static(data_type)

    def data(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> np.ndarray:
        if self.is_static(data_type):
            data = self._grid.surface(data_type, to_vertex=True)['value'].to_numpy()
            data = data[self.vertex_reindex].flatten()
        else:
            vals = []
            for timestep in self._time_index(data_type, index):
                val = self._grid.surface(data_type, timestep, to_vertex=True)['value'].to_numpy()
                vals.append(val)
            data = np.hstack(vals).reshape(len(vals), -1)
            data = data[:, self.vertex_reindex] if data.ndim > 1 else data[self.vertex_reindex].flatten()
            index = self._time_index_leftover(index)
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
            data = data[:, self.cell_reindex] if data.ndim > 1 else data[self.cell_reindex].flatten()
            index = self._time_index_leftover(index)
        return data[index]

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

    def _time_index_leftover(self, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType:
        if isinstance(index, tuple):
            return tuple([slice(None)] + list(index[1:]))
        return slice(None)
