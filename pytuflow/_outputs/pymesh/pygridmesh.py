import typing
from pathlib import Path

from . import PyMesh, GridMeshGeometry, GridMeshDataExtractor
from .mesh3d import Mesh3DMixin, GLTFMixin

if typing.TYPE_CHECKING:
    from ..grid import Grid


class PyGridMesh(PyMesh, Mesh3DMixin, GLTFMixin):

    def __init__(self, grid: 'str | Path | Grid', topology_ref: 'Grid | None' = None, direction_convention = 'arithmetic'):
        super().__init__()
        if isinstance(grid, (str, Path)):
            from ..grid import Grid
            self.fpath = Path(grid)
            self._grid = Grid(self.fpath)
        else:
            self.fpath = grid.fpath
            self._grid = grid
        self.geom = GridMeshGeometry(topology_ref if topology_ref is not None else grid)
        self.extractors = [GridMeshDataExtractor(grid, direction_convention)]

    def load(self):
        super().load()
        self.extractors[0].cell_reindex = self.geom.cell_reindex
        self.extractors[0].vertex_reindex = self.geom.vertex_reindex

    def translate_data_type(self, data_type: str) -> tuple[str, ...]:
        # For scalar magnitude types that have a "vector X" counterpart, redirect
        # to the vector form so the extractor returns (T, n, 2) arrays.
        if 'vector ' not in data_type and not data_type.endswith(' direction'):
            _ = self.data_types()  # ensure _standardised_data_types is populated
            prefix = ''
            base = data_type
            for pfx in ('max ', 'min '):
                if base.startswith(pfx):
                    prefix, base = pfx, base[len(pfx):]
                    break
            vector_form = f'{prefix}vector {base}'
            if vector_form in self._standardised_data_types:
                data_type = vector_form
        if 'vector ' in data_type:
            dtype = data_type.replace('vector ', '')
            prefix = ''
            if dtype.startswith('max '):
                dtype = dtype[4:]
                prefix = 'max '
            elif dtype.startswith('min '):
                dtype = dtype[4:]
                prefix = 'min '
            data_type = f'{prefix}{dtype} direction'
        return super().translate_data_type(data_type)
