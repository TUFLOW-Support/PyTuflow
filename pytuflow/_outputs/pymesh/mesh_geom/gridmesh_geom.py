import typing

import numpy as np
import pandas as pd

from . import PyMeshGeometry, GeometryLazyLoadMixin, VTKGeometryMixin
from .. import Transform2D

try:
    import pyvista as pv
except ImportError:
    from ..stubs import pyvista as pv

if typing.TYPE_CHECKING:
    from ...grid import Grid


class GridMeshGeometry(PyMeshGeometry, GeometryLazyLoadMixin, VTKGeometryMixin):

    def __init__(self, grid: 'Grid'):
        super(GridMeshGeometry, self).__init__(grid.fpath)
        self._grid = grid
        self.has_z = False
        self.vertex_reindex = None
        self.cell_reindex = None
        self._cell_pos = None
        self._data_type_ref = None
        self._weights = None
        self._loaded = False

    def load(self):
        if self._loaded:
            return

        data_types = self._grid.data_types('static')
        if 'bed elevation' in data_types or 'bed level' in data_types:
            self.has_z = True
            self._data_type_ref = 'bed elevation' if 'bed elevation' in data_types else 'bed level'
        elif data_types:
            self._data_type_ref = data_types[0]
        else:
            self._data_type_ref = self._grid.data_types()[0]

        surf = self._grid.surface(self._data_type_ref, to_vertex=True)
        cell_surf = self._grid.surface(self._data_type_ref)
        self.cell_reindex = cell_surf['active'].to_numpy()
        self._vertices = surf[['x', 'y', 'value']].to_numpy()
        inds = np.arange(surf['x'].size).reshape(self._grid.nrow + 1, self._grid.ncol + 1)
        cells = [np.concatenate((inds[i,j:j+2], inds[i+1,j+1::-1][:2])) for i in range(inds.shape[0] - 1) for j in range(inds.shape[1] - 1)]
        self._cells_df = pd.DataFrame(np.full(len(cells), 4), columns=['nnode'])
        self._cells_df[['n1', 'n2', 'n3', 'n4']] = cells

        # remove cells that are inactive and re-index
        self._cells_df = self._cells_df.loc[self.cell_reindex].reset_index(drop=True)
        self.vertex_reindex, new_indices = np.unique(self._cells_df[['n1', 'n2', 'n3', 'n4']].to_numpy().flatten(), return_inverse=True)
        self._vertices = self._vertices[self.vertex_reindex]
        self._cells_df[['n1', 'n2', 'n3', 'n4']] = new_indices.reshape(self._cells_df[['n1', 'n2', 'n3', 'n4']].shape)

        self._cell_pos = cell_surf[['x', 'y', 'value']].to_numpy()[self.cell_reindex]

        quads = self._cells_df.loc[self._cells_df['n4'] != -1, ['n1', 'n2', 'n3', 'n4']].reset_index().to_numpy()
        tris = self._cells_df.loc[self._cells_df['n4'] == -1, ['n1', 'n2', 'n3']].reset_index().to_numpy()
        self._triangles, self._cell2triangle = self.create_triangles(quads, tris)

        self._cells = self._flatten_cells(self._cells_df)

        self._global_bbox.update_extents(self._vertices)
        shift = (
            -self._global_bbox.x.min - self._global_bbox.width / 2,
            -self._global_bbox.y.min - self._global_bbox.height / 2
        )
        self._trans = Transform2D(translate=shift)
        self._local_bbox = self._global_bbox.transform(self._trans)
        self._vertices_local = np.append(
            self._trans.translate(self._vertices[:, 0:2]).astype(self.dtype),
            self._vertices[:, [2]].astype(self.dtype),
            axis=1
        )
        self._mesh = pv.PolyData(
            np.append(self._vertices_local[:, :2], np.zeros((self._vertices.shape[0], 1)), axis=1),
            self._cells
        )
        self._locator = self._build_locator(self._mesh)

        self._loaded = True

    def cell_position(self, cell_id: int | typing.Iterable[int] | slice, scope: str = 'global') -> np.ndarray:
        self.load()
        if scope == 'local':
            return self._trans.transform(self._cell_pos[cell_id])
        return self._cell_pos[cell_id]

    def cell_to_vertex_weights(self) -> np.ndarray:
        self.load()
        if self._weights is None:
            self._weights = np.full((self._cells_df.shape[0], 4), 1.)
        return self._weights
