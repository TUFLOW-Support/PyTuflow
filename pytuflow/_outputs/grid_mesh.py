import typing

from .mesh import Mesh
from .._pytuflow_types import PathLike
from .pymesh import PyGridMesh

if typing.TYPE_CHECKING:
    from .grid import Grid


class GridMesh(Mesh):
    """Class for loading Grid datasets into a mesh structure. This has no notable advantages over using the
    :class:`Grid<pytuflow.Grid>` class, other than providing some additional export functionality inherited from the
    :class:`Mesh<pytuflow.Mesh>` class.

    It's possible to convert to a ``GridMesh`` from the :class:`Grid<pytuflow.Grid>`
    class by using the :meth:`Grid.to_mesh()<pytuflow.Grid.to_mesh()>` method.

    Parameters
    ----------
    fpath : PathLike
        Path to the Grid dataset file.
    grid : Grid, optional
        An existing Grid object. If not provided, a new Grid object will be created from the ``fpath`` parameter.
        This parameter takes precedence over the ``fpath`` parameter.
    base_topology : Grid, optional
        An optional base topology Grid object to define the mesh structure. The :class:`Grid<pytuflow.Grid>` should
        match the dimensions and extent of the dataset being loaded. Typically only required when working with datasets
        that are temporal or contain multiple data types.

    Examples
    --------
    >>> from pytuflow import GridMesh
    >>> mesh = GridMesh('/path/to/results/grid/Model_Max_h.tif')
    """

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

    def curtain(self, *args, **kwargs):
        """no-doc"""
        super().curtain(*args, **kwargs)

    def profile(self, *args, **kwargs):
        """no-doc"""
        super().profile(*args, **kwargs)
