import contextlib
import typing
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.ma.core import masked

try:
    import pyvista as pv
except ImportError:
    from ..stubs import pyvista as pv

Dataset = None
File = None
try:
    from h5py import File
except ImportError:
    from ..stubs.h5py import File
try:
    from netCDF4 import Dataset
except ImportError:
    from ..stubs.netCDF4 import Dataset

from . import PyMeshGeometry, GeometryLazyLoadMixin, VTKGeometryMixin
from .. import proj_transformer, Transform2D


class PyNCMeshGeometry(PyMeshGeometry, GeometryLazyLoadMixin, VTKGeometryMixin):

    def __init__(self, fpath: str | Path):
        self._init_lazy_load()
        self._spherical = False
        self._cell_position = None
        self._cell_position_local = None
        self._weights = None
        super().__init__(fpath)

    @property
    def spherical(self) -> bool:
        with self._open():
            return self._spherical

    @spherical.setter
    def spherical(self, value: bool):
        self._spherical = value

    def load(self):
        if not self._loaded:
            self._load()

    def cell_position(self, cell_id: int | typing.Iterable[int] | slice, scope: str = 'global') -> np.ndarray:
        self.load()
        if self._cell_position is None:
            with self._open() as nc:
                cell_x = self._data(nc, 'cell_X')
                cell_y = self._data(nc, 'cell_Y')
                cell_z = self._data(nc, 'cell_Zb')
                self._cell_position = np.column_stack((cell_x, cell_y, cell_z))
                local_pos = self._trans.transform(self._cell_position[:, :2])
                self._cell_position_local = np.column_stack((local_pos, cell_z))
        if scope == 'global':
            return self._cell_position[cell_id]
        elif scope == 'local':
            return self._cell_position_local[cell_id]
        else:
            raise ValueError("scope must be either 'global' or 'local'")

    def cell_to_vertex_weights(self) -> np.ndarray:
        self.load()
        if self._weights is None:
            is_tri = self._cells_df['n4'].values == -1

            # Index nx, ny for each for 5 edges (4 angles)
            ii = [3, 0, 1, 2, 3, 0]
            idx = self.cell_nodes[:, ii]
            nx = self._vertices[idx, 0]
            ny = self._vertices[idx, 1]

            # For triangle cells, set last corner to be _first corner
            nx[is_tri, 4:6] = nx[is_tri, 1:3]
            ny[is_tri, 4:6] = ny[is_tri, 1:3]

            # Calculate angles
            dx = nx[:, 1:] - nx[:, :-1]
            dy = ny[:, 1:] - ny[:, :-1]
            ds = np.sqrt(dx * dx + dy * dy)

            mask = ds == 0
            if np.any(mask):
                ds[mask] = 1  # prevent division by zero

            ang = np.arccos(-(dx[:, 1:] * dx[:, 0:-1] + dy[:, 1:] * dy[:, 0:-1]) / (ds[:, 1:] * ds[:, 0:-1]))
            ang[mask[:,:4]] = 0

            # Set angle of repeated corner to 0
            ang[is_tri, 3] = 0

            # Sum angles for each node & divide by total angle
            ang_sum = np.bincount(self.cell_nodes.flatten(), weights=ang.flatten())
            self._weights = ang / ang_sum[self.cell_nodes]

        return self._weights

    def _load(self):
        with self._open() as nc:
            self._vertices = np.column_stack((
                self._data(nc, 'node_X'),
                self._data(nc, 'node_Y'),
                self._data(nc, 'node_Zb')
            ))
            if np.ma.isMaskedArray(self._vertices):
                if np.ma.is_masked(self._vertices):
                    self._vertices = self._vertices.filled(np.nan)
                else:
                    self._vertices = np.array(self._vertices)
            cell_node = self._data(nc, 'cell_node')
            if np.ma.isMaskedArray(cell_node):
                if np.ma.is_masked(cell_node):
                    cell_node = cell_node.filled(np.nan)
                else:
                    cell_node = np.array(cell_node)
            columns = ['n1', 'n2', 'n3', 'n4'] if cell_node.shape[1] == 4 else ['n1', 'n2', 'n3']

            self._cells_df = pd.DataFrame(
                cell_node - 1,
                columns=columns,
                dtype=np.int64
            )
            if len(columns) == 3:
                self._cells_df['n4'] = -1

            self._cells_df.insert(0, 'nnode', 4)
            self._cells_df.loc[self._cells_df['n4'] == -1, 'nnode'] = 3
            self._cells = self._flatten_cells(self._cells_df)

            quads = self._cells_df.loc[self._cells_df['n4'] != -1, ['n1', 'n2', 'n3', 'n4']].reset_index().to_numpy()
            tris = self._cells_df.loc[self._cells_df['n4'] == -1, ['n1', 'n2', 'n3']].reset_index().to_numpy()
            self._triangles, self._cell2triangle = self.create_triangles(quads, tris)

            self._global_bbox.update_extents(self._vertices)

            if self.spherical:
                # transform object converts spherical to a local cartesian system using the proj library
                cartesian_transformer, inverse = proj_transformer(self._vertices[:, 0:2])
                self._trans = Transform2D(proj_transformer=cartesian_transformer, proj_transformer_inverse=inverse, order='P')
            else:
                shift = (
                    -self._global_bbox.x.min - self._global_bbox.width / 2,
                    -self._global_bbox.y.min - self._global_bbox.height / 2
                )
                self._trans = Transform2D(translate=shift)

            self._local_bbox = self._global_bbox.transform(self._trans)
            self._vertices_local = np.append(
                self._trans.transform(self._vertices[:, 0:2]).astype(self.dtype),
                self._vertices[:, [2]].astype(self.dtype),
                axis=1
            )

            self._mesh = pv.PolyData(
                np.append(self._vertices_local[:, :2], np.zeros((self._vertices.shape[0], 1)), axis=1),
                self._cells
            )
            self._locator = self._build_locator(self._mesh)
            self._loaded = True

    @staticmethod
    def _data(nc: File | dict, variable_name: str) -> np.ndarray:
        if File is not None:
            a = nc[variable_name][:]
        else:
            a = nc[variable_name][:]
        if np.ma.isMaskedArray(a):
            if np.ma.is_masked(a):
                return a.filled(np.nan)
            else:
                return np.array(a)
        return a

    @contextlib.contextmanager
    def _open(self) -> typing.Generator[File | dict, None, None]:
        if Dataset is not None:
            with self._netcdf4_open() as nc:
                yield nc
        elif File is not None:
            with self._h5py_open() as h5:
                yield h5
        else:
            raise RuntimeError("Neither netCDF4 nor h5py library is available.")

    @contextlib.contextmanager
    def _netcdf4_open(self) -> typing.Generator[dict, None, None]:
        nc = None
        try:
            nc = Dataset(self.fpath, 'r')
            self._spherical = nc.spherical.lower() == 'true' if 'spherical' in nc.ncattrs() else False
            yield nc.variables
        finally:
            if nc is not None:
                nc.close()

    @contextlib.contextmanager
    def _h5py_open(self) -> typing.Generator[File, None, None]:
        h5 = None
        try:
            h5 = File(self.fpath, 'r')
            if 'spherical' in h5.attrs:
                self._spherical = h5.attrs['spherical'].decode('utf-8').lower() == 'true'
            yield h5
        finally:
            if h5 is not None:
                h5.close()
