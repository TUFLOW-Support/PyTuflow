import typing
import numpy as np

if typing.TYPE_CHECKING:
    from . import PyMesh, PyDataExtractor
    from ..helpers.mesh_driver import DatasetGroup

class SoftLoadMixin:

    def _init_soft_load(self: 'PyMesh'):
        self.valid = True

    def data_groups(self: 'PyMesh', extractor: 'PyDataExtractor' = None) -> typing.Generator['DatasetGroup', None, None]:
        from ..helpers.mesh_driver import DatasetGroup
        extractors = [extractor] if extractor is not None else self.extractors
        _ = [x.open() for x in extractors]
        try:
            for dtype in self.data_types():
                if dtype.lower() == 'bed elevation':
                    yield DatasetGroup(dtype, 'scalar', [0.], 1)
                    continue
                times = self.times(dtype).tolist()
                if (isinstance(times, np.ndarray) and not times.size) or (not isinstance(times, np.ndarray) and not times):
                    times = [0.]
                type_ = 'vector' if self.is_vector(dtype) else 'scalar'
                if type_ == 'vector' and dtype.lower().endswith('_y'):
                    continue
                if type_ == 'vector' and dtype.lower().endswith('_x'):
                    dtype = dtype[:-2]
                vert_lyr_count = 2 if self.is_3d(dtype) else 1
                yield DatasetGroup(dtype, type_, times, vert_lyr_count)
        finally:
            _ = [x.close_reader() for x in extractors]
