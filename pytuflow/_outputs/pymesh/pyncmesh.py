from pathlib import Path

import numpy as np

from . import PyMesh, PyNCMeshGeometry, PyNCMeshDataExtractor


class PyNCMesh(PyMesh):

    def __init__(self, fpath: str | Path, engine: str = None):
        super().__init__()
        self.fpath = Path(fpath)
        self.geom = PyNCMeshGeometry(fpath)
        self.extractor: PyNCMeshDataExtractor = PyNCMeshDataExtractor(fpath, engine)
        self.name = self.fpath.stem
        for dtype in self.data_types():
            if dtype.lower() != 'bed elevation':
                ref_time = self.reference_time_(dtype)
                if ref_time is not None:
                    self.has_inherent_reference_time = True
                    self.reference_time = ref_time
                break

    def translate_data_type(self, data_type: str) -> tuple[str, ...]:
        if data_type.lower() == 'v':
            return 'V_x', 'V_y'
        return super().translate_data_type(data_type)

    def on_vertex(self, data_type: str) -> bool:
        if data_type.lower() == 'bed elevation':
            return True
        dims = set([x.lower() for x in self.extractor.dimension_names(self.translate_data_type(data_type)[0])])
        return len({'numcells2d', 'numcells3d'}.intersection(dims)) == 0

    def cell_index(self, cell_id: int | list[int] | np.ndarray, data_type: str) -> int:
        return self.extractor.data('idx3', cell_id).flatten() - 1  # convert to 0-based index

    def zlevel_count(self, cell_idx2: int) -> int:
        return self.extractor.data('NL', cell_idx2).flatten()

    def zlevels(self, time_index: int, nlevels: int, cell_idx2: int, cell_idx3: int) -> np.ndarray:
        idx = cell_idx2 + cell_idx3
        if isinstance(cell_idx2, int) or cell_idx2.shape[0] == 1:
            return self.extractor.data('layerface_Z', (time_index, slice(idx, idx + nlevels + 1)))
        idx = [i + j for i, nlevel in np.column_stack((idx, nlevels)) for j in range(nlevel + 1)]
        return self.extractor.data('layerface_Z', (time_index, idx))
