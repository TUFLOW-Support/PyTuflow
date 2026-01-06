import typing

import numpy as np

from . import depth_averaging

if typing.TYPE_CHECKING:
    from . import PyMesh


class CellDataMixin:

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
            raise ValueError('Point falls outside mesh.')

        data_type = self.translate_data_type(data_type)

        # check if the cell is active
        wd = self.extractor.wd_flag(data_type[0], (time_index, cell_id))
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
                a = self.extractor.data(dtype, (time_index, slice(cell_idx, cell_idx + nlevels)))
            else:
                a = self.extractor.data(dtype, (time_index, cell_idx))
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
        return float(data) if len(values) == 1 else tuple(data.flatten())

    def time_series_from_cell_data(
            self: 'PyMesh',
            point: np.ndarray,
            data_type: str,
            depth_averaging_method: str
    ) -> np.ndarray:
        cell_id = self.geom.find_containing_cell(point, scope='local')
        if cell_id == -1:
            raise ValueError('Point falls outside mesh.')

        data_type = self.translate_data_type(data_type)

        # get the data - velocity collects 2 values V_x and V_y
        is_3d = self.is_3d(data_type[0])
        cell_idx = self.cell_index(cell_id, data_type[0])[0] if is_3d else cell_id
        nlevels = self.zlevel_count(cell_id)[0]
        values = []
        for dtype in data_type:
            if is_3d:
                a = self.extractor.data(dtype, (slice(None), slice(cell_idx, cell_idx + nlevels)))
            else:
                cell_idx = cell_id
                a = self.extractor.data(dtype, (slice(None), cell_idx))
            values.append(a)

        wd = self.extractor.wd_flag(data_type[0], (slice(None), cell_id)).flatten().astype(bool)

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
            idx = [icell + ilevel for icell, nlevel in np.column_stack((cell_idx, nlevels)) for ilevel in range(nlevel)]
        else:
            max_nlevels = 1
            idx = cells

        values = []
        for dtype in data_type:
            a = self.extractor.data(dtype, (time_index, idx))
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

        wd = self.extractor.wd_flag(data_type[0], (time_index, cells)).flatten().astype(bool)
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

    def profile_from_cell_data(self: 'PyMesh', point: np.ndarray, data_type: str, time_index: int) -> np.ndarray:
        cell_id = self.geom.find_containing_cell(point, scope='local')
        if cell_id == -1:
            raise ValueError('Point falls outside mesh.')

        data_type = self.translate_data_type(data_type)

        # check if the cell is active
        wd = self.extractor.wd_flag(data_type[0], (time_index, cell_id))
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
                a = self.extractor.data(dtype, (time_index, slice(cell_idx, cell_idx + nlevels)))
            else:
                a = self.extractor.data(dtype, (time_index, cell_id))
            values.append(a)
        values = np.column_stack(values).reshape(-1, len(values))

        zlevels = self.zlevels(time_index, nlevels, cell_id, cell_idx)
        zlevels = list(zip(zlevels[:-1], zlevels[1:]))

        return np.column_stack(
            (np.array(zlevels).flatten(), np.repeat(values, 2, axis=0))
        ).reshape((-1, 2) if len(values[1] == 1) else (-1, 1, 2))

    def curtain_from_cell_data(
            self: 'PyMesh',
            cell_ids: np.ndarray,
            points: np.ndarray,
            dir_: np.ndarray,
            data_type: str,
            time_index: int
    ) -> np.ndarray:
        data_type = self.translate_data_type(data_type)
        cells, inverse = np.unique(cell_ids, return_inverse=True)
        outside = cells[0] == -1
        if outside:
            cells = cells[1:]

        wd = self.extractor.wd_flag(data_type[0], (time_index, cells)).flatten().astype(bool)
        if outside:
            wd = np.append([False], wd)
        wd = wd[inverse]
        cells, inverse = np.unique(cell_ids[wd], return_inverse=True)
        if inverse.size > 1 and inverse[-1] == inverse[-2]:
            inverse = inverse[:-1]

        cell_idx = self.cell_index(cells, data_type[0])

        nlevels = self.zlevel_count(cells)
        zlevels = self.zlevels(time_index, nlevels, cells, cell_idx)
        if self.is_3d(data_type[0]):
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
            a_ = self.extractor.data(dtype, (time_index, idx))
            data = a_ if data is None else np.column_stack((data, a_))

        nlevels = nlevels[inverse]

        # if cell_ids[-1] == -1:
        #     data = np.append(np.repeat(data[:-2,...], 2, axis=0), [np.nan, np.nan], axis=0)
        # else:
        #     data = np.repeat(data[:-1,...], 2, axis=0)

        # offsets
        repeat = nlevels if self.is_3d(data_type[0]) else 1
        ch = np.repeat((np.repeat(points[wd, 0], 2)[1:-1]).reshape(-1, 2), repeat, axis=0)
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
            if nlevels.size < dir_.size:
                dir_ = dir_[:-1]
                wd = wd[:-1]
            dir_ = np.repeat(dir_[wd], nlevels, axis=0)
            vec = self._project_vector(data, dir_)
        data = np.repeat(data, 4, axis=0)
        if self.is_vector(data_type[0]):
            data = np.append(data, np.repeat(vec, 4, axis=0), axis=1)

        return np.column_stack((offsets, elev, data))
