import typing

import numpy as np
import pandas as pd

from . import SceneMesh, FormatConvention

if typing.TYPE_CHECKING:
    from .. import PyMesh, Bbox2D


class Mesh3DMixin:

    def mesh3d(self,
               time: float = -1,
               time_index: int = -1,
               data_types: typing.Iterable[str] = ('Depth', 'Vector Velocity-x', 'Vector Velocity-y'),
               uv_projection_extent: 'typing.Iterable[float] | Bbox2D' = (),
               convention: FormatConvention = FormatConvention.OpenGL,
               reverse_winding_order: bool = False,
               ) -> SceneMesh:
        """Return the mesh as a 3D SceneMesh object."""
        mesh3d = SceneMesh()
        mesh3d.inds = self.indices(reverse_winding_order)
        mesh3d.pos = self.positions(data_types, time, time_index, convention)
        mesh3d.face_counts = np.full((mesh3d.inds.count() // 3,), 3, dtype='u4')
        mesh3d.cd = self.vertex_colors(time, time_index, data_types)
        mesh3d.uv = self.uvs(uv_projection_extent, convention)
        return mesh3d

    def indices(self: 'PyMesh', reverse_winding_order: bool) -> np.ndarray:
        """Return the mesh triangle indices as a flat array of unsigned ints."""
        if reverse_winding_order:
            a = self.geom.triangles[:, [1, 3, 2]]
        else:
            a = self.geom.triangles[:,1:]
        return a.astype('u4').flatten()

    def positions(self: 'PyMesh',
                  data_types: typing.Iterable[str] = ('Depth', 'Vector Velocity-x', 'Vector Velocity-y'),
                  time: float = -1,
                  time_index: int = -1,
                  convention: FormatConvention = FormatConvention.OpenGL,
                  ) -> np.ndarray:
        """Return the mesh vertex positions at time (or the time_index) as a flat array of floats."""
        from .. import Transform2D
        data_type = 'Bed Elevation' if time == -1 and time_index == -1 else 'Water Level'
        time_index = self._find_time_index(data_type, time) if time_index == -1 else time_index

        pos = np.array(self.geom.vertices_local)
        if data_types[0].lower() != 'bed elevation':
            z = self.extractor.data(data_type, (time_index, slice(None))).astype('f4')
            wd = self.extractor.wd_flag(data_type, (time_index, slice(None)))
            wd = self._map_wet_dry_to_verts(wd)
            z[~wd] = pos[~wd, 2]  # set dry cells to bed elevation
            pos[:, 2] = z.flatten()

        # move the origin to the centroid of the mesh bbox
        translation = np.array(self.geom.local_bbox.size) * -0.5
        trans = Transform2D(translate=translation)
        pos = trans.transform(pos)

        if convention in [FormatConvention.OpenGL, FormatConvention.OpenGL_2]:
            return (pos[:, [0, 2, 1]] * [1, 1, -1]).flatten().astype('f4')
        elif convention == FormatConvention.Unreal:
            return (pos[:, [1, 0, 2]] * 100.).flatten().astype('f4')
        elif convention == FormatConvention.Unity:
            return pos[:, [0, 2, 1]].flatten().astype('f4')
        else:  # Blender
            return pos.flatten().astype('f4')

    def vertex_colors(self: 'PyMesh',
                      time: float = -1,
                      time_index: int = -1,
                      data_types: typing.Iterable[str] = ('Depth', 'Vector Velocity-x', 'Vector Velocity-y')
                      ) -> np.ndarray:
        """Return the mesh vertex colors at time (or the time_index) as a flat array of floats."""
        results = {}  # cache results
        def get_data_type(data_type_name) -> tuple[str, str]:
            if data_type_name.endswith('-x'):
                data_type_name = data_type_name[:-2]
                typ = 'vecx'
            elif data_type_name.endswith('-y'):
                data_type_name = data_type_name[:-2]
                typ = 'vecy'
            else:
                typ = 'scalar'
            lower = [x.lower() for x in self.data_types()]
            return self.data_types()[lower.index(data_type_name.lower())], typ

        def pack_data(data_type_name: str, typ: str, time_index: int) -> np.ndarray:
            if data_type_name not in results:
                data = self.extractor.data(data_type_name, (time_index, slice(None)))
                data_max = self.maximum(data_type_name)
                results[data_type_name] = (data, data_max)
            else:
                data, data_max = results[data_type_name]
            if typ == 'scalar':
                return (data / data_max).astype('f4') if data_max > 0 else data.astype('f4')
            idx = 0 if typ == 'vecx' else 1
            return ((data[..., idx] / data_max).astype('f4') + 1) / 2 if data_max > 0 else data[..., idx].astype('f4')

        if data_types and data_types[0].lower() == 'bed elevation':  # return only the 2dm height in the red channel
            a = np.zeros((self.geom.vertices.shape[0], 3), dtype='f4')
            zmin, zmax = self.geom.vertices[...,2].min(), self.geom.vertices[...,2].max()
            z = (self.geom.vertices[...,2] - zmin) / (zmax - zmin) if (zmax - zmin) > 0 else self.geom.vertices[...,2]
            a[:, 0] = z.astype('f4')
            return a.flatten()

        time_index = self._find_time_index(data_types[0], time) if time_index == -1 else time_index

        red_type, typ = get_data_type(data_types[0])
        red = pack_data(red_type, typ, time_index)
        blue_type, typ = get_data_type(data_types[1])
        blue = pack_data(blue_type, typ, time_index)
        green_type, typ = get_data_type(data_types[2])
        green = pack_data(green_type, typ, time_index)

        return np.column_stack((red.reshape(-1, 1), blue.reshape(-1, 1), green.reshape(-1, 1))).flatten()

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
