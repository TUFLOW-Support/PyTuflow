from datetime import datetime, timezone

import numpy as np
try:
    import pandas as pd
except ImportError:
    from .stubs import pandas as pd

from . import (LineStringMixin, LineStringLike, PointMixin, PointLike, VertexDataMixin, CellDataMixin, Cache,
               PyMeshGeometry, PyDataExtractor, NCEngine, H5Engine, SoftLoadMixin, QgisMeshGeometry)

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

try:
    from qgis.core import QgsApplication
except ImportError:
    from .stubs.qgis.core import QgsApplication


class PyMesh(VertexDataMixin, CellDataMixin, PointMixin, LineStringMixin, SoftLoadMixin):
    DRIVER_SOURCE = 'python'

    def __init__(self, *args, **kwargs):
        self._init_soft_load()
        self.cache = Cache()
        self.name = ''
        self.geom: PyMeshGeometry | QgisMeshGeometry = PyMeshGeometry('')
        self.extractor: PyDataExtractor = PyDataExtractor()
        self.has_inherent_reference_time = False
        self.reference_time = datetime(1990, 1, 1, tzinfo=timezone.utc)
        self.start_end_locs = []  # used by CATCHJson to stitch sections together

        self._cached_data_types = {}
        self._data_types = []
        self._standardised_data_types = []
        self._cells_4_mapping = None

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} {self.name}>'

    def __contains__(self, item: str) -> bool:
        return item in self.data_types()

    @staticmethod
    def available() -> bool:
        return '.stubs' not in pv.__name__ and (H5Engine.available() or NCEngine.available())

    @staticmethod
    def qgis_available() -> bool:
        return '.stubs' not in QgsApplication.__module__

    @staticmethod
    def qgis_initialized() -> bool:
        return QgsApplication.instance() is not None

    @staticmethod
    def pv_available() -> bool:
        return '.stubs' not in pv.__name__

    @staticmethod
    def external_engine_available() -> bool:
        return H5Engine.available() or NCEngine.available()

    def clear_cache(self):
        self.cache.clear()
        self._data_types.clear()
        self._standardised_data_types.clear()

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
        if self.cache.contains('translate_data_type', data_type):
            return self.cache.get('translate_data_type', data_type)
        from ..map_output import MapOutput
        dtype = MapOutput._get_standard_data_type_name(data_type)
        try:
            data_type = self.data_types()[self._standardised_data_types.index(dtype)]
            self.cache.set((data_type,), 'translate_data_type', data_type)
        except ValueError:
            pass
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
        data_type = self.translate_data_type(data_type)[0]
        if self.cache.contains('times', data_type):
            return self.cache.get('times', data_type)
        times = self.extractor.times(data_type)
        self.cache.set(times, 'times', data_type)
        return times

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
            from ..map_output import MapOutput
            self._data_types = ([self.geom.data_type] if self.geom.data_type else []) + self.extractor.data_types()
            self._standardised_data_types = [MapOutput._get_standard_data_type_name(x) for x in self._data_types]
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
        if self.cache.contains('reference_time', data_type):
            return self.cache.get('reference_time', data_type)
        ref_time = self.extractor.reference_time(self.translate_data_type(data_type)[0])
        self.cache.set(ref_time, 'reference_time', data_type)
        return ref_time

    def maximum(self, data_type: str, depth_averaging: str = None,
                split_vector_components: bool = False) -> float | tuple[float, float]:
        """Returns the maximum value for the specified result type. The full path the result type must be specified,
        for example, "depth" will return the maximum for the temporal depth results. If searching for the absolute
        maximum (the maximum value in the maximum output surface) then "depth/maximums" must be used (if applicable).

        Parameters
        ----------
        data_type : str
            The type of result to return the maximum value for.
        depth_averaging : str, optional
            The depth averaging method to use when extracting 3D data.
        split_vector_components : bool, optional
            Returns the maximum of the vector components separately rather than the magnitude.

        Returns
        -------
        float | tuple[float, float]
            The maximum value for the specified result type.
        """
        if not self.is_3d(data_type):
            depth_averaging = None
        if not self.is_vector(data_type):
            split_vector_components = False

        if self.cache.contains('maximum', data_type, depth_averaging, split_vector_components):
            return self.cache.get('maximum', data_type, depth_averaging, split_vector_components)
        if data_type.lower() in ['bed elevation', 'bed level']:
            mx = float(np.max(self.geom.vertex_position(slice(None), get_z=True)[:, 2]))
            self.cache.set('maximum', data_type, mx)
            return mx

        try:  # some formats store maximums/minimums in the metadata
            mx = self.extractor.maximum(self.translate_data_type(data_type)[0], depth_averaging, split_vector_components)
        except NotImplementedError:  # need to extract full data to find maximum
            if self.on_vertex(data_type):
                data, mask = self.vertex_data(data_type, slice(None))
            else:
                data, mask = self.cell_data(data_type, slice(None), depth_averaging)
            if self.is_vector(data_type) and not split_vector_components:
                data = np.linalg.norm(data, axis=1 if data.ndim == 2 else 2)

            if self.is_vector(data_type) and split_vector_components:
                mx = (float(data[mask].max(axis=0)[0]), float(data[mask].max(axis=0)[1]))
            else:
                mx = float(data[mask].max())

        self.cache.set(mx, 'maximum', data_type, depth_averaging, split_vector_components)
        return mx

    def minimum(self, data_type: str, depth_averaging: str = None,
                split_vector_components: bool = False) -> float | tuple[float, float]:
        """Returns the minimum value for the specified result type. The full path the result type must be specified,
        for example, "depth" will return the minimum for the temporal depth results. If searching for the absolute
        minimum (the minimum value in the minimum output surface) then "minimums/depth" must be used (if applicable).

        Parameters
        ----------
        data_type : str
            The type of result to return the maximum value for.
        depth_averaging : str, optional
            The depth averaging method to use when extracting 3D data.
        split_vector_components : bool, optional
            Returns the minimum of the vector components separately rather than the magnitude.

        Returns
        -------
        float | tuple[float, float]
            The maximum value for the specified result type.
        """
        if not self.is_3d(data_type):
            depth_averaging = None
        if not self.is_vector(data_type):
            split_vector_components = False

        if self.cache.contains('minimum', data_type, depth_averaging, split_vector_components):
            return self.cache.get('minimum', data_type, depth_averaging, split_vector_components)
        if data_type.lower() in ['bed elevation', 'bed level']:
            mn = float(np.min(self.geom.vertex_position(slice(None), get_z=True)[:, 2]))
            self.cache.set('minimum', data_type, mn)
            return mn

        try:  # some formats store maximums/minimums in the metadata
            mn = self.extractor.minimum(self.translate_data_type(data_type)[0], depth_averaging, split_vector_components)
        except NotImplementedError:  # need to extract full data to find maximum
            if self.on_vertex(data_type):
                data, mask = self.vertex_data(data_type, slice(None))
            else:
                data, mask = self.cell_data(data_type, slice(None), depth_averaging)
            if self.is_vector(data_type) and not split_vector_components:
                data = np.linalg.norm(data, axis=1 if data.ndim == 2 else 2)

            if self.is_vector(data_type):
                mn = (float(data[mask].min(axis=0)[0]), float(data[mask].min(axis=0)[1]))
            else:
                mn = float(data[mask].min())

        self.cache.set(mn, 'minimum', data_type, depth_averaging, split_vector_components)
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
        if self.cache.contains('is_vector', data_type):
            return self.cache.get('is_vector', data_type)
        vector = data_type.lower() not in ['bed elevation', 'bed level'] and self.extractor.is_vector(self.translate_data_type(data_type)[0])
        self.cache.set(vector, 'is_vector', data_type)
        return vector

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
        if self.cache.contains('is_static', data_type):
            return self.cache.get('is_static', data_type)
        static = data_type.lower() in ['bed elevation', 'bed level'] or self.extractor.is_static(self.translate_data_type(data_type)[0])
        self.cache.set(static, 'is_static', data_type)
        return static

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
        if data_type.lower() == 'bed elevation':
            return True
        if self.cache.contains('on_vertex', data_type):
            return self.cache.get('on_vertex', data_type)
        vertex = self.extractor.on_vertex(self.translate_data_type(data_type)[0])
        self.cache.set(vertex, 'on_vertex', data_type)
        return vertex

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
        if self.cache.contains('is_3d', data_type):
            return self.cache.get('is_3d', data_type)
        is_3d = self.extractor.is_3d(self.translate_data_type(data_type)[0])
        self.cache.set(is_3d, 'is_3d', data_type)
        return is_3d

    def cell_index(self, cell_id: int | list[int] | np.ndarray, data_type: str) -> np.ndarray:
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
        return self.extractor.cell_index(cell_id, self.translate_data_type(data_type)[0])

    def zlevel_count(self, cell_idx2: int | np.ndarray | list[int] | slice) -> int | np.ndarray | list[int]:
        """Returns the number of vertical levels for the given 2D cell index.

        Parameters
        ----------
        cell_idx2 : int | np.ndarray | list[int]
            The 2D cell index to get the number of vertical levels for.

        Returns
        -------
        int | np.ndarray | list[int]
            The number of vertical levels for the given 2D cell index.
        """
        return self.extractor.zlevel_count(cell_idx2)

    def zlevels(self, time_index: int, nlevels: int, cell_idx2: int | np.ndarray,
                cell_idx3: int | np.ndarray) -> np.ndarray:
        """Returns the vertical levels for the given time index, number of levels, 2D cell index, and 3D cell index.

        Parameters
        ----------
        time_index : int
            The time index to get the vertical levels for.
        nlevels : int
            The number of vertical levels.
        cell_idx2 : int | np.ndarray
            The 2D cell index.
        cell_idx3 : int | np.ndarray
            The 3D cell index.

        Returns
        -------
        np.ndarray
            The vertical levels for the given parameters.
        """
        return self.extractor.zlevels(time_index, nlevels, cell_idx2, cell_idx3)

    def surface(self,
                data_type: str,
                time: float | datetime,
                depth_averaging: str = 'sigma&0&1',
                to_vertex: bool = False,
                coord_scope: str = 'global',
                time_index: int = -1
                ) -> tuple[np.ndarray, np.ndarray]:
        """Returns the surface data for the specified data type and time.

        Parameters
        ----------
        data_type : str
            The result type to extract the surface for.
        time : float | datetime
            The time to extract the data for.
        depth_averaging : str, optional
            The depth averaging method to use when extracting 3D data. Options are:

            - `singlelevel`
            - `multilevel`
            - `depth`
            - `height`
            - `elevation`
            - `sigma` (default)

        to_vertex : bool, optional
            Whether to return data on vertices. If the data already exists on vertices, then this parameter has no
            effect. If the data is on cells and this parameter is set to ``True``, then data will be interpolated
            to the vertices.
        coord_scope : str, optional
            The coordinate scope to return the data in. Options are:

            - ``"global"``: returns data in global coordinates (i.e. the original coordinate system of the mesh).
            - ``"local"``: returns data in local coordinates. For cartesian coordinates, the origin (0, 0) is shifted
              to the centre of the mesh bounding box. For geographic coordinates, the local coordinates are
              the coordinates converted into a projected system.
        time_index : int, optional
            The time index to return the data for. This value will take precedence over the ``time``
            parameter if a value greater than ``-1`` is provided.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            A tuple containing the data array and a mask array containing information on whether the vertex/cell is wet.
        """
        with self.extractor.open():
            if self.is_static(data_type):
                time_index = -1
            else:
                time_index = time_index if time_index >= 0 else self._find_time_index(data_type, time)

            if self.on_vertex(data_type):
                to_vertex = True
            if not self.is_3d(data_type):
                depth_averaging = None

            if self.cache.contains('surface', data_type, time_index, depth_averaging, to_vertex):
                return self.cache.get('surface', data_type, time_index, depth_averaging, to_vertex)

            if self.on_vertex(data_type):
                data, mask = self.vertex_data(data_type, time_index)
            else:
                data, mask = self.cell_data(data_type, time_index, depth_averaging, to_vertex)

            if to_vertex:
                pos = self.geom.vertex_position(slice(None), scope=coord_scope, get_z=True)
            else:
                pos = self.geom.cell_position(slice(None), scope=coord_scope)

            data = np.column_stack((pos[:, :2], data.flatten() if not self.is_vector(data_type) else data.reshape(-1, 2)))
            mask = mask.flatten()

            self.cache.set((data, mask), 'surface', data_type, time_index, depth_averaging, to_vertex)
            return data, mask

    def data_point(self,
                   point: PointLike,
                   data_type: str,
                   time: float = 0.,
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
        with self.extractor.open():
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
        with self.extractor.open():
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
        with self.extractor.open():
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
        with self.extractor.open():
            # coerce line
            line = self._coerce_into_line(line)

            # time index
            time_index = self._find_time_index(data_type, time)

            # check cache for results
            if self.cache.contains('curtain', data_type, time_index, self._linestring_as_wkt(line)):
                return self.cache.get('curtain', data_type, time_index, self._linestring_as_wkt(line))

            if data_type.lower() in ['velocity', 'max velocity', 'min velocity'] and not self.is_vector(data_type):
                if data_type.lower() == 'velocity':
                    test = f'vector {data_type}'
                elif data_type.lower() == 'max velocity':
                    test = 'vector velocity/maximums'
                else:
                    test = 'vector velocity/minimums'
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
            self._get_start_end_locations(cell_ids, acell)

            self.cache.set(curtain, 'curtain', data_type, time_index, self._linestring_as_wkt(line))
            return curtain

    def flux(self, line: LineStringLike, data_type: str, use_unit_flow: bool) -> np.ndarray:
        """Returns the flux across a line. The data_type can be "q"/"unit flow" and the flux will be calculated
        using unit flow and the flow width. It can also be any other scalar result type
        and the flux will be calculated by multiplying data type with the depth the velocity to obtain a flux.
        E.g. it's possible to calculate the volume of sediment or salt by passing in a sediment or salinity
        data type. Passing in an empty string will essentially calculate the volume flux, although using 'unit flow'
        is recommended if it is available.

        Parameters
        ----------
        line : LineStringLike
            The line to extract the flux for.
        data_type : str
            The result type to extract the flux for. If "q" is specified, then the flux will be calculated using
            solely the "q" data type. If a scalar data type is passed in, then the flux will be calculated
            with help from the velocity result. Other vector data types are not supported.
        use_unit_flow : bool
            Use unit flow.

        Returns
        -------
        np.ndarray
            An array containing the extracted flux across the line.
        """
        _ = self.data_types()
        data_types = self._standardised_data_types
        # Checks
        unit_flow = ''
        if use_unit_flow:
            # check to see if this result type is available
            if not 'unit flow' in data_types:
                raise ValueError('Data type "unit flow" is not available for flux calculation.')
            unit_flow = 'unit flow'
            if not self.is_vector('unit flow'):
                if 'vector unit flow' not in data_types:
                    raise ValueError('Data type "unit flow" is not a vector and could not find a "vector unit flow".')
                unit_flow = 'vector unit flow'
        else:
            if data_type:
                if self.is_static(data_type):
                    raise ValueError('data type for flux calculation cannot be static')
                if self.is_vector(data_type):
                    raise ValueError('data type for flux calculation must be unit flow or a scalar type')
            # check for depth and velocities - if velocity is called Vector Velocity like in a TUFLOW HPC XMDF output,
            # then searching for Velocity is still good enough since these are created together
            if 'velocity' not in data_types:
                raise ValueError('velocity not found in available data types')
            elif not self.on_vertex('velocity'):
                # don't need to check depths, the layer thickness are defined in cell centred format
                if self.is_3d('velocity') and data_type and not self.is_3d(data_type):
                    raise ValueError('data_type must be 3D for 3D results')
            elif 'depth' not in data_types:
                raise ValueError('depth not found in available data types')

        with self.extractor.open():
            # coerce line
            line = self._coerce_into_line(line)

            if self.cache.contains('flux', data_type, self._linestring_as_wkt(line), use_unit_flow):
                return self.cache.get('flux', data_type, self._linestring_as_wkt(line), use_unit_flow)

            # check cache for line intersections, otherwise calculate
            if self.cache.contains('mesh_line', self._linestring_as_wkt(line)):
                cell_ids, acell, dir_, mid_cell_ids, amid, dir_mid = self.cache.get('mesh_line',
                                                                                    self._linestring_as_wkt(line))
            else:
                cell_ids, acell, dir_, mid_cell_ids, amid, dir_mid = self.geom.mesh_line(line)
                self.cache.set(
                    (cell_ids, acell, dir_, mid_cell_ids, amid, dir_mid),
                    'mesh_line',
                    self._linestring_as_wkt(line)
                )

            # get data
            if self.on_vertex('velocity'):
                flux = self.flux_from_vertex_data(line, cell_ids, acell, dir_mid, data_type, unit_flow)
            else:
                flux = self.flux_from_cell_data(cell_ids, acell, dir_, data_type, unit_flow)

            self.cache.set(flux, 'flux', data_type, self._linestring_as_wkt(line), use_unit_flow)
            return flux

    def _find_time_index(self, data_type: str, time: float | datetime) -> int:
        if data_type.lower() in ['bed elevation', 'bed level']:
            return 0
        if isinstance(time, datetime):
            if time.tzinfo is None:
                time = time.replace(tzinfo=timezone.utc)
            time = (time - self.reference_time).total_seconds() / 3600.
        times = self.times(data_type)
        if len(times) == 1:  # assume static
            return 0
        diff = np.array([x - time for x in times])
        return int(np.abs(diff).argmin())

    def _map_wet_dry_to_verts(self, wd: np.ndarray) -> np.ndarray:
        cells = self.geom.cells_df.copy()
        cells['wd'] = wd
        m = cells.melt(id_vars=['wd'], value_vars=['n1', 'n2', 'n3', 'n4'])
        ind = np.unique(m[m['wd'] == 1]['value'])
        ind = ind[ind != -1]
        df = pd.DataFrame(self.geom.vertex_position(slice(None), get_z=True), columns=['x', 'y', 'z'])
        df['wd'] = False
        df.loc[ind, 'wd'] = True
        return df['wd'].to_numpy()

    def map_cell_data_to_vertexes(self, cell_data: np.ndarray, mapping_func: str) -> np.ndarray:
        if self._cells_4_mapping is None:
            self._cells_4_mapping = self.geom.cells_df.copy()
        cells = self._cells_4_mapping
        cells['cell_data'] = cell_data
        m = cells.melt(id_vars=['cell_data'], value_vars=['n1', 'n2', 'n3', 'n4'])
        ind = m[m['value'] != -1][['cell_data', 'value']]
        if mapping_func == 'max':
            return ind.groupby(by='value').max().to_numpy().reshape((-1,))
        elif mapping_func == 'mean':
            return ind.groupby(by='value').mean().to_numpy().reshape((-1,))

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
