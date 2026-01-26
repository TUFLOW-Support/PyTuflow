import typing
from pathlib import Path

from . import PyMesh, GridMeshGeometry, GridMeshDataExtractor

if typing.TYPE_CHECKING:
    from ..grid import Grid


class PyGridMesh(PyMesh):

    def __init__(self, grid: 'str | Path | Grid', topology_ref: 'Grid | None' = None):
        super().__init__()
        if isinstance(grid, (str, Path)):
            from ..grid import Grid
            self.fpath = Path(grid)
            self._grid = Grid(self.fpath)
        else:
            self.fpath = grid.fpath
            self._grid = grid
        self.geom = GridMeshGeometry(topology_ref if topology_ref is not None else grid)
        self.extractor = GridMeshDataExtractor(grid)

    def load(self):
        super().load()
        self.extractor.cell_reindex = self.geom.cell_reindex
        self.extractor.vertex_reindex = self.geom.vertex_reindex
