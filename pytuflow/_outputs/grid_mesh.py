import typing

from .mesh import Mesh
from .._pytuflow_types import PathLike
from .pymesh import PyGridMesh

if typing.TYPE_CHECKING:
    from .grid import Grid


class GridMesh(Mesh):

    def __init__(self, fpath: PathLike, grid: 'Grid | None' = None, base_topology: 'Grid | None' = None):
        super().__init__(fpath)
        if grid is None:
            from .grid import Grid
            self._grid = Grid(fpath)
        else:
            self._grid = grid
        self._driver = PyGridMesh(self._grid, base_topology)
        self._soft_load_driver = self._driver
        self._initial_load()

    def _initial_load(self):
        self.name = self._grid.name
        self._info = self._grid._info.copy()
        self._info['data_type'] = self._driver.data_types()
        mask = self._info['data_type'].str.contains('vector ')
        self._info.loc[mask, 'type'] = 'vector'
