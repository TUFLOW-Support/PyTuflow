import typing

import numpy as np

from . import barycentric_coord, PointLike

if typing.TYPE_CHECKING:
    from . import PyMesh


class VertexDataMixin:

    def vertex_data(self: 'PyMesh',
                    data_type: str,
                    time_index: int | slice
                    ) -> tuple[np.ndarray, np.ndarray]:
        """Returns data values and active mask for all vertices in the mesh for a given time slice."""
        data_type = self.translate_data_type(data_type)[0]
        is_static = self.is_static(data_type)
        if is_static:
            index = slice(None)
        else:
            index = (time_index, slice(None))

        if data_type == self.geom.data_type:
            data = self.geom.vertex_position(slice(None), get_z=True)[:, 2]
            wd = np.full(data.shape[0], True, dtype=bool)
            return data, wd

        data = self.extractor.data(data_type, index)
        wd = self.extractor.wd_flag(data_type, index).astype(bool)
        if wd.ndim == 1:
            wd_vert = self._map_wet_dry_to_verts(wd)
        else:
            wd_vert = np.empty(data.shape[:2], dtype=bool)
            for t in range(wd.shape[0]):
                wd_vert[t] = self._map_wet_dry_to_verts(wd[t])
        return data, wd_vert

    def data_point_from_vertex_data(self: 'PyMesh',
                                    point: np.ndarray,
                                    data_type: str,
                                    time_index: int,
                                    return_type: str
                                    ) -> float | tuple[float, float]:
        """Returns the interpolated data value from mesh vertices at the given point."""
        data_type = self.translate_data_type(data_type)[0]
        tri = self.geom.find_containing_triangle(point, 'local')
        if tri == -1:
            return np.nan

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
        data_type = self.translate_data_type(data_type)[0]
        tri = self.geom.find_containing_triangle(point, 'local')
        if tri == -1:
            return np.array([])

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
        data_type = self.translate_data_type(data_type)[0]
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

    def flux_from_vertex_data(self: 'PyMesh',
                               line: np.ndarray,
                               cell_ids: np.ndarray,
                               acell: np.ndarray,
                               dir_mid: np.ndarray,
                               data_type: str,
                               unit_flow: str,
                               ) -> np.ndarray:
        """Calculate flux across a line using vertex-based data.

        For 'unit flow'/'q', interpolates the unit flow vector at each segment midpoint
        and projects it onto the line normal. For any other (scalar) data type, the flux
        is computed as ``scalar * depth * dot(velocity, normal)`` integrated along the line.

        Parameters
        ----------
        line : np.ndarray
            The line in local coordinates (unused directly; retained for API symmetry
            with the curtain equivalent).
        cell_ids : np.ndarray
            N cell IDs at intersection + endpoint positions returned by ``mesh_line``.
        acell : np.ndarray
            Nx3 ``[offset, x, y]`` intersection + endpoint positions (local coords).
        dir_mid : np.ndarray
            (N-1)x2 normalised direction vectors, one per segment midpoint.
        data_type : str
            Result type: ``'unit flow'``/``'q'`` for direct unit-flow flux, or a scalar
            data type for ``scalar * depth * velocity`` flux.
        unit_flow : str
            The result type name for unit flow. If left blank, velocity and depth will be used
            rather than unit flow.

        Returns
        -------
        np.ndarray
            ``(T, 2)`` array of ``[time, flux]``, or empty array if the line lies
            entirely outside the mesh.
        """
        is_unit_flow_request = unit_flow != ''
        # Some formats (e.g. TUFLOW HPC XMDF) store 'unit flow' as a scalar magnitude
        # rather than a (qx, qy) vector.  Only use it directly when it is truly a vector;
        # otherwise fall back to velocity × depth which is mathematically equivalent.
        use_q_vector = is_unit_flow_request and self.is_vector(unit_flow)

        if use_q_vector:
            q_dt = self.translate_data_type(unit_flow)[0]
            wd_dt = q_dt
            times = self.times(unit_flow)
            vel_dt = depth_dt = None
        else:
            # Use the vector form of velocity (e.g. TUFLOW HPC XMDF stores the scalar
            # magnitude as 'velocity' and the (Vx, Vy) vector as 'vector velocity').
            vel_dt = self.translate_data_type(
                'vector velocity' if not self.is_vector('velocity') else 'velocity'
            )[0]
            wd_dt = vel_dt
            depth_dt = self.translate_data_type('depth')[0]
            times = self.times(data_type) if data_type else self.times('velocity')

        scalar_dt = self.translate_data_type(data_type)[0] if data_type else None

        T = len(times)
        n_segs = len(cell_ids) - 1

        widths = np.diff(acell[:, 0])                                           # (n_segs,)
        # dir_mid has n_segs+2 entries: one "before start" sentinel and one "after end" sentinel.
        # Trim both to obtain one direction per segment, matching the segment layout.
        # The normal is a 90° CCW rotation of the line direction so that positive flux means
        # flow crossing left-to-right when walking along the line (same convention as _project_vector).
        normals = np.column_stack((-dir_mid[1:-1, 1], dir_mid[1:-1, 0]))       # (n_segs, 2)

        # --- Pass 1: find containing triangles for two sample points per segment ---
        # Each segment is sampled at two points: one nudged from each endpoint toward the
        # interior of the segment.  This avoids placing the query exactly on a mesh edge
        # (which can return -1 or NaN from barycentric interpolation) while also capturing
        # any gradient across the cell rather than averaging it away at the midpoint.
        # The two contributions are combined with the trapezoidal rule.
        # When a point lies exactly on the mesh boundary the sample may still fail (-1 tri);
        # in that case only the successful sample is used with a rectangular (single-point) rule.
        NUDGE = 0.01                # fraction of segment length to nudge inward from each end
        seg_info = []               # list of dicts {'a': (...), 'b': (...)} or None per segment
        all_vert_set = set()        # all unique vertex IDs needed
        all_tricell_list = []       # cell IDs for wd_flag reads

        for i in range(n_segs):
            c0, c1 = cell_ids[i], cell_ids[i + 1]
            if c0 == -1 and c1 == -1:
                seg_info.append(None)
                continue
            hint = int(c0) if c0 != -1 else int(c1)
            p0, p1 = acell[i, 1:3], acell[i + 1, 1:3]
            dv = p1 - p0

            info = {}
            for key, pt in (('a', p0 + NUDGE * dv), ('b', p1 - NUDGE * dv)):
                tri = self.geom.find_containing_triangle(pt, scope='local', cell_id=hint)
                if tri == -1:
                    continue
                uvw = self.geom.barycentric_factors(pt, tri, scope='local')
                verts, inv = np.unique(self.geom.triangle_vertices(tri), return_inverse=True)
                tri_cell = int(self.geom.triangle_cell(tri))
                info[key] = (tri_cell, verts, inv, uvw)
                all_vert_set.update(int(v) for v in verts)
                all_tricell_list.append(tri_cell)

            seg_info.append(info if info else None)

        if not all_vert_set:
            return np.array([])

        # --- Pass 2: batch-read all vertex data and wd_flags in one shot each ---
        all_verts = np.array(sorted(all_vert_set))

        if use_q_vector:
            all_q = self.extractor.data(q_dt, (slice(None), all_verts))            # (T, N_v, 2)
        else:
            all_vel = self.extractor.data(vel_dt, (slice(None), all_verts))        # (T, N_v, 2)
            all_depth = self.extractor.data(depth_dt, (slice(None), all_verts))    # (T, N_v)
        if scalar_dt:
            all_scalar = self.extractor.data(scalar_dt, (slice(None), all_verts))  # (T, N_v)

        ucells_wd = np.unique(all_tricell_list)
        wd_all = self.extractor.wd_flag(wd_dt, (slice(None), ucells_wd)).astype(bool)  # (T, N_uc)
        vert_to_idx = {int(v): i for i, v in enumerate(all_verts)}
        cell_to_wd_idx = {int(c): i for i, c in enumerate(ucells_wd)}

        def _q_contrib(local_idx, inv, uvw, wd):
            """Return per-timestep unit-flow flux contribution (before × width)."""
            q   = all_q[:, local_idx[inv], :]                       # (T, 3, 2)
            q_i = (q * uvw.reshape(1, 3, 1)).sum(axis=1)            # (T, 2)
            p   = (q_i * normals[i]).sum(axis=1)                    # (T,)
            p[~wd] = 0.0
            return p

        def _vel_depth_contrib(local_idx, inv, uvw, wd):
            """Return per-timestep vel×depth flux contribution (before × width)."""
            v   = all_vel[:, local_idx[inv], :]                     # (T, 3, 2)
            v_i = (v * uvw.reshape(1, 3, 1)).sum(axis=1)            # (T, 2)
            vn  = (v_i * normals[i]).sum(axis=1)                    # (T,)
            vn[~wd] = 0.0
            d   = all_depth[:, local_idx[inv]]                      # (T, 3)
            d_i = (d * uvw).sum(axis=1)                             # (T,)
            d_i[~wd] = 0.0
            return vn * d_i

        def _scalar(local_idx, inv, uvw, wd):
            """Return interpolated scalar (concentration / tracer), zeroed on dry cells."""
            s   = all_scalar[:, local_idx[inv]]                     # (T, 3)
            s_i = (s * uvw).sum(axis=1)                             # (T,)
            s_i[~wd] = 0.0
            return s_i

        # --- Pass 3: accumulate flux contributions (trapezoidal over the two sample points) ---
        flux_vals = np.zeros(T)
        for i, info in enumerate(seg_info):
            if info is None:
                continue

            parts = []
            for key in ('a', 'b'):
                if key not in info:
                    continue
                tri_cell, verts, inv, uvw = info[key]
                local_idx = np.array([vert_to_idx[int(v)] for v in verts])
                wd = wd_all[:, cell_to_wd_idx[tri_cell]]            # (T,)

                Q = (_q_contrib if use_q_vector else _vel_depth_contrib)(local_idx, inv, uvw, wd)
                if scalar_dt:
                    parts.append(_scalar(local_idx, inv, uvw, wd) * Q * widths[i])
                else:
                    parts.append(Q * widths[i])

            if len(parts) == 2:
                flux_vals += 0.5 * (parts[0] + parts[1])   # trapezoidal rule
            elif parts:
                flux_vals += parts[0]                       # fallback: single-point rule

        return np.column_stack((times, flux_vals))

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
        if not active.any():
            return np.array([])

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
