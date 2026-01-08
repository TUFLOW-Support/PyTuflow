import contextlib
import typing
from pathlib import Path

import numpy as np
import pandas as pd
try:
    import pyvista as pv
except ImportError:
    from ..stubs import pyvista as pv

Dataset = None
File = None
try:
    from h5py import File
except ImportError:
    try:
        from netCDF4 import Dataset
    except ImportError:
        raise ImportError("NetCDF4 or h5py library is required to use NCMeshGeometry.")

from . import PyMeshGeometry, GeometryLazyLoadMixin, VTKGeometryMixin
from .. import proj_transformer, Transform2D


class PyNCMeshGeometry(PyMeshGeometry, GeometryLazyLoadMixin, VTKGeometryMixin):

    def __init__(self, fpath: str | Path):
        self._init_lazy_load()
        self._spherical = False
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

    def _load(self):
        with self._open() as nc:
            self._vertices = np.column_stack((
                self._data(nc, 'node_X'),
                self._data(nc, 'node_Y'),
                self._data(nc, 'node_Zb')
            ))

            self._cells_df = pd.DataFrame(
                self._data(nc, 'cell_node') - 1,
                columns=['n1', 'n2', 'n3', 'n4'],
                dtype=np.int64
            )
            self._cells_df.insert(0, 'nnode', 4)
            self._cells_df.loc[self._cells_df['n4'] == -1, 'nnode'] = 3
            self._cells = self._flatten_cells(self._cells_df)

            quads = self._cells_df.loc[self._cells_df['n4'] != -1, ['n1', 'n2', 'n3', 'n4']].reset_index().to_numpy()
            tris = self._cells_df.loc[self._cells_df['n4'] == -1, ['n1', 'n2', 'n3']].reset_index().to_numpy()
            self._triangles, self._cell2triangle = self.create_triangles(quads, tris)

            self._global_bbox.update_extents(self._vertices)

            dtype = np.float32
            if self.spherical:
                # transform object converts spherical to a local cartesian system using the proj library
                cartesian_transformer, inverse = proj_transformer(self._vertices[:, 0:2])
                self._trans = Transform2D(proj_transformer=cartesian_transformer, proj_transformer_inverse=inverse, order='P')
            else:
                self._trans = Transform2D(translate=(-self._global_bbox.x.min, -self._global_bbox.y.min))

            self._local_bbox = self._global_bbox.transform(self._trans)
            self._vertices_local = np.append(
                self._trans.transform(self._vertices[:, 0:2]).astype(dtype),
                self._vertices[:, [2]].astype(dtype),
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
            return nc[variable_name][:]
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
