import numpy as np
import pandas as pd
try:
    import vtk
except ImportError:
    from ..stubs import vtk
try:
    import pyvista as pv
except ImportError:
    from ..stubs import pyvista as pv

from .. import Bbox2D, Transform2D


class GeometryLazyLoadMixin:

    def _init_lazy_load(self):
        # store as private variables so the public variables can be lazy loaded
        self._vertices = np.array([])
        self._vertices_local = np.array([])
        self._cells = np.array([])
        self._cells_df = pd.DataFrame()
        self._cell2triangle = np.array([])
        self._triangles = np.array([])
        self._cell_nodes = np.array([])
        self._mesh = None
        self._global_bbox = Bbox2D()
        self._local_bbox = Bbox2D()
        self._trans = None
        self._spherical = False
        self._locator = None
        self._loaded = False

    @property
    def vertices(self) -> np.ndarray:
        if not self._loaded:
            self._load()
        return self._vertices

    @vertices.setter
    def vertices(self, verts: np.ndarray):
        self._vertices = verts
        if not self._vertices.size:
            return
        self._vertices_local = np.append(
            self._trans.translate(self._vertices[:, 0:2]).astype('f4'),
            self._vertices[:, [2]].astype('f4'),
            axis=1
        )

    @property
    def vertices_local(self) -> np.ndarray:
        if not self._loaded:
            self._load()
        return self._vertices_local

    @vertices_local.setter
    def vertices_local(self, verts: np.ndarray):
        self._vertices_local = verts

    @property
    def cells(self) -> np.ndarray:
        if not self._loaded:
            self._load()
        return self._cells

    @cells.setter
    def cells(self, cells: np.ndarray):
        self._cells = cells

    @property
    def cells_df(self) -> pd.DataFrame:
        if not self._loaded:
            self._load()
        return self._cells_df

    @cells_df.setter
    def cells_df(self, df: pd.DataFrame):
        self._cells_df = df

    @property
    def cell_nodes(self) -> np.ndarray:
        if self._cell_nodes.size == 0:
            self._cell_nodes = self.cells_df[['n1', 'n2', 'n3', 'n4']].to_numpy()
            is_tri = self._cell_nodes[:, 3] == -1
            self._cell_nodes[is_tri, 3] = self._cell_nodes[is_tri, 2]
        return self._cell_nodes

    @cell_nodes.setter
    def cell_nodes(self, cn: np.ndarray):
        self._cell_nodes = cn

    @property
    def cell2triangle(self) -> np.ndarray:
        if not self._loaded:
            self._load()
        return self._cell2triangle

    @cell2triangle.setter
    def cell2triangle(self, c2t: np.ndarray):
        self._cell2triangle = c2t

    @property
    def triangles(self) -> np.ndarray:
        if not self._loaded:
            self._load()
        return self._triangles

    @triangles.setter
    def triangles(self, tris: np.ndarray):
        self._triangles = tris

    @property
    def mesh(self) -> pv.PolyData:
        if not self._loaded:
            self._load()
        return self._mesh

    @mesh.setter
    def mesh(self, mesh: pv.PolyData):
        self._mesh = mesh

    @property
    def locator(self):
        if not self._loaded:
            self._load()
        return self._locator

    @locator.setter
    def locator(self, val: vtk.vtkStaticCellLocator):
        self._locator = val

    @property
    def global_bbox(self) -> Bbox2D:
        if not self._loaded:
            self._load()
        return self._global_bbox

    @global_bbox.setter
    def global_bbox(self, bbox: Bbox2D):
        self._global_bbox = bbox

    @property
    def local_bbox(self) -> Bbox2D:
        if not self._loaded:
            self._load()
        return self._local_bbox

    @local_bbox.setter
    def local_bbox(self, bbox: Bbox2D):
        self._local_bbox = bbox

    @property
    def trans(self) -> Transform2D:
        if not self._loaded:
            self._load()
        return self._trans

    @trans.setter
    def trans(self, val: Transform2D):
        self._trans = val

    @property
    def spherical(self) -> bool:
        return self._spherical

    @spherical.setter
    def spherical(self, val: bool):
        self._spherical = val

    def _load(self):
        pass
