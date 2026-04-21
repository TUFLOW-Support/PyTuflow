import typing

import numpy as np

from . import depth_averaging

if typing.TYPE_CHECKING:
    from . import PyMesh


class CellDataMixin:

    def cell_data(self: 'PyMesh',
                  data_type: str,
                  time_index: int | slice,
                  depth_averaging_method: str,
                  to_vertex: bool = False
                  ) -> tuple[np.ndarray, np.ndarray]:
        def cell2node(data_: np.ndarray, dry_mask: np.ndarray, wts_: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
            data_[dry_mask] = 0
            if wts_ is None:
                wts_ = self.geom.cell_to_vertex_weights().copy()
                wts_[dry_mask, :] = 0
                wts_sum = np.bincount(self.geom.cell_nodes.flatten(), wts_.flatten())
                mask = wts_sum == 0
                wts_sum[mask] = -999
                wts_ = wts_ / wts_sum[self.geom.cell_nodes]
            data_tiled = np.tile(data_, (4, 1)).transpose() * wts_
            return np.bincount(self.geom.cell_nodes.flatten(), data_tiled.flatten()), wts_

        data_types = self.translate_data_type(data_type)
        is_3d = self.is_3d(data_types[0])
        is_vector = self.is_vector(data_types[0])
        is_static = self.is_static(data_types[0])

        index = slice(None) if is_static else (time_index, slice(None))

        wd = self.wd_flag(data_types[0], index)
        if is_3d and depth_averaging_method is None:
            # be careful here - QGIS data extractor won't work here, but it should not get here anyway
            # as when depth averaging is None and 3D, the QGIS providers have a maximum() call which is used instead
            # this is only needed if a depth averaging method is specified which is not provided in QGIS call
            wd3d_index = self.data('idx2', slice(None)) - 1
            wd3d = wd[wd3d_index] if wd.ndim == 1 else wd[:, wd3d_index]

        wts = None
        if is_3d and depth_averaging_method is not None:
            nlevels = self.zlevel_count(slice(None))
            max_nlevels = nlevels.max()
            zlevels = self.zlevels(time_index, nlevels, np.arange(nlevels.shape[0]), self.cell_index(slice(None), data_types[0]))
            a_padded = np.full((nlevels.shape[0], max_nlevels), np.nan)
            b_padded = np.full((nlevels.shape[0], max_nlevels + 1), np.nan)

        data = np.array([])
        values = []
        for dtype in data_types:
            if dtype == self.geom.data_type:
                if to_vertex:
                    a = self.geom.vertex_position(slice(None))[:, 2]
                    wd = np.full((a.shape[0],), True)
                else:
                    a = self.geom.cell_position(slice(None))[:, 2]
                    wd = np.full((a.shape[0],), True)
                return a, wd

            a = self.data(dtype, index)
            extracted = [a[..., 0], a[..., 1]] if a.ndim == 3 else [a]
            for data in extracted:
                if data.ndim == 2 and data.shape[0] == 1:
                    data = data.flatten()
                if is_3d and depth_averaging_method is not None:
                    def depth_average(data_: np.ndarray, zlevels_: np.ndarray) -> np.ndarray:
                        a_padded[:] = np.nan
                        b_padded[:] = np.nan
                        k1, k2 = 0, 0
                        for i, nlevel in enumerate(nlevels):
                            a_padded[i, :nlevel] = data_[k1:k1 + nlevel]
                            b_padded[i, :nlevel + 1] = zlevels_[k2:k2 + nlevel + 1]
                            k1 += nlevel
                            k2 += nlevel + 1
                        return depth_averaging.get_method_func(depth_averaging_method)(b_padded, a_padded)

                    if data.ndim == 1:
                        data = depth_average(data, zlevels)
                        if to_vertex:
                            data, wts = cell2node(data, ~wd, wts)
                        else:
                            data[~wd, ...] = 0.
                    else:
                        shape = (data.shape[0], self.geom.vertices.shape[0]) if to_vertex else (data.shape[0], nlevels.shape[0])
                        data_avg = np.full(shape, np.nan)
                        for t in range(data.shape[0]):
                            if to_vertex:
                                depth_avg = depth_average(data[t, :], zlevels)
                                data_avg[t, :], wts = cell2node(depth_avg, ~wd[t, :], wts)
                            else:
                                data_avg[t, :] = depth_average(data[t, :], zlevels[t, :])
                        if not to_vertex:
                            data_avg[~wd, ...] = 0.
                        data = data_avg

                elif to_vertex:
                    data, wts = cell2node(data, ~wd, wts)
                else:
                    data[~wd3d if is_3d else ~wd, ...] = 0.

                if is_vector:
                    data = data.reshape(data.shape[0], -1, 1)
                values.append(data)

        if len(values) > 1:
            if is_static:
                data = np.column_stack(values).reshape((-1, 2) if is_vector else (-1, 1))
            else:
                data = np.concatenate(values, axis=2 if is_vector else 1)
        if to_vertex:
            wd = self._map_wet_dry_to_verts(wd)

        if is_3d and depth_averaging_method is None:
            wd = wd3d

        return data, wd

    def data_point_from_cell_data(
            self: 'PyMesh',
            point: np.ndarray,
            data_type: str,
            time_index: int,
            depth_averaging_method: str,
    ) -> float | tuple[float, float]:
        """Returns the data value from the mesh cell at the given point. No interpolation is performed."""
        cell_id = self.geom.find_containing_cell(point, scope='local')
        if cell_id == -1:
            return np.nan

        extractor = self._get_extractor(data_type)
        data_type = self.translate_data_type(data_type)

        # check if the cell is active
        wd = self.wd_flag(data_type[0], (time_index, cell_id))
        if not wd:
            return np.nan

        # get the data - velocity collects 2 values V_x and V_y
        # will collect float or tuple[float] for 2D results, and np.ndarray for 3D results
        is_3d = self.is_3d(data_type[0])
        cell_idx = self.cell_index(cell_id, data_type[0])[0] if is_3d else cell_id
        nlevels = self.zlevel_count(cell_id)[0]
        values = []
        for dtype in data_type:
            if is_3d:
                if extractor.NAME == 'QgisDataExtractor':
                    a = self.data(dtype, (time_index, [cell_idx]))
                    if a.ndim == 2:
                        values = [a[:, 0], a[:, 1]]
                        break
                else:
                    a = self.data(dtype, (time_index, slice(cell_idx, cell_idx + nlevels)))
            else:
                a = self.data(dtype, (time_index, cell_idx))
            values.append(a)

        if is_3d:
            values_avg = []
            for val in values:
                zlevels = self.zlevels(time_index, nlevels, cell_id, cell_idx)
                a = depth_averaging.get_method_func(depth_averaging_method)(zlevels, val)
                values_avg.append(a)
            values = values_avg

        if len(values) > 1:
            data = np.column_stack(values)
        else:
            data = values[0]
        return float(data[0] if isinstance(data, np.ndarray) and data.ndim > 0 else data) if len(values) == 1 else tuple([x for x in data.flatten()])

    def time_series_from_cell_data(
            self: 'PyMesh',
            point: np.ndarray,
            data_type: str,
            depth_averaging_method: str
    ) -> np.ndarray:
        cell_id = self.geom.find_containing_cell(point, scope='local')
        if cell_id == -1:
            return np.array([])

        extractor = self._get_extractor(data_type)
        data_type = self.translate_data_type(data_type)

        # get the data - velocity collects 2 values V_x and V_y
        is_3d = self.is_3d(data_type[0])
        cell_idx = self.cell_index(cell_id, data_type[0])[0] if is_3d else cell_id
        nlevels = self.zlevel_count(cell_id)[0]
        values = []
        for dtype in data_type:
            if is_3d:
                if extractor.NAME == 'QgisDataExtractor':
                    a = self.data(dtype, (slice(None), [cell_idx]))
                    if a.ndim == 3:
                        values = [a[:,:, 0], a[:,:, 1]]
                        break
                else:
                    a = self.data(dtype, (slice(None), slice(cell_idx, cell_idx + nlevels)))
            else:
                cell_idx = cell_id
                a = self.data(dtype, (slice(None), cell_idx))
            values.append(a)

        wd = self.wd_flag(data_type[0], (slice(None), cell_id)).flatten().astype(bool)

        if is_3d:
            zlevels = self.zlevels(slice(None), nlevels, cell_id, cell_idx)
            values_avg = []
            for val in values:
                a = depth_averaging.get_method_func(depth_averaging_method)(zlevels, val)
                values_avg.append(a)
            values = values_avg

        if len(values) > 1:
            data = np.column_stack(values)
        else:
            data = values[0]
        data[~wd, ...] = np.nan
        return data if len(values) == 1 else data.reshape(-1, 1, 2)

    def section_from_cell_data(
            self: 'PyMesh',
            cell_ids: np.ndarray,
            points: np.ndarray,
            data_type: str,
            time_index: int,
            depth_averaging_method: str
    ) -> np.ndarray:
        extractor = self._get_extractor(data_type)
        data_type = self.translate_data_type(data_type)

        cells, inverse = np.unique(cell_ids, return_inverse=True)
        outside = cells[0] == -1
        if outside:
            cells = cells[1:]
        is_3d = self.is_3d(data_type[0])
        cell_idx = self.cell_index(cells, data_type[0])
        if is_3d:
            nlevels = self.zlevel_count(cells)
            max_nlevels = nlevels.max()
            if extractor.NAME == 'QgisDataExtractor':
                idx = cells
            else:
                idx = [icell + ilevel for icell, nlevel in np.column_stack((cell_idx, nlevels)) for ilevel in range(nlevel)]
        else:
            max_nlevels = 1
            idx = cells

        values = []
        for dtype in data_type:
            a = self.data(dtype, (time_index, idx))
            extracted = [a[:,0], a[:,1]] if a.ndim == 2 else [a]
            for a in extracted:
                if is_3d:
                    zlevels = self.zlevels(time_index, nlevels, cells, cell_idx)
                    a_padded = np.full((cell_idx.shape[0], max_nlevels), np.nan)
                    b_padded = np.full((cell_idx.shape[0], max_nlevels + 1), np.nan)
                    k1, k2 = 0, 0
                    for i, nlevel in enumerate(nlevels):
                        a_padded[i, :nlevel] = a[k1:k1 + nlevel]
                        b_padded[i, :nlevel+1] = zlevels[k2:k2 + nlevel + 1]
                        k1 += nlevel
                        k2 += nlevel + 1
                    avg = depth_averaging.get_method_func(depth_averaging_method)(b_padded, a_padded)
                    values.append(avg)
                else:
                    values.append(a)

        if len(values) > 1:
            data = np.column_stack(values)
        else:
            data = values[0]
        if outside:
            data = np.append(np.zeros((1, data.shape[1]) if data.ndim > 1 else (1,)), data, axis=0)

        wd = self.wd_flag(data_type[0], (time_index, cells)).flatten().astype(bool)
        if outside:
            wd = np.append([False], wd)
        data[~wd, ...] = np.nan
        data = data[inverse]

        if cell_ids[-1] == -1:
            data = (np.append(
                np.repeat(data[:-2,...], 2, axis=0),
                [np.nan, np.nan] if data.ndim == 1 else [[np.nan, np.nan], [np.nan, np.nan]], axis=0)
            )
        else:
            data = np.repeat(data[:-1,...], 2, axis=0)
        offset = np.repeat(points[:,[0]], 2, axis=0)[1:-1,...]

        return np.append(
            offset.reshape((-1, 1) if len(values) == 1 else (-1, 1, 1)),
            data.reshape(-1, 1) if len(values) == 1 else data.reshape(-1, 1, 2),
            axis=1 if len(values) == 1 else 2
        )

    def flux_from_cell_data(self: 'PyMesh',
                             cell_ids: np.ndarray,
                             acell: np.ndarray,
                             dir_: np.ndarray,
                             data_type: str,
                             unit_flow: str,
                             ) -> np.ndarray:
        """Calculate flux across a line using cell-centred data.

        For 'unit flow'/'q', the unit flow vector in each cell is projected onto the
        line normal and integrated over the segment width.  For any other (scalar) data
        type, the flux is ``scalar * depth * dot(velocity, normal)`` integrated along the
        line (2-D only; 3-D cell-centred scalar flux is not yet implemented).

        Parameters
        ----------
        cell_ids : np.ndarray
            N cell IDs at intersection + endpoint positions returned by ``mesh_line``.
        acell : np.ndarray
            Nx3 ``[offset, x, y]`` intersection + endpoint positions.
        dir_ : np.ndarray
            Nx2 normalised direction vectors at each intersection point.
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
        is_unit_flow = unit_flow != ''

        times = self.times(unit_flow if is_unit_flow else 'velocity')
        T = len(times)

        # N-1 segments: segment i spans acell[i]→acell[i+1] and belongs to cell_ids[i].
        # When the line endpoint (p2) lies outside the mesh, cell_ids ends with
        # [..., cN, cN, -1]: the duplicate cN is a phantom for the exit→p2 segment
        # which is outside the mesh. Exclude it by zeroing valid for the last entry.
        seg_cells = cell_ids[:-1]
        valid = seg_cells != -1
        if cell_ids[-1] == -1 and valid.any():
            valid[-1] = False
        if not valid.any():
            return np.array([])

        valid_cells = seg_cells[valid]
        widths = np.diff(acell[:, 0])[valid]                                     # (M,)
        normals = np.column_stack((-dir_[:-1, 1], dir_[:-1, 0]))[valid]         # (M, 2)

        ucells, inverse = np.unique(valid_cells, return_inverse=True)            # (n,), (M,)

        if is_unit_flow:
            if data_type and self.is_3d(data_type):
                raise ValueError('Calculating volume flux of a data type is not supported with unit flow for 3D results. Use use_unit_flow=False')
            dt = self.translate_data_type(unit_flow)[0]
            q = self.data(dt, (slice(None), ucells))                  # (T, n, 2)
            wd = self.wd_flag(dt, (slice(None), ucells)).astype(bool) # (T, n)
            q_seg = q[:, inverse, :]                                             # (T, M, 2)
            wd_seg = wd[:, inverse]            
            q_seg[np.isnan(q_seg)] = 0.                              # (T, M)
            proj = (q_seg * normals).sum(axis=2)                                 # (T, M)
            proj[~wd_seg] = 0.0
            if data_type:
                scalar_dt = self.translate_data_type(data_type)[0]
                scalar = self.data(scalar_dt, (slice(None), ucells))  # (T, n)
                scalar_seg = scalar[:, inverse]                                   # (T, M)
                scalar_seg[~wd_seg] = 0.0
                flux_vals = (scalar_seg * proj * widths).sum(axis=1)             # (T,)
            else:
                flux_vals = (proj * widths).sum(axis=1)                          # (T,)
        else:
            vel_data_types = self.translate_data_type('velocity')
            vel_dt = vel_data_types[0]
            if self.is_3d(vel_dt):
                # 3D: sum flux contributions layer by layer across all segments
                cell_idx3 = self.cell_index(ucells, vel_dt)  # (n,) 3D start indices (0-based)
                nlevels = self.zlevel_count(ucells)           # (n,) layer counts per cell
                max_NL = int(nlevels.max())
                n = len(ucells)

                # Flat list of 3D layer indices: all layers of all unique cells, contiguous
                if self._get_extractor().NAME == 'QgisDataExtractor' and (ucells == cell_idx3).all():
                    flat_3d_idx = cell_idx3
                else:
                    flat_3d_idx = [int(cell_idx3[i]) + j
                                for i, nl in enumerate(nlevels)
                                for j in range(int(nl))]

                # Read velocity: two-component (V_x, V_y) or single (T, Σ_NL, 2) dataset
                if len(vel_data_types) == 1:
                    all_vel = self.data(vel_data_types[0], (slice(None), flat_3d_idx))  # (T, Σ_NL, 2)
                else:
                    comps = [self.data(dt, (slice(None), flat_3d_idx)) for dt in vel_data_types]
                    all_vel = np.stack(comps, axis=-1)                           # (T, Σ_NL, 2)

                # Layer face elevations: (T, Σ_(NL_i+1)); faces are [top, bottom] per layer
                all_faces = self.zlevels(slice(None), nlevels, ucells, cell_idx3)

                # Build padded arrays (T, n, max_NL, ...)
                vel_padded   = np.zeros((T, n, max_NL, 2))
                thick_padded = np.zeros((T, n, max_NL))
                valid_mask   = np.zeros((n, max_NL), dtype=bool)  # True where layer exists
                k_v, k_f = 0, 0
                for i, nl in enumerate(nlevels):
                    nl = int(nl)
                    vel_padded[:, i, :nl, :]  = all_vel[:, k_v:k_v + nl, :]
                    # abs() handles either face ordering ([top, bottom] or [bottom, top])
                    thick_padded[:, i, :nl]   = np.abs(np.diff(all_faces[:, k_f:k_f + nl + 1], axis=1))
                    valid_mask[i, :nl]         = True
                    k_v += nl
                    k_f += nl + 1

                # wd_flag per 2D cell (T, n)
                wd = self.wd_flag(vel_dt, (slice(None), ucells)).astype(bool)

                # Expand to segment arrays via inverse
                vel_seg   = vel_padded[:, inverse, :, :]   # (T, M, max_NL, 2)
                thick_seg = thick_padded[:, inverse, :]    # (T, M, max_NL)
                wd_seg    = wd[:, inverse]                 # (T, M)
                valid_seg = valid_mask[inverse]            # (M, max_NL)

                # Normal projection per layer: (T, M, max_NL)
                vel_n = (vel_seg * normals[np.newaxis, :, np.newaxis, :]).sum(axis=3)

                # Combined wet-dry mask: cell must be wet AND layer must exist
                wet_3d = wd_seg[:, :, np.newaxis] & valid_seg[np.newaxis, :, :]  # (T, M, max_NL)
                vel_n[~wet_3d]    = 0.0
                thick_seg[~wet_3d] = 0.0

                if data_type:
                    scalar_dt_list = self.translate_data_type(data_type)
                    scalar_dt = scalar_dt_list[0]
                    if self.is_3d(scalar_dt):
                        # Scalar also 3D: read at the same flat layer indices
                        all_sc = self.data(scalar_dt, (slice(None), flat_3d_idx))  # (T, Σ_NL)
                        sc_padded = np.zeros((T, n, max_NL))
                        k = 0
                        for i, nl in enumerate(nlevels):
                            nl = int(nl)
                            sc_padded[:, i, :nl] = all_sc[:, k:k + nl]
                            k += nl
                        sc_seg = sc_padded[:, inverse, :]                        # (T, M, max_NL)
                        sc_seg[~wet_3d] = 0.0
                    else:
                        # 2D scalar: same value for every layer in the column
                        sc_2d = self.data(scalar_dt, (slice(None), ucells))  # (T, n)
                        sc_seg = np.where(wet_3d, sc_2d[:, inverse, np.newaxis], 0.0)  # (T, M, max_NL)
                    flux_vals = (sc_seg * vel_n * thick_seg * widths[np.newaxis, :, np.newaxis]).sum(axis=(1, 2))
                else:
                    flux_vals = (vel_n * thick_seg * widths[np.newaxis, :, np.newaxis]).sum(axis=(1, 2))
            else:
                # 2D path
                vel = self.data(vel_dt, (slice(None), ucells))                # (T, n, 2)
                wd = self.wd_flag(vel_dt, (slice(None), ucells)).astype(bool) # (T, n)
                vel_seg = vel[:, inverse, :]                                             # (T, M, 2)
                wd_seg = wd[:, inverse]                                                  # (T, M)
                vel_n = (vel_seg * normals).sum(axis=2)                                  # (T, M)
                vel_n[~wd_seg] = 0.0

                depth_dt = self.translate_data_type('depth')[0]
                depth = self.data(depth_dt, (slice(None), ucells))            # (T, n)
                depth_seg = depth[:, inverse]                                            # (T, M)
                depth_seg[~wd_seg] = 0.0

                if data_type:
                    scalar_dt = self.translate_data_type(data_type)[0]
                    scalar = self.data(scalar_dt, (slice(None), ucells))      # (T, n)
                    scalar_seg = scalar[:, inverse]                                      # (T, M)
                    scalar_seg[~wd_seg] = 0.0
                    flux_vals = (scalar_seg * depth_seg * vel_n * widths).sum(axis=1)
                else:
                    flux_vals = (depth_seg * vel_n * widths).sum(axis=1)

        return np.column_stack((times, flux_vals))

    def profile_from_cell_data(self: 'PyMesh', point: np.ndarray, data_type: str, time_index: int) -> np.ndarray:
        cell_id = self.geom.find_containing_cell(point, scope='local')
        if cell_id == -1:
            return np.array([])

        extractor = self._get_extractor(data_type)
        data_type = self.translate_data_type(data_type)

        # check if the cell is active
        wd = self.wd_flag(data_type[0], (time_index, cell_id))
        if not wd:
            zdtype, _ = self._2d_to_3d_data_types(data_type[0])
            z = self.data_point(point, zdtype)
            return np.array([[z, np.nan], [z, np.nan]])

        # get the data - velocity collects 2 values V_x and V_y
        cell_idx = self.cell_index(cell_id, data_type[0])[0]
        nlevels = self.zlevel_count(cell_id)[0]
        values = []
        for dtype in data_type:
            if self.is_3d(dtype):
                if extractor.NAME == 'QgisDataExtractor':
                    values = self.data(dtype, (time_index, [cell_idx]))
                    shape = (-1, 2 if self.is_vector(dtype) else 1)
                    values = values.reshape(shape)
                    break
                a = self.data(dtype, (time_index, slice(cell_idx, cell_idx + nlevels)))
            else:
                a = self.data(dtype, (time_index, cell_id))
            values.append(a)
        values = np.column_stack(values).reshape(-1, len(values)) if isinstance(values, list) else values

        zlevels = self.zlevels(time_index, nlevels, cell_id, cell_idx)
        zlevels = list(zip(zlevels[:-1], zlevels[1:]))

        return np.column_stack(
            (np.array(zlevels).flatten(), np.repeat(values, 2, axis=0))
        ).reshape((-1, 2) if len(values[1]) == 1 else (-1, 1, 3))

    def curtain_from_cell_data(
            self: 'PyMesh',
            cell_ids: np.ndarray,
            points: np.ndarray,
            dir_: np.ndarray,
            data_type: str,
            time_index: int
    ) -> np.ndarray:
        extractor = self._get_extractor(data_type)
        data_type = self.translate_data_type(data_type)
        cells, inverse = np.unique(cell_ids, return_inverse=True)
        outside = cells[0] == -1
        if outside:
            cells = cells[1:]

        wd = self.wd_flag(data_type[0], (time_index, cells)).flatten().astype(bool)
        if outside:
            wd = np.append([False], wd)
        wd = wd[inverse]
        wd = (wd.astype(int)[:-1] + wd.astype(int)[1:]) == 2
        cell_ids = np.repeat(cell_ids, 2)[1:-1].reshape(-1, 2)[:, 0]
        dir_ = np.repeat(dir_, 2, axis=0)[1:-1].reshape(-1, 4)[:,:2]
        cells, inverse = np.unique(cell_ids[wd], return_inverse=True)

        cell_idx = self.cell_index(cells, data_type[0])

        nlevels = self.zlevel_count(cells)
        zlevels = self.zlevels(time_index, nlevels, cells, cell_idx)
        if self.is_3d(data_type[0]):
            if extractor.NAME == 'QgisDataExtractor':
                idx = cells
            else:
                idx = [icell + ilevel for icell, nlevel in np.column_stack((cell_idx, nlevels)) for ilevel in range(nlevel)]
        else:
            idx = cells

        # Build inverse mapping into 3D array
        offsets = np.concatenate([[0], np.cumsum(nlevels[:-1])])
        size = np.sum(nlevels[inverse])

        # Build inverse mapping into zlevels
        nlevels_z = nlevels + 1
        offsets_z = np.concatenate([[0], np.cumsum(nlevels_z[:-1])])
        size_z = np.sum(nlevels_z[inverse])

        inverse3d = np.empty(size, dtype=int)
        inverse_z = np.empty(size_z, dtype=int)
        pos = 0
        pos_z = 0
        for orig_idx in inverse:
            nl = nlevels[orig_idx]
            start = offsets[orig_idx]
            try:
                inverse3d[pos:pos + nl] = np.arange(start, start + nl)
            except ValueError:
                print('issue!')
            pos += nl

            nl = nlevels_z[orig_idx]
            start = offsets_z[orig_idx]
            inverse_z[pos_z:pos_z + nl] = np.arange(start, start + nl)
            pos_z += nl

        data = None
        for dtype in data_type:
            a_ = self.data(dtype, (time_index, idx))
            data = a_ if data is None else np.column_stack((data, a_))

        nlevels = nlevels[inverse]

        # offsets
        repeat = nlevels if self.is_3d(data_type[0]) else 1
        ch = np.repeat((np.repeat(points[:, 0], 2)[1:-1]).reshape(-1, 2)[wd], repeat, axis=0)
        offsets = np.concatenate((ch, ch[:, ::-1]), axis=1).reshape((-1,))

        # elevations
        zlevels = zlevels[inverse_z]
        if self.is_3d(data_type[0]):
            counts = np.concatenate([[2] + [4] * (nl - 1) + [2] for nl in nlevels]) if self.is_3d(data_type[0]) else 1
            elev = np.repeat(zlevels, counts)
        else:
            inds = np.cumsum(nlevels)
            segments = np.split(zlevels, inds[:-1])
            mins = [seg.min() for seg in segments]
            maxs = [seg.max() for seg in segments]
            elev = np.repeat(np.array([x for x in zip(maxs, mins)]), 2)

        # data
        data = data[inverse3d] if self.is_3d(data_type[0]) else data[inverse]
        if self.is_vector(data_type[0]):
            dir_ = np.repeat(dir_[wd], nlevels, axis=0)
            vec = self._project_vector(data, dir_)
        data = np.repeat(data, 4, axis=0)
        if self.is_vector(data_type[0]):
            data = np.append(data, np.repeat(vec, 4, axis=0), axis=1)

        return np.column_stack((offsets, elev, data))
