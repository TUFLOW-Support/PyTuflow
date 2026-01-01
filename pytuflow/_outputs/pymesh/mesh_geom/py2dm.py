import re
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import pyvista as pv
except ImportError:
    from ..stubs import pyvista as pv
try:
    import geopandas as gpd
except ImportError:
    gpd = None

from . import GeometryLazyLoadMixin, VTKGeometryMixin, PyMeshGeometry
from .. import Bbox2D, Transform2D


class Py2dm(PyMeshGeometry, GeometryLazyLoadMixin, VTKGeometryMixin):

    def __init__(self, fpath: Path | str):
        self._init_lazy_load()
        super().__init__(fpath)
        self.has_z = True
        #: bool: True if 2dm file was written by TUFLOW Classic/HPC which contains additional header information
        self.tuflow_fixed_grid = False
        #: float: The x-coordinate of the origin.
        self.ox = -999
        #: float: The y-coordinate of the origin.
        self.oy = -999
        #: int: The number of rows in the model domain.
        self.nrow = 0
        #: int: The number of columns in the model domain.
        self.ncol = 0
        #: float: The width of the model domain.
        self.width = 0.
        #: float: The height of the model domain.
        self.height = 0.
        #: float: The cell size in the x-direction.
        self.dx = 0.
        #: float: The cell size in the y-direction.
        self.dy = 0.
        #: float: The angle of rotation of the model domain.
        self.angle = 0.

        self._soft_load()
        self._loaded = False

    def load(self):
        if not self._loaded:
            self._load()

    @staticmethod
    def read_2dm_file(fpath: Path) -> pd.DataFrame:
        """Reads the .2dm file into a dataframe with the first two rows skipped and the column names
        starting at "A".

        Parameters
        ----------
        fpath : Path
            The path to the .2dm file.

        Returns
        -------
        pd.DataFrame
            The dataframe containing the .2dm file data.
        """
        return pd.read_csv(fpath, skiprows=2, sep=r'\s+', names=[chr(x) for x in range(ord('A'), ord('A') + 11)])

    @staticmethod
    def load_nodes(df: pd.DataFrame) -> np.ndarray:
        """Loads the nodes from the raw 2dm dataframe.

        Parameters
        ----------
        df : pd.DataFrame
            The raw 2dm dataframe.

        Returns
        -------
        np.ndarray
            The nodes array.
        """
        nds = df[df['A'] == 'ND'][['B', 'C', 'D', 'E']].rename(columns={'B': 'ind', 'C': 'x', 'D': 'y', 'E': 'z'})
        uses_fortran_indexing = nds['ind'].min() == 1
        if uses_fortran_indexing:
            nds['ind'] -= 1
        nds.set_index('ind', inplace=True)
        return nds.to_numpy('f8')

    @staticmethod
    def load_cells(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Loads the cells/primitives from the raw 2dm dataframe.

        Parameters
        ----------
        df : pd.DataFrame
            The raw 2dm dataframe.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            The quads and triangles cell arrays.
        """
        fortran_indexing = df[df['A'] == 'ND']['B'].min() == 1

        quads = df[df['A'] == 'E4Q'][['B', 'C', 'D', 'E', 'F']].rename(
            columns={'B': 'ind', 'C': 'n1', 'D': 'n2', 'E': 'n3', 'F': 'n4'})
        if not quads.empty:
            quads[['ind', 'n1', 'n2', 'n3', 'n4']] = quads[['ind', 'n1', 'n2', 'n3', 'n4']].astype(int)
            if fortran_indexing:
                quads[['ind', 'n1', 'n2', 'n3', 'n4']] = quads[['ind', 'n1', 'n2', 'n3', 'n4']] - 1
            quads.set_index('ind', inplace=True)

        tris = df[df['A'] == 'E3T'][['B', 'C', 'D', 'E', 'F']].rename(
            columns={'B': 'ind', 'C': 'n1', 'D': 'n2', 'E': 'n3'})
        tris[['ind', 'n1', 'n2', 'n3']] = tris[['ind', 'n1', 'n2', 'n3']].astype(int)
        if fortran_indexing:
            tris[['ind', 'n1', 'n2', 'n3']] = tris[['ind', 'n1', 'n2', 'n3']] - 1
            tris = tris.set_index('ind').drop(columns=['F'])

        return quads.reset_index().to_numpy(dtype='i8'), tris.reset_index().to_numpy(dtype='i8')

    def tuflow_grid_bbox(self, output_cell_size: float) -> Bbox2D:
        # only supports TUFLOW Classic/HPC and only if "Grid Output Origin == Origin" (which is not the default)
        if not self.tuflow_fixed_grid:
            raise NotImplemented('tuflow_grid_bbox is only supported for tuflow fixed grid models.')
        pts = pd.DataFrame({'x': [self.ox, self.ox + self.ncol * self.dx], 'y': [self.oy, self.oy + self.nrow * self.dy]})
        bbox = Bbox2D(pts)
        trans = Transform2D(translate=[-self.ox, -self.oy], rotate=self.angle)
        bbox = bbox.transform(trans, order='TR')
        bbox.x.max = int(round((bbox.x.max - bbox.x.min) / output_cell_size)) * output_cell_size + bbox.x.min
        bbox.y.max = int(round((bbox.y.max - bbox.y.min) / output_cell_size)) * output_cell_size + bbox.y.min
        return bbox

    def _soft_load(self):
        """Loads header information from the 2dm file. Typically this info is only written by TUFLOW Classic/HPC."""
        with self.fpath.open() as f:
            data = re.split(r'\s+', f.readline())
            if len(data) > 1 and data[1].strip():
                self.ox = float(data[1])
            if len(data) > 2 and data[2].strip():
                self.oy = float(data[2])
            if len(data) > 3 and data[3].strip():
                self.angle = float(data[3])
            if len(data) > 4 and data[4].strip():
                self.nrow = int(data[4])
            if len(data) > 5 and data[5].strip():
                self.ncol = int(data[5])
            if len(data) > 6 and data[6].strip():
                self.dx = float(data[6])
            if len(data) > 7 and data[7].strip():
                self.tuflow_fixed_grid = True
                self.dy = float(data[7])
            if self.tuflow_fixed_grid:
                self.width = self.ncol * self.dx
                self.height = self.nrow * self.dy
                self._start_radius = self.dx / 2 * 1.2

    def _load(self):
        """Loads and processes the 2dm file: loads nodes, quads, triangles, and converts to local coordinates."""
        df = self.read_2dm_file(self.fpath)
        self._vertices = self.load_nodes(df)
        quads, tris = self.load_cells(df)

        df_quads = pd.DataFrame(quads, columns=['cell_id', 'n1', 'n2', 'n3', 'n4'])
        df_quads.insert(0, 'nnode', 4)

        df_tris = pd.DataFrame(tris, columns=['cell_id', 'n1', 'n2', 'n3'])
        df_tris['n4'] = -1
        df_tris.insert(0, 'nnode', 3)

        self._cells_df = (
            pd.concat([df_quads, df_tris])
            .set_index('cell_id')
            .sort_index()
        )

        self._cells = self._flatten_cells(self._cells_df)

        self._triangles, self._cell2triangle = self.create_triangles(quads, tris)  # everything as a triangle

        self._global_bbox.update_extents(self._vertices)
        self._trans = Transform2D(translate=(-self._global_bbox.x.min, -self._global_bbox.y.min))
        self._local_bbox = self._global_bbox.transform(self._trans)
        self._vertices_local = np.append(
            self._trans.translate(self._vertices[:, 0:2]).astype('f4'),
            self._vertices[:,[2]].astype('f4'),
            axis=1
        )
        self._mesh = pv.PolyData(
            np.append(self._vertices_local[:, :2], np.zeros((self._vertices.shape[0], 1)), axis=1),
            self._cells
        )
        self._loaded = True
