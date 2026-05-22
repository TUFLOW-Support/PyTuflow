import typing

if typing.TYPE_CHECKING:
    from . import PyMesh
    from ..helpers.mesh_driver import DatasetGroup

class SoftLoadMixin:

    def _init_soft_load(self: 'PyMesh'):
        self.valid = True

    def data_groups(self: 'PyMesh') -> typing.Generator['DatasetGroup', None, None]:
        from ..helpers.mesh_driver import DatasetGroup
        bed_level_count = 0
        with self.extractor.open():
            for dtype in self.data_types():
                if dtype.lower() == 'bed elevation' and bed_level_count == 0:
                    yield DatasetGroup(dtype, 'scalar', [0.], 1)
                    bed_level_count += 1
                    continue
                if dtype.lower() == 'bed elevation':
                    dtype = 'dynamic bed level'
                times = self.times(dtype).tolist()
                if not times:
                    times = [0.]
                type_ = 'vector' if self.is_vector(dtype) else 'scalar'
                if type_ == 'vector' and dtype.lower().endswith('_y'):
                    continue
                if type_ == 'vector' and dtype.lower().endswith('_x'):
                    dtype = dtype[:-2]
                vert_lyr_count = 2 if self.is_3d(dtype) else 1
                yield DatasetGroup(dtype, type_, times, vert_lyr_count)
