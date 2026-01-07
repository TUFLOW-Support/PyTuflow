from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import (LineStringMixin, LineStringLike, PointMixin, PointLike, VertexDataMixin, CellDataMixin, Cache,
               PyMeshGeometry, PyDataExtractor, NCEngine, H5Engine, SoftLoadMixin)

try:
    import shapely
    has_shapely = True
except ImportError:
    has_shapely = False
    from .stubs import shapely

try:
    import pyvista as pv
except ImportError:
    from .stubs import pyvista as pv


class PyMesh(VertexDataMixin, CellDataMixin, PointMixin, LineStringMixin, SoftLoadMixin):
    DRIVER_SOURCE = 'python'

    def __init__(self, *args, **kwargs):
        self._init_soft_load()
        self.cache = Cache()
        self.name = ''
        self.geom: PyMeshGeometry = PyMeshGeometry('')
        self.extractor: PyDataExtractor = PyDataExtractor()
        self.has_inherent_reference_time = False
        self.reference_time = datetime(1970, 1, 1, tzinfo=timezone.utc)
        self.start_end_locs = []  # used by CATCHJson to stitch sections together

        self._cached_data_types = {}
        self._data_types = []

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} {self.name}>'

    def __contains__(self, item: str) -> bool:
        return item in self.data_types()

    @staticmethod
    def available() -> bool:
        return '.stubs' not in pv.__name__ and (H5Engine.available() or NCEngine.available())

    def load(self):
        self.geom.load()

    def translate_data_type(self, data_type: str) -> tuple[str, ...]:
        """Translate data type for result extraction. An example is velocity, which the user would input
        "V", but some extractors may require 2 separate data types "V_x" and "V_y to extract the full vector.

        Does not translate common names into extractor specific names. Does translate case-insenstive names
        into the correct case for the extractor.

        Parameters
        ----------
        data_type : str
            The data type to translate.

        Returns
        -------
        tuple[str, ...]
            The translated data type(s). Returned as a tuple since vectors may require multiple data types.
        """
        from ..map_output import MapOutput
        dtype = MapOutput._get_standard_data_type_name(data_type)
        dtype = [x for x in self.data_types() if MapOutput._get_standard_data_type_name(x) == dtype]
        data_type = dtype[0] if dtype else data_type
        if not self._cached_data_types:
            self._cached_data_types = {x.lower(): x for x in self.data_types()}
        data_type = self._cached_data_types.get(data_type.lower(), data_type)
        return (data_type,)

    def times(self, data_type: str) -> np.ndarray:
        """Returns the times available for the given result type.

        Parameters
        ----------
        data_type : str
            The result type to get the times for.

        Returns
        -------
        np.ndarray[float]
            An array of times.
        """
        return self.extractor.times(self.translate_data_type(data_type)[0])

    def data_types(self) -> list[str]:
        """Returns a list of the available data types for this mesh object. Typically, the data types will
        be returned in a path structure, except for temporal data, which will be returned with just the name.

        For example, temporal depth results will be returned as "depth" and if there is a maximum depth dataset,
        it will be returned as "maximums/depth". The folder structure is somewhat determined by the mesh format
        itself.

        Returns
        -------
        list[str]
            A list of available data types in the mesh object.
        """
        if not self._data_types:
            self._data_types = ['Bed Elevation'] + self.extractor.data_types() if self.geom.has_z else self.extractor.data_types()
        return self._data_types

    def reference_time_(self, data_type: str) -> datetime:
        """Returns the reference time for the given data type. Will return None if the dataset does
        not have a reference time.

        Parameters
        ----------
        data_type :  str
            The result type to get the reference time for.

        Returns
        -------
        datetime
            The dataset reference time.
        """
        return self.extractor.reference_time(self.translate_data_type(data_type)[0])

    def maximum(self, data_type: str) -> float:
        """Returns the maximum value for the specified result type. The full path the result type must be specified,
        for example, "depth" will return the maximum for the temporal depth results. If searching for the absolute
        maximum (the maximum value in the maximum output surface) then "maximums/depth" must be used (if applicable).

        Parameters
        ----------
        data_type : str
            The type of result to return the maximum value for.

        Returns
        -------
        float
            The maximum value for the specified result type.
        """
        if self.cache.contains('maximum', data_type):
            return self.cache.get('maximum', data_type)
        mx = self.extractor.maximum(self.translate_data_type(data_type)[0])
        self.cache.set('maximum', data_type, mx)
        return mx

    def minimum(self, data_type: str) -> float:
        """Returns the minimum value for the specified result type. The full path the result type must be specified,
        for example, "depth" will return the minimum for the temporal depth results. If searching for the absolute
        minimum (the minimum value in the minimum output surface) then "minimums/depth" must be used (if applicable).

        Parameters
        ----------
        data_type : str
            The type of result to return the maximum value for.

        Returns
        -------
        float
            The maximum value for the specified result type.
        """
        if self.cache.contains('minimum', data_type):
            return self.cache.get('minimum', data_type)
        mn = self.extractor.minimum(self.translate_data_type(data_type)[0])
        self.cache.set('minimum', data_type[0], mn)
        return mn

    def is_vector(self, data_type: str) -> bool:
        """Returns whether the specified data type is a vector result.

        Parameters
        ----------
        data_type : str
            The type of result to check.

        Returns
        -------
        bool
            ``True`` if the data type is a vector result, ``False`` otherwise.
        """
        return data_type.lower() != 'bed elevation' and self.extractor.is_vector(self.translate_data_type(data_type)[0])

    def is_static(self, data_type: str) -> bool:
        """Returns whether the specified data type is a static result.

        Parameters
        ----------
        data_type : str
            The type of result to check.

        Returns
        -------
        bool
            ``True`` if the data type is a static result, ``False`` otherwise.
        """
        return data_type.lower() == 'bed elevation' or self.extractor.is_static(self.translate_data_type(data_type)[0])

    def on_vertex(self, data_type: str) -> bool:
        """Returns whether the specified data type is stored on mesh vertices.

        Parameters
        ----------
        data_type : str
            The type of result to check.

        Returns
        -------
        bool
            ``True`` if the data type is stored on mesh vertices, ``False`` otherwise.
        """
        return True

    def is_3d(self, data_type: str) -> bool:
        """Returns whether the specified data type is a 3D result.

        Parameters
        ----------
        data_type : str
            The type of result to check.

        Returns
        -------
        bool
            ``True`` if the data type is a 3D result, ``False`` otherwise.
        """
        return self.extractor.is_3d(self.translate_data_type(data_type)[0])

    def cell_index(self, cell_id: int | list[int] | np.ndarray, data_type: str) -> int:
        """Returns the index of the given cell ID for the specified data type. For 2D data types, the cell ID
        is the same as the index, but for 3D data types the cell index can be different.

        Parameters
        ----------
        cell_id : int
            The cell ID to get the index for.
        data_type : str
            The type of result to check.

        Returns
        -------
        int
            The index of the given cell ID for the specified data type.
        """
        return cell_id

    def data_point(self,
                   point: PointLike,
                   data_type: str, time: float = 0.,
                   time_index: int = -1,
                   depth_averaging: str = 'sigma&0&1',
                   return_type: str = 'scalar',
                   ) -> float | tuple[float, float] | np.ndarray:
        """Extract the data at given point for the specified data type and time.

        Parameters
        ----------
        point : PointLike
            The point to extract the data for.
        data_type : str
            The result type to extract the data for.
        time : float, optional
            The time to extract the data for. The time must match a timestep that exists within the dataset
            i.e. the routine will not look for the closest time, it will look for the time exactly.
        time_index : int, optional
            The time index to return the data for. This value will take precedence over the ``time
            `` parameter if a value greater than ``-1`` is provided.
        depth_averaging : str, optional
            The depth averaging method to use when extracting 3D data. Options are:

            - `singlelevel`
            - `multilevel`
            - `depth`
            - `height`
            - `elevation`
            - `sigma` (default)
        return_type : str, options
            The return type of the data for vector results (has no effect on scalar results). Options are:

            - `scalar` (default): returns the scalar value or magnitude of vector values.
            - `vector`: returns the vector components as a tuple of floats.

        Returns
        -------
        float | tuple[float, float] | np.ndarray
            The data value at the given point. If the data type is a vector, a tuple of floats will be returned.
            If the data is 3D, a numpy array will be returned with the vertical profile.
        """
        # coerce point
        p = self.geom.trans.transform(self._coerce_into_point(point))
        wkt = self._point_as_wkt(point)

        vector = self.is_vector(data_type)
        if not vector:
            return_type = 'scalar'

        # time index
        if self.is_static(data_type):
            time_index = -1
        else:
            time_index = time_index if time_index >= 0 else self._find_time_index(data_type, time)

        # check cache
        if self.cache.contains('data_point', data_type, wkt, time_index, return_type, depth_averaging):
            return self.cache.get('data_point', data_type, wkt, time_index, return_type, depth_averaging)

        # get value
        if self.on_vertex(data_type):
            data_point = self.data_point_from_vertex_data(p, data_type, time_index, return_type)
        else:
            data_point = self.data_point_from_cell_data(p, data_type, time_index, depth_averaging)

        # save cache
        self.cache.set(data_point, 'data_point', data_type, wkt, time_index, return_type, depth_averaging)

        return data_point

    def time_series(self,
                    point: PointLike,
                    data_type: str,
                    depth_averaging: str = 'sigma&0&1',
                    return_type: str = 'scalar',
                    ) -> np.ndarray:
        """"Returns time series information for the given point and data type.

        The returned array will be ``(N,2)`` for scalar data types and ``(N,1,3)`` for vector data types, where N
        is the number of time steps. The first column will be the time, and the second
        column (or second and third columns for vector data) will be the data values.

        Parameters
        ----------
        point : PointLike
            The point to extract the time series for.
        data_type : str
            The result type to extract the time series for.
        depth_averaging : str, optional
            The depth averaging method to use when extracting 3D data. Options are:

            - `singlelevel`
            - `multilevel`
            - `depth`
            - `height`
            - `elevation`
            - `sigma` (default)
        return_type : str, options
            The return type of the data for vector results (has no effect on scalar results). Options are:

            - `scalar` (default): returns the scalar value or magnitude of vector values.
            - `vector`: returns the vector components as a tuple of floats.

        Returns
        -------
        np.ndarray
            An array containing the extracted time series data.
        """
        if self.is_static(data_type):
            raise ValueError('Time series not available for static data types.')

        # coerce point
        p = self.geom.trans.transform(self._coerce_into_point(point))
        wkt = self._point_as_wkt(point)

        vector = self.is_vector(data_type)
        if not vector:
            return_type = 'scalar'

        depth_averaging = depth_averaging if self.is_3d(data_type) else None

        # check cache
        if self.cache.contains('time_series', data_type, return_type, depth_averaging, wkt):
            return self.cache.get('time_series', data_type, return_type, depth_averaging, wkt)

        # get data
        if self.on_vertex(data_type):
            data = self.time_series_from_vertex_data(p, data_type, return_type=return_type)
        else:
            data = self.time_series_from_cell_data(p, data_type, depth_averaging)

        if data.size == 0:
            return np.array([])

        time_series = np.append(
            self.times(data_type).reshape((-1, 1, 1) if data.ndim > 2 else (-1, 1)),
            data.reshape(-1, 1) if data.ndim == 1 else data,
            axis=2 if data.ndim > 2 else 1
        )

        # save cache
        self.cache.set(time_series, 'time_series', data_type, return_type, depth_averaging, wkt)

        return time_series


    def section(self,
                line: LineStringLike,
                data_type: str,
                time: float,
                depth_averaging: str = 'sigma&0&1',
                return_type: str = 'scalar',
                get_start_end_locs: bool = True,
                ) -> np.ndarray:
        """Returns section information for the given line and data type at the specified time.

        The returned array will be ``(N,2)`` for scalar data types and ``(N,1,3)`` for vector data types, where N
        is the number of points along the section. The first columns will be the distance along the section, and the
        second column (or second and third columns for vector data) will be the data values.

        Parameters
        ----------
        line : LineStringLike
            The line to extract the section along.
        data_type : str
            The result type to extract the section for.
        time : float
            The time to extract the data for. The time must match a timestep that exists within the
            dataset i.e. the routine will not look for the closest time, it will look for the time exactly.
        depth_averaging : str, optional
            The depth averaging method to use when extracting 3D data. Options are:

            - `singlelevel`
            - `multilevel`
            - `depth`
            - `height`
            - `elevation`
            - `sigma` (default)
        return_type : str, options
            The return type of the data for vector results (has no effect on scalar results). Options are:

            - `scalar` (default): returns the scalar value or magnitude of vector values.
            - `vector`: returns the vector components as a tuple of floats.
        get_start_end_locs : bool, optional
            Whether to record the start and end locations of the section within the mesh. The curtain plot
            for vertex data uses the section method and will independently record the start and end locations,
            so this allows it to be turned off for that use case.

        Returns
        -------
        np.ndarray
            An array containing the extracted section data.
        """
        with self.extractor.open():
            # coerce line
            line = self._coerce_into_line(line)

            # time index
            time_index = self._find_time_index(data_type, time)
            wkt = self._linestring_as_wkt(line)

            vector = self.is_vector(data_type)
            if not vector:
                return_type = 'scalar'

            depth_averaging = depth_averaging if self.is_3d(data_type) else None

            # check cache for results
            if self.cache.contains('section', data_type, time_index, return_type, depth_averaging, wkt):
                return self.cache.get('section', data_type, time_index, return_type, depth_averaging, wkt)

            # check cache for line intersections, otherwise calculate
            if self.cache.contains('mesh_line', wkt):
                cell_ids, acell, _, mid_cell_ids, amid, _ = self.cache.get('mesh_line', wkt)
            else:
                cell_ids, acell, dir_, mid_cell_ids, amid, dir_mid = self.geom.mesh_line(line)
                self.cache.set(
                    (cell_ids, acell, dir_, mid_cell_ids, amid, dir_mid),
                    'mesh_line',
                    wkt
                )

            # get data
            if self.on_vertex(data_type):
                section = self.section_from_vertex_data(mid_cell_ids, amid, data_type, time_index, return_type)
            else:
                section = self.section_from_cell_data(cell_ids, acell, data_type, time_index, depth_averaging)

            # start and end locations
            if get_start_end_locs:
                self._get_start_end_locations(cell_ids, acell)

            # save cache
            self.cache.set(section, 'section', data_type, time_index, return_type, depth_averaging, wkt)

            return section

    def profile(self, point: PointLike, data_type: str, time: float, return_type: str = 'scalar') -> np.ndarray:
        """Returns the vertical profile at the given point for the specified data type and time.

        The returned array will be ``(N,2)`` for scalar results and ``(N,1,3)`` for vector results, where N is the number
        of points in the profile. The first column will be the elevation, and the second column
        (or second and third columns for vector data) will be the data values.

        Parameters
        ----------
        point : PointLike
            The point to extract the profile for.
        data_type : str
            The result type to extract the profile for.
        time : float
            The time to extract the data for. The time must match a timestep that exists within the
            dataset i.e. the routine will not look for the closest time, it will look for
            the time exactly.
        return_type : str, options
            The return type of the data for vector results (has no effect on scalar results). Options are:

            - `scalar` (default): returns the scalar value or magnitude of vector values.
            - `vector`: returns the vector components as a tuple of floats.

        Returns
        -------
        np.ndarray
            An array containing the extracted profile data.
        """
        # coerce point
        p = self.geom.trans.transform(self._coerce_into_point(point))

        # time index
        time_index = self._find_time_index(data_type, time)

        vector = self.is_vector(data_type)
        if not vector:
            return_type = 'scalar'

        # check cache
        if self.cache.contains('profile', data_type, time_index, return_type, self._point_as_wkt(p)):
            return self.cache.get('profile', data_type, time_index, return_type, self._point_as_wkt(p))

        # get data
        if self.on_vertex(data_type):
            data = self.profile_from_vertex_data(point, data_type, time_index, return_type)
        else:
            data = self.profile_from_cell_data(p, data_type, time_index)

        # save cache
        self.cache.set(data, 'profile', data_type, time_index, return_type, self._point_as_wkt(p))

        return data

    def curtain(self, line: LineStringLike, data_type: str, time: float) -> np.ndarray:
        """Returns curtain plot information for the given data type along the specified line at the given time.

        The returned array will be ``(N,3)`` for scalar results and ``(N,1,6)`` for vector results,
        where ``N`` is the number of points in the curtain.

        The first two columns represent the ``x`` and ``y`` plot coordinates (i.e. offset and z)
        and the third column represents the data value for scalar results. Vector results also return the projected
        vector components onto the curtain plane as the fifth and sixth columns, where ``Y`` is considered
        along the curtain plane, and ``X`` is considered perpendicular to the curtain plane.

        Parameters
        ----------
        line : LineStringLike
            The line to extract the curtain along.
        data_type : str
            The result type to extract the curtain for.
        time : float
            The time to extract the data for. The time must match a timestep that exists within the
            dataset i.e. the routine will not look for the closest time, it will look for the time exactly.

        Returns
        -------
        np.ndarray
            An array containing the extracted curtain data.
        """
        # coerce line
        line = self._coerce_into_line(line)

        # time index
        time_index = self._find_time_index(data_type, time)

        # check cache for results
        if self.cache.contains('curtain', data_type, time_index, self._linestring_as_wkt(line)):
            return self.cache.get('curtain', data_type, time_index, self._linestring_as_wkt(line))

        if data_type.lower() == 'velocity' and not self.is_vector(data_type):
            test = f'vector {data_type}'
            test_a = {x.lower(): x for x in self.data_types()}
            if test in test_a:
                data_type = test_a[test]

        # check cache for line intersections, otherwise calculate
        if self.cache.contains('mesh_line', self._linestring_as_wkt(line)):
            cell_ids, acell, dir_, mid_cell_ids, amid, dir_mid = self.cache.get('mesh_line', self._linestring_as_wkt(line))
        else:
            cell_ids, acell, dir_, mid_cell_ids, amid, dir_mid = self.geom.mesh_line(line)
            self.cache.set(
                (cell_ids, acell, dir_, mid_cell_ids, amid, dir_mid),
                'mesh_line',
                self._linestring_as_wkt(line)
            )

        # get data
        if self.on_vertex(data_type):
            curtain = self.curtain_from_vertex_data(line, cell_ids, acell, dir_mid, data_type, time)
        else:
            curtain = self.curtain_from_cell_data(cell_ids, acell, dir_, data_type, time_index)

        # start and end locations
        self._get_start_end_locations(cell_ids, acell)

        self.cache.set(curtain, 'curtain', data_type, time_index, self._linestring_as_wkt(line))
        return curtain

    def _find_time_index(self, data_type: str, time: float) -> int:
        if data_type.lower() == 'bed elevation':
            return 0
        times = self.times(data_type)
        if len(times) == 1:  # assume static
            return 0
        for i, t in enumerate(times):
            if np.isclose(time, t, atol=0.001, rtol=0.):
                return i
        raise ValueError(f'No time found in Mesh file for {time}.')

    def _map_wet_dry_to_verts(self, wd: np.ndarray) -> np.ndarray:
        cells = self.geom.cells_df.copy()
        cells['wd'] = wd
        m = cells.melt(id_vars=['wd'], value_vars=['n1', 'n2', 'n3', 'n4'])
        ind = np.unique(m[m['wd'] == 1]['value'])
        ind = ind[ind != -1]
        df = pd.DataFrame(self.geom.vertices, columns=['x', 'y', 'z'])
        df['wd'] = False
        df.loc[ind, 'wd'] = True
        return df['wd'].to_numpy()

    def _2d_to_3d_data_types(self, data_type: str) -> tuple[str, str]:
        """Return the bed elevation and water level data types for the given 2d data type so that the 3D profile
        can be constructed. Data type is required so that it can determine if maximums or minimums are being requested.
        """
        if data_type.lower().startswith('max') or data_type.lower().endswith('/maximums'):
            wl_dtype = {'max H', 'Water Level/Maximums', 'max water surface elevation'}
        elif data_type.lower().startswith('min') or data_type.lower().endswith('/minimums'):
            wl_dtype = {'min H', 'Water Level/Minimums', 'min water surface elevation'}
        else:
            wl_dtype = {'Water Level', 'H', 'water surface elevation'}

        wl_dtype = set(self.data_types()).intersection(wl_dtype)
        if wl_dtype:
            wl_dtype = wl_dtype.pop()
        else:
            raise KeyError('Could not determine water level data type for profile extraction.')

        return 'Bed Elevation', wl_dtype

    @staticmethod
    def _project_vector(values: np.ndarray, axis: np.ndarray) -> np.ndarray:
        """Projects vector values onto a given axis.

        Values is ``(N,1,2)`` array of vector values to project. Axis is a ``(N,2)`` array of normalized
        direction vectors onto which to project the values.
        """
        x_axis = axis.reshape(-1, 2)[:,[1, 0]] * [-1, 1]
        y_axis = axis.reshape(-1, 2)
        proj_x = np.sum(values.reshape(-1, 2) * x_axis[:, :2], axis=1)
        proj_y = np.sum(values.reshape(-1, 2) * y_axis[:, :2], axis=1)
        return np.column_stack((proj_x, proj_y))

    def _get_start_end_locations(self, cell_ids: np.ndarray, acell: np.ndarray):
        """Record the start and end locations of the section within the mesh.
        That is each location where the line enters and exits the mesh.

        (used for stitching sections together for CATCHJson output)
        """
        self.start_end_locs.clear()

        inside = cell_ids != -1
        if not inside.any():
            return  # fully outside

        s = acell[:, 0]

        # Find transitions
        inside_int = inside.astype(int)
        diff = np.diff(inside_int)

        # False -> True : entry
        entry_idxs = np.where(diff == 1)[0] + 1

        # True -> False : exit
        exit_idxs = np.where(diff == -1)[0]

        starts = []
        ends = []

        # Line starts inside
        if inside[0]:
            starts.append(s[0])

        # Normal entries
        starts.extend(s[i] for i in entry_idxs)

        # Normal exits
        ends.extend(s[i] for i in exit_idxs)

        # Line ends inside
        if inside[-1]:
            ends.append(s[-1])

        self.start_end_locs = list(zip(starts, ends))
