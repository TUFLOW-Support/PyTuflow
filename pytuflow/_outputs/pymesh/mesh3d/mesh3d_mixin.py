import typing
from datetime import datetime

import numpy as np

from . import SceneMesh, FormatConvention

if typing.TYPE_CHECKING:
    from .. import PyMesh, Bbox2D


class Mesh3DMixin:

    def mesh3d(self,
               mesh_geometry: str,
               time: float,
               vertex_colour: list[str],
               uv_projection_extent: 'list[float] | tuple[float] | np.ndarray | Bbox2D',
               convention: FormatConvention,
               reverse_winding_order: bool,
               ) -> SceneMesh:
        """Return the mesh as a 3D SceneMesh object."""
        mesh3d = SceneMesh()
        mesh3d.inds = self.indices(reverse_winding_order)
        mesh3d.pos = self.positions(time, mesh_geometry, convention)
        mesh3d.face_counts = np.full((mesh3d.inds.count() // 3,), 3, dtype='u4')
        mesh3d.cd = self.vertex_colors(time, vertex_colour)
        mesh3d.uv = self.uvs(uv_projection_extent, convention)
        mesh3d.norms = self.normals(convention)
        return mesh3d

    def indices(self: 'PyMesh', reverse_winding_order: bool) -> np.ndarray:
        """Return the mesh triangle indices as a flat array of unsigned ints."""
        if reverse_winding_order:
            a = self.geom.triangles[:, [1, 3, 2]]
        else:
            a = self.geom.triangles[:,1:]
        return a.astype('u4').flatten()

    def positions(self: 'PyMesh',
                  time: float,
                  mesh_geometry: str,
                  convention: FormatConvention = FormatConvention.OpenGL,
                  ) -> np.ndarray:
        """Return the mesh vertex positions at time (or the time_index) as a flat array of floats."""
        pos = self.geom.vertices_local
        if mesh_geometry:
            pos -= 0.05  # avoid z-fighting
            val, mask = self.surface(mesh_geometry, time, coord_scope='local', to_vertex=True)
            if val.shape[1] == 4:  # vector - convert to magnitude
                pos[mask, 2] = np.linalg.norm(val[mask, 2:], axis=1)
            else:
                pos[mask, 2] = val[mask, 2].flatten()

        if convention in [FormatConvention.OpenGL, FormatConvention.OpenGL_2]:
            return (pos[:, [0, 2, 1]] * [1, 1, -1]).flatten().astype('f4')
        elif convention == FormatConvention.Unreal:
            return (pos[:, [1, 0, 2]] * 100.).flatten().astype('f4')
        elif convention == FormatConvention.Unity:
            return pos[:, [0, 2, 1]].flatten().astype('f4')
        else:  # Blender
            return pos.flatten().astype('f4')

    def vertex_colors(self: 'PyMesh',
                      time: float,
                      vertex_colour: list[str],
                      ) -> np.ndarray:
        """Return the mesh vertex colors at time (or the time_index) as a flat array of floats."""
        results = {}  # cache results
        colours = np.zeros((self.geom.vertices.shape[0], 3), dtype='f4')  # rgb
        if not vertex_colour:
            return colours.flatten()

        def get_data_type(data_type_name) -> tuple[str, str]:
            if data_type_name.endswith('-x'):
                data_type_name = data_type_name[:-2]
                typ = 'vecx'
            elif data_type_name.endswith('-y'):
                data_type_name = data_type_name[:-2]
                typ = 'vecy'
            else:
                typ = 'scalar'
            data_type_ = self.translate_data_type(data_type_name)[0]
            lower = [x.lower() for x in self.data_types()]
            return self.data_types()[lower.index(data_type_.lower())], typ

        def pack_data(data_type_name: str, typ: str, time: float | datetime) -> np.ndarray:
            if data_type_name not in results:
                if data_type_name == self.geom.data_type:
                    data = self.geom.vertices[:, 2]
                else:
                    data, mask = self.surface(data_type_name, time, to_vertex=True)
                    data[~mask, 2] = 0.
                    data = data[:, 2]
                data_max = self.maximum(data_type_name)
                data_min = self.minimum(data_type_name)
                results[data_type_name] = (data, data_max, data_min)
            else:
                data, data_max, data_min = results[data_type_name]
            if typ == 'scalar':
                return ((data - data_min) / (data_max - data_min)).astype('f4') if data_max > 0 else data.astype('f4')
            idx = 0 if typ == 'vecx' else 1
            return (((data[..., idx] - data_min) / (data_max - data_min)).astype('f4') + 1) / 2 if data_max > 0 else data[..., idx].astype('f4')

        for i, dtype in enumerate(vertex_colour):
            if i > colours.shape[1] - 1:
                raise ValueError('Only three data types can be used for vertex colors (R, G, B).')
            dtype_name, dtype_dtype = get_data_type(dtype)
            col = pack_data(dtype_name, dtype_dtype, time)
            colours[:, i] = col

        return colours.flatten()

    def uvs(self: 'PyMesh',
            uv_projection_extent: 'typing.Iterable[float] | Bbox2D' = (),
            convention: FormatConvention = FormatConvention.OpenGL
            ) -> np.ndarray:
        """Return the mesh vertex UVs as a flat array of floats."""
        from .. import Bbox2D

        pos = self.geom.vertices_local[:, :2]
        if ((isinstance(uv_projection_extent, np.ndarray) and uv_projection_extent.size) or
                (not isinstance(uv_projection_extent, np.ndarray) and uv_projection_extent)):
            if isinstance(uv_projection_extent, Bbox2D):
                bbox = uv_projection_extent
            else:
                pts = np.array(uv_projection_extent).reshape((-1, 2))
                bbox = Bbox2D(pts)
            bbox = bbox.transform(self.geom.trans)
        else:
            bbox = self.geom.local_bbox

        u = (pos[:, 0] - bbox.x.min) / bbox.width
        v = (pos[:, 1] - bbox.y.min) / bbox.height
        if convention == FormatConvention.OpenGL:
            v = 1 - v  # reverse v
        return np.column_stack((u.astype('f4'), v.astype('f4'))).flatten()

    def normals(self, convention: FormatConvention = FormatConvention.OpenGL) -> np.ndarray:
        if convention in [FormatConvention.Unreal, FormatConvention.Blender]:
            norm = np.array([0., 0., 1.], dtype='f4')
        else:
            norm = np.array([0., 1., 0.], dtype='f4')
        return np.repeat(norm[np.newaxis, :], self.geom.vertices.shape[0], axis=0).flatten()
