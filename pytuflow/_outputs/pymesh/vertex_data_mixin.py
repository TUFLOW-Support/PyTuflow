import typing

import numpy as np

from . import barycentric_coord, PointLike

if typing.TYPE_CHECKING:
    from . import PyMesh


class VertexDataMixin:

    def data_point_from_vertex_data(self: 'PyMesh',
                                    point: np.ndarray,
                                    data_type: str,
                                    time_index: int,
                                    return_type: str
                                    ) -> float | tuple[float, float]:
        """Returns the interpolated data value from mesh vertices at the given point."""
        tri = self.geom.find_containing_triangle(point, 'local')
        if tri == -1:
            raise ValueError('Point falls outside mesh.')

        cell_id = self.geom.triangle_cell(tri)

        if data_type.lower() != 'bed elevation':
            wd_flag = self.extractor.wd_flag(data_type, (time_index, cell_id)).flatten().astype(bool)[0]
            if not wd_flag:
                return np.nan

        vert_ids, inverse = np.unique(self.geom.triangle_vertices(tri), return_inverse=True)

        # calculate interpolation weights
        uvw = self.geom.barycentric_factors(point, tri, scope='local')

        if data_type.lower() == 'bed elevation':
            pos = self.geom.vertex_position(vert_ids)[inverse]
            a = pos[:, 2].reshape((1, 3))
        else:
            a = self.extractor.data(data_type, (time_index, vert_ids))[inverse]

        if self.is_vector(data_type) and return_type == 'vector':
            data_x = (a[..., 0] * uvw).sum(axis=1)
            data_y = (a[..., 1] * uvw).sum(axis=1)
            data_point = (float(data_x[0]), float(data_y[0]))
        elif self.is_vector(data_type):
            mag = np.linalg.norm(a, axis=1).reshape(-1, 3)
            data_point = float((mag * uvw).sum(axis=1)[0])
        else:
            data_point = float((a * uvw).sum(axis=1)[0])

        return data_point

    def time_series_from_vertex_data(self: 'PyMesh',
                                     point: np.ndarray,
                                     data_type: str,
                                     return_type: str,
                                     ) -> np.ndarray:
        """Timeseries call to get data from vertices at a given point."""
        tri = self.geom.find_containing_triangle(point, 'local')
        if tri == -1:
            raise ValueError('Point falls outside mesh.')

        # calculate interpolation weights
        uvw = self.geom.barycentric_factors(point, tri, scope='local')

        # calculate the values
        vert_ids, inverse = np.unique(self.geom.triangle_vertices(tri), return_inverse=True)
        a = self.extractor.data(data_type, (slice(None), vert_ids))[:,inverse]

        vector = self.is_vector(data_type)
        if vector and return_type == 'vector':
            data_x = (a[..., 0] * uvw).sum(axis=1)
            data_y = (a[..., 1] * uvw).sum(axis=1)
            data = np.concatenate((data_x.reshape((-1, 1, 1)), data_y.reshape((-1, 1, 1))), axis=2)
        elif vector:
            mag = np.linalg.norm(a, axis=2)
            data = (mag * uvw).sum(axis=1).reshape(-1, 1)
        else:
            data = (a * uvw).sum(axis=1)

        # wd flag
        cell_id = self.geom.triangle_cell(tri)
        wd_flag = self.extractor.wd_flag(data_type, (slice(None), cell_id)).flatten().astype(bool)
        data[~wd_flag, ...] = np.nan

        return data

    def section_from_vertex_data(
            self: 'PyMesh',
            cell_ids: np.ndarray,
            points: np.ndarray,
            data_type: str,
            time_index: int,
            return_type: str,
    ) -> np.ndarray:
        """Extract data along a section defined by a linestring from mesh vertices."""
        # results on vertices - use mid-points
        # get vertices of triangle that mid-point falls within
        verts = np.empty((len(cell_ids), 3), dtype='i8')
        for i, (cell_id, mid) in enumerate(zip(cell_ids, points)):
            if cell_id == -1:
                verts[i, ...] = -1
                continue
            tri = self.geom.find_containing_triangle(mid[1:], scope='local', cell_id=cell_id)
            if tri == -1:
                verts[i, ...] = -1
            else:
                verts[i, ...] = self.geom.triangle_vertices(tri)
        # unique vertices
        uvert, inverse = np.unique(verts.flatten(), return_inverse=True)
        # if -1 exists, it will always be first since the unique routine sorts
        outside = uvert[0] == -1
        if outside:
            uvert = uvert[1:]

        # extract data and then remap back to original verts
        vector = self.is_vector(data_type)
        if data_type.lower() == 'bed elevation':
            data = self.geom.vertex_position(uvert)[..., 2]
        else:
            data = self.extractor.data(data_type, (time_index, uvert))
        if outside:
            data = np.append([[np.nan, np.nan]] if vector else [np.nan], data, axis=0).reshape((-1, 2) if vector else (-1,))
        data = data[inverse].reshape((-1, 3, 2) if vector else (-1, 3))

        # vertex points for interpolation
        pos = self.geom.vertex_position(uvert, scope='local')[..., :2]
        if outside:
            pos = np.append([[np.nan, np.nan]], pos, axis=0)  # re-add outside points as nan

        pos = pos[inverse].reshape((-1, 6))

        # interpolate
        uvw = np.column_stack(barycentric_coord(points[:, 1:], pos[:, 0:2], pos[:, 2:4], pos[:, 4:6]))
        if vector and return_type == 'vector':
            vecx = (data[..., 0] * uvw).sum(axis=1)
            vecy = (data[..., 1] * uvw).sum(axis=1)
            values = np.concatenate((vecx.reshape(-1, 1, 1), vecy.reshape(-1, 1, 1)), axis=2)
        elif vector:
            mag = np.linalg.norm(data, axis=2)
            values = (mag * uvw).sum(axis=1).reshape(-1, 1)
        else:
            values = (data * uvw).sum(axis=1)

        # is the cell active?
        cells, inverse = np.unique(cell_ids, return_inverse=True)
        # if -1 exists, it will always be first since the unique routine sorts
        outside = cells[0] == -1
        if outside:
            cells = cells[1:]
        if data_type.lower() == 'bed elevation':
            active = np.full(len(cells), True, dtype=bool)
        else:
            active = self.extractor.wd_flag(data_type, (time_index, cells)).astype(bool)
        if outside:
            active = np.append([False], active)
        active = active[inverse]
        values[~active] = np.nan

        return np.append(
            points[:, 0].reshape((-1, 1, 1) if values.ndim > 2 else (-1, 1)),
            values.reshape(-1, 1) if values.ndim == 1 else values,
            axis=2 if values.ndim > 2 else 1
        )

    def profile_from_vertex_data(self: 'PyMesh',
                                 point: PointLike,
                                 data_type: str,
                                 time_index: int,
                                 return_type: str
                                 ) -> np.ndarray:
        """Extract data along a vertical profile at a given point from mesh vertices."""
        # results on vertices or 2d results
        zdtype, hdtype = self._2d_to_3d_data_types(data_type)
        z = self.data_point(point, zdtype)
        h = self.data_point(point, hdtype, time_index=time_index)
        if np.isnan(h):
            return np.array([[z, np.nan], [z, np.nan]])

        value = self.data_point(point, data_type, time_index=time_index, return_type=return_type)

        if self.is_vector(data_type) and return_type == 'vector':
            return np.array([[[h, value[0], value[1]]], [[z, value[0], value[1]]]])
        return np.array([[h, value], [z, value]])

    def curtain_from_vertex_data(
            self: 'Mesh',
            linestring: np.ndarray,
            cell_ids: np.ndarray,
            points: np.ndarray,
            dir_: np.ndarray,
            data_type: str,
            time: float
    ) -> np.ndarray:
        """Extract data along a curtain defined by a linestring from mesh vertices."""
        zdtype, hdtype = self._2d_to_3d_data_types(data_type)
        az = self.section(linestring, zdtype, time, get_start_end_locs=False)
        ah = self.section(linestring, hdtype, time, get_start_end_locs=False)
        val = self.section(linestring, data_type, time, return_type='vector', get_start_end_locs=False)

        az = az[1:-1]
        ah = ah[1:-1]
        val = val[1:-1]
        dir_ = dir_[1:-1]
        active = ~np.isnan(ah[:,1])

        ch = np.repeat(points[:, 0], 2)[1:-1].reshape(-1, 2)[active].flatten()
        ch = ch[np.array([[i, i+1, i+1, i] for i in range(0, ch.shape[0], 2)]).flatten()]

        y = np.column_stack((ah[:, 1], az[:, 1]))[active].flatten()
        y = y[np.array([[i, i, i+1, i+1] for i in range(0, y.shape[0], 2)]).flatten()]

        z = np.repeat(val[...,1:].reshape(val.shape[0], -1)[active], 4, axis=0).reshape(val[active].shape[0] * 4, -1)

        proj_vector = np.array([])
        if self.is_vector(data_type):
            proj_vector = self._project_vector(val[..., 1:], dir_).reshape(-1, 1, 2)
            proj_vector = np.repeat(proj_vector.reshape(proj_vector.shape[0], -1)[active], 4, axis=0).reshape(-1, 2)

        if self.is_vector(data_type):
            curtain = np.concatenate(
                (ch.reshape(-1, 1, 1), y.reshape(-1, 1, 1), z.reshape(-1, 1, 2), proj_vector.reshape(-1, 1, 2)),
                axis=2
            )
        else:
            curtain = np.column_stack((ch, y, z))

        return curtain
