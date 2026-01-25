import warnings
from abc import abstractmethod
from datetime import datetime
from typing import Union

import numpy as np
import pandas as pd

from .helpers.grid_line import GridLine
from .map_output import MapOutput, PointLocation, Point, LineStringLocation
from .._pytuflow_types import PathLike, TimeLike, TuflowPath

from .pymesh import Cache, LineStringMixin, PointMixin, Bbox2D, Transform2D


GRIDLINE_METHOD = 'optimised'  # 'legacy' or 'optimised'


class Grid(MapOutput, LineStringMixin, PointMixin):
    """Abstract class for grid/raster outputs."""

    def __init__(self, fpath: PathLike | dict):
        d = None
        if isinstance(fpath, dict):
            d, fpath = fpath, None
        else:
            fpath = TuflowPath(fpath)
        super(Grid, self).__init__(fpath)
        self.fpath = fpath
        self._info = pd.DataFrame()
        self.cache = Cache()
        self._cached_timesteps = {}
        self._cached_data = {}
        self._data = None

        if d is None:
            if not TuflowPath(fpath).exists():
                raise FileNotFoundError(self.fpath)
            self._initial_load()
        else:
            dx = d.get('dx', None)
            dy = d.get('dy',    dx)
            ox = d.get('ox', 0.)
            oy = d.get('oy', 0.)
            ncol = d.get('ncol', None)
            nrow = d.get('nrow', None)
            if dx is None or   ncol is None or nrow is None:
                raise ValueError("Insufficient grid information provided.")
            data = d.get('data', None)
            if data is None:
                raise ValueError("No grid data provided.")
            data_type = d.get('data_type', 'arraydata').lower()
            timesteps = d.get('timesteps', -1)
            dtype = d.get('dtype', 'scalar')
            static = timesteps == -1 or (isinstance(timesteps, (list, tuple)) and len(timesteps) == 0)
            if not static:
                if dtype == 'scalar' and data.ndim == 3 and data.shape[0] == len(timesteps):
                    pass  # all good
                elif dtype == 'vector' and data.ndim == 4 and data.shape[0] == len(timesteps):
                    pass  # all good
                else:
                    raise ValueError("Data shape does not match number of timesteps.")
            else:
                if dtype == 'scalar' and data.ndim == 2:
                    pass  # all good
                elif dtype == 'vector' and data.ndim == 3:
                    pass  # all good
                else:
                    raise ValueError("Data shape does not match static data format.")
            self._cached_timesteps[data_type] = set(range(timesteps) if timesteps != -1 else -1)
            self._cached_data[data_type] = data

            self._info = pd.DataFrame(
                {
                    'data_type': [data_type],
                    'type': [dtype],
                    'is_max': [False],
                    'is_min': [False],
                    'static': static,
                    'start': [0 if static else timesteps[0]],
                    'end': [0 if static else timesteps[-1]],
                    'dt': [0 if static else self._calculate_time_step(np.array(timesteps))],
                    'dx': [dx],
                    'dy': [dy],
                    'ox': [ox],
                    'oy': [oy],
                    'ncol': [ncol],
                    'nrow': [nrow],
                    'nodatavalue': [d.get('nodatavalue', np.nan)],
                }
            )

    @property
    def dx(self) -> float:
        """The grid cell size in the x-direction."""
        return float(self._info.iloc[0]['dx'])

    @property
    def dy(self) -> float:
        """The grid cell size in the y-direction."""
        return float(self._info.iloc[0]['dy'])

    @property
    def ox(self) -> float:
        """The x-origin of the grid."""
        return float(self._info.iloc[0]['ox'])

    @property
    def oy(self) -> float:
        """The y-origin of the grid."""
        return float(self._info.iloc[0]['oy'])

    @property
    def ncol(self) -> int:
        """The number of columns in the grid."""
        return int(self._info.iloc[0]['ncol'])

    @property
    def nrow(self) -> int:
        """The number of rows in the grid."""
        return int(self._info.iloc[0]['nrow'])

    @property
    def no_data_value(self) -> float:
        """The no data value for the grid."""
        return float(self._info.iloc[0]['nodatavalue'])

    def _initial_load(self):
        self.name = self.fpath.stem
        with TuflowPath(self.fpath).open_grid() as grid:
            self._info = pd.DataFrame(
                {
                    'data_type': [self.name],
                    'type': ['scalar'],
                    'is_max': [False],
                    'is_min': [False],
                    'static': [True],
                    'start': [0],
                    'end': [0],
                    'dt': [0],
                    'dx': [grid.dx],
                    'dy': [grid.dy],
                    'ox': [grid.ox],
                    'oy': [grid.oy],
                    'ncol': [grid.ncol],
                    'nrow': [grid.nrow],
                    'nodatavalue': [grid.no_data_value],
                }
            )

    def _value(self, dtype: str, idx: tuple | int | np.ndarray | slice) -> float | np.ndarray:
        if self._data is None:
            with TuflowPath(self.fpath).open_grid() as grid:
                self._data = grid.as_array()
        return self._data[idx]

    def _surface(self, dtype: str, time_index: int | np.ndarray | slice) -> np.ndarray:
        is_static = self._is_static(dtype)
        if dtype.lower() not in self._cached_timesteps:
            self._cached_timesteps[dtype.lower()] = set()
            _, _, _, _, ncol, nrow, _ = self._grid_info(dtype)
            shape = (nrow, ncol) if is_static else (len(self.times(dtype)), nrow, ncol)
            self._cached_data[dtype.lower()] = np.full(shape, np.nan, dtype=float)

        # special treatment if time_index is slice(None)
        if not is_static and isinstance(time_index, slice) and time_index == slice(None):
            vals = self._value(dtype, time_index)
            for i, val in enumerate(vals):
                if i not in self._cached_timesteps[dtype.lower()]:
                    self._cached_data[dtype.lower()][i, ...] = val
                    self._cached_timesteps[dtype.lower()].add(i)
            return vals


        if isinstance(time_index, (int, np.int32, np.int64)):
            time_indexes = {time_index}
        elif not is_static and isinstance(time_index, slice):
            start = time_index.start or 0
            stop = time_index.stop or len(self.times(dtype))
            step = time_index.step or 1
            time_indexes = set(range(start, stop, step))
        else:
            time_indexes = time_index

        data = []
        for ti in time_indexes:
            if ti not in self._cached_timesteps[dtype.lower()]:
                idx = slice(None) if is_static else ti
                val = self._value(dtype, idx)
                if is_static:
                    self._cached_data[dtype.lower()][:] = val
                else:
                    self._cached_data[dtype.lower()][idx, ...] = val
                self._cached_timesteps[dtype.lower()].add(time_index)
            else:
                val = self._cached_data[dtype.lower()][ti] if not is_static else self._cached_data[dtype.lower()]
            data.append(val)

        if len(data) == 1:
            return data[0]
        return np.array(data).reshape(len(time_indexes), *data[0].shape)

    def maximum(self, data_types: str | list[str]) -> float | pd.DataFrame:
        """Returns the maximum values for the given data types.

        Some formats store maximum values in the metadata (e.g. XMDF), if this is the case, the maximum values
        will be returned directly from the metadata. If the format does not store maximum values, the maximum
        values will be calculated from the data. In this case, the maximum and temporal datasets will be treated
        as separate. For example, if ``"depth"`` is requested as a data type, it will be calculated
        from the temporal depth data. If ``"max depth"`` is requested, it will be calculated from the maximum
        depth data.

        If multiple data types are requested, a DataFrame will be returned with the data types as the index
        and the maximum values as the column. Vector results will return the magnitude of the vector.

        Parameters
        ----------
        data_types : str | list[str]
            The data types to return the maximum values for.

        Returns
        -------
        float | pd.DataFrame
            The maximum value(s) for the given data type(s).

        Examples
        --------
        Get the maximum water level for a given mesh:

        >>> grid = ... # Assume grid is a loaded Grid result
        >>> grid.maximum('water level')
        45.672345

        Get the maximum velocity and depth for multiple data types:

        >>> grid.maximum(['velocity', 'depth'])
                          maximum
        velocity         1.234567
        depth            5.678901
        """
        df = pd.DataFrame()
        data_types = self._figure_out_data_types(data_types, None)
        for dtype in data_types:
            surface = self._surface(dtype, slice(None))
            mx = np.nanmax(surface)
            if len(data_types) == 1:
                return float(mx)
            df_ = pd.DataFrame([mx], columns=['maximum'], index=[dtype])
            df = pd.concat([df, df_], axis=0) if not df.empty else df_
        return df

    def minimum(self, data_types: str | list[str]) -> float | pd.DataFrame:
        """Returns the minimum values for the given data types.

        Some formats store minimum values in the metadata (e.g. XMDF), if this is the case, the minimum values
        will be returned directly from the metadata. If the format does not store minimum values, the minimum
        values will be calculated from the data. In this case, the minimum and temporal datasets will be treated
        as separate. For example, if ``"depth"`` is requested as a data type, it will be calculated
        from the temporal depth data. If ``"max depth"`` is requested, it will be calculated from the minimum
        depth data.

        If multiple data types are requested, a DataFrame will be returned with the data types as the index
        and the minimum values as the column. Vector results will return the magnitude of the vector.

        Parameters
        ----------
        data_types : str | list[str]
            The data types to return the minimum values for.

        Returns
        -------
        float | pd.DataFrame
            The minimum value(s) for the given data type(s).

        Examples
        --------
        Get the minimum water level for a given mesh:

        >>> grid = ... # Assume grid is a loaded Grid result
        >>> grid.minimum('water level')
        32.547954

        Get the minimum velocity and depth for multiple data types:

        >>> grid.minimum(['velocity', 'depth'])
                    minimum
        velocity         0.
        depth            0.
        """
        df = pd.DataFrame()
        data_types = self._figure_out_data_types(data_types, None)
        for dtype in data_types:
            surface = self._surface(dtype, slice(None))
            mx = np.nanmin(surface)
            if len(data_types) == 1:
                return float(mx)
            df_ = pd.DataFrame([mx], columns=['minimum'], index=[dtype])
            df = pd.concat([df, df_], axis=0) if not df.empty else df_
        return df

    def surface(self, data_type: str = None, time: TimeLike = -1, to_vertex: bool = False, coord_scope: str = 'global') -> pd.DataFrame:
        """Returns the value for every cell/vertex at the specified time.

        Parameters
        ----------
        data_type : str
            The data type to extract the surface data for.
        time : TimeLike
            The time to extract the surface data for.
        to_vertex : bool, optional
            Whether to interpolate the cell data to vertex data. Values are interpolated using a bilnear approach.
        coord_scope : str, optional
            The coordinate scope for the output coordinates. Options are:

            - ``"global"`` (default) - coordinates are unchanged from the input data (i.e. easting/northing or lon/lat)
            - ``"local"`` - coordinates are transformed to a local Cartesian coordinate system and the origin is moved
              to the centre of the grid extent. This can be useful for visualisation purposes, especially when converting
              into 3D formats for viewing in programs like Blender, Unreal Engine, etc

        Returns
        -------
        pd.DataFrame
            The surface data as a DataFrame with columns for the coordinates, value(s), and active mask.

        Examples
        --------
        >>> grid = ... # Assume grid is a loaded Grid result
        >>> df = mesh.surface('water level', 1.5)
                       x            y      value  active
        0     292946.050  6177594.102  53.490948   False
        1     292943.773  6177584.365  53.665874   False
        2     292934.036  6177586.643  53.753918   False
        3     292936.313  6177596.380  53.582664   False
        4     292948.328  6177603.839  53.198586   False
        ...          ...          ...        ...     ...
        5356  293571.392  6178423.468  43.893784   False
        5357  293581.129  6178421.190  44.085411   False
        5358  293590.866  6178418.913  44.279270   False
        5359  293600.603  6178416.635  44.473816   False
        5360  293610.340  6178414.357  44.671116   False
        """
        if data_type is None:
            data_type = self._info.iloc[0]['data_type']
        else:
            data_type = self._figure_out_data_types(data_type, None)[0]
        if self._is_static(data_type):
            idx = -1
        else:
            times = self.times(data_type, fmt='absolute') if isinstance(time, datetime) else self.times(data_type)
            time_index = self._closest_time_index(times, time)
            idx = (time_index,)

        dx, dy, ox, oy, ncol, nrow, ndv = self._grid_info(data_type)
        data = self._surface(data_type, idx)
        mask = (~np.isnan(data)) & (data != ndv)
        data[~mask] = np.nan
        if to_vertex:
            x = ox + np.arange(ncol + 1) * dx
            y = oy + np.arange(nrow + 1) * dy

            # average values to vertices (from cell centres, this is the same as bilinear interpolation)
            # pad the data with the edge values to handle the boundaries
            vertices = np.full((nrow + 2, ncol + 2), np.nan)
            vertices[1:-1, 1:-1] = data
            vertices[0, 1:-1] = data[0, :]
            vertices[-1, 1:-1] = data[-1, :]
            vertices[:, 0] = vertices[:, 1]
            vertices[:, -1] = vertices[:, -2]
            with warnings.catch_warnings():
                # if all surrounding cells are NaN, then the return is NaN and runtime warning is given
                # this is the correct behaviour, so we can ignore the warning
                warnings.simplefilter("ignore", category=RuntimeWarning)
                vertices = np.nanmean(
                    np.stack([
                        vertices[:-1, :-1],
                        vertices[:-1, 1:],
                        vertices[1:, :-1],
                        vertices[1:, 1:]
                    ]),
                    axis=0
                )
            mask = ~np.isnan(vertices)
            data = vertices
        else:
            x = (ox + dx / 2.) + np.arange(ncol) * dx
            y = (oy + dy / 2.) + np.arange(nrow) * dy


        if coord_scope == 'local':
            xy = np.column_stack((x, y))
            bbox = Bbox2D(xy)
            shift = (
                -bbox.x.min - bbox.width / 2,
                -bbox.y.min - bbox.height / 2
            )
            trans = Transform2D(translate=shift)
            x, y = trans.transform(xy).T

        xx, yy = np.meshgrid(x, y)

        df = pd.DataFrame({'x': xx.flatten(), 'y': yy.flatten(), 'value': data.flatten(), 'active': mask.flatten()})
        return df

    def data_point(self, locations: PointLocation, data_types: str | list[str] | None = None,
                   time: TimeLike = -1) -> float | tuple[float, float] | pd.DataFrame:
        """Extracts the data value for the given point locations and data types at the specified time.

        The ``locations`` can be a single point in the form of a tuple ``(x, y)`` or in the Well Known Text (WKT)
        format. It can also be a list of points, or a dictionary of points where the key will be used in the column name
        in the resulting DataFrame.

        The ``locations`` argument can also be a single GIS file path e.g. Shapefile or GPKG (but any format supported
        by GDAL is also supported). GPKG's should follow the TUFLOW convention if specifying the layer name within
        the database ``database.gpkg >> layer``. If the GIS layer has a field called ``name``, ``label``, or ``ID``
        then this will be used as the column name in the resulting DataFrame.

        The returned value will be a single float if a single location and data type is provided, or a tuple if the
        data type is a vector result type. If multiple locations and/or data types are provided, a DataFrame will
        be returned with the data types as columns and the point locations as the index.

        Parameters
        ----------
        locations : Point | list[Point] | dict[str, Point] | PathLike
            The location to extract the data for.
        data_types : str | list[str]
            The data types to extract the data for.
        time : TimeLike
            The time to extract the data for.

        Returns
        -------
        float | tuple[float, float] | pd.DataFrame
            The data value(s) for the given location(s) and data type(s).

        Examples
        --------
        Get the water level data for a given point defined as ``(x, y)``:

        >>> grid = ... # Assume grid is a loaded grid result instance
        >>> grid.data_point((293250, 6178030), 'water level', 1.5)
        42.723076

        Get the maximum water level and depth for multiple points defined in a shapefile. Time is passed as ``-1`` since
        it is a static dataset (it could be any time value since it won't affect the result):

        >>> grid.data_point('/path/to/points.shp', ['max water level', 'max depth'], -1)
              max water level  max depth
        pnt1        40.501997   2.785571
        pnt2        43.221862   3.450053
        """
        pnts = self._translate_point_location(locations)
        if data_types is None:
            data_types = [self._info.iloc[0]['data_type']]
        else:
            data_types = self._figure_out_data_types(data_types, None)
        rows = []
        values1 = []
        for name, pnt in pnts.items():
            rows.append(name)
            values2 = []
            for dtype in data_types:
                dx, dy, ox, oy, ncol, nrow, _ = self._grid_info(dtype)
                n, m = self._get_xy_index(pnt, dx, dy, ox, oy, ncol, nrow)
                is_static = self._is_static(dtype)
                if not is_static:
                    times = self.times(dtype, fmt='absolute') if isinstance(time, datetime) else self.times(dtype)
                    timeidx = self._closest_time_index(times, time)
                    idx = (timeidx, n, m)
                else:
                    idx = (n, m)
                val = float(self._value(dtype, idx))
                if len(data_types) == 1 and len(pnts) == 1:
                    return val
                values2.append(val)
            values1.append(values2)
        df = pd.DataFrame(values1[::-1]).rename(columns=dict(enumerate(data_types)), index=dict(enumerate(rows[::-1])))
        return df

    def time_series(self, locations: PointLocation, data_types: str | list[str] | None,
                    time_fmt: str = 'relative', **kwargs) -> pd.DataFrame:
        """Extracts time-series data for the given locations and data types.

        The ``locations`` can be a single point in the form of a tuple ``(x, y)`` or in the Well Known Text (WKT)
        format. It can also be a list of points, or a dictionary of points where the key will be used in the column name
        in the resulting DataFrame.

        The ``locations`` argument can also be a single GIS file path e.g. Shapefile or GPKG (but any format supported
        by GDAL is also supported). GPKG's should follow the TUFLOW convention if specifying the layer name within
        the database ``database.gpkg >> layer``. If the GIS layer has a field called ``name``, ``label``, or ``ID``
        then this will be used as the column name in the resulting DataFrame.

        The returned DataFrame will use a single time index and the column names will be in the form of:
        ``label/data_type`` e.g. ``pnt1/water level``.

        Parameters
        ----------
        locations : Point | list[Point] | dict[str, Point] | PathLike
            The location to extract the time series data for.
        data_types : str | list[str]
            The data types to extract the time series data for.
        time_fmt : str, optional
            The format for the time values. Options are ``relative`` or ``absolute``.

        Returns
        -------
        pd.DataFrame
            The time series data.

        Examples
        --------
        Get the water level time-series data for a given point defined in a shapefile:

        >>> grid = ... # Assume grid is a loaded grid result instance
        >>> grid.time_series('/path/to/point.shp', 'water level')
        time     pnt1/water level
        0.00000               NaN
        0.08333               NaN
        0.16670               NaN
        0.25000               NaN
        0.33330         44.125675
        0.41670         44.642513
        0.50000         45.672554
        0.58330         46.877666
        """
        df = pd.DataFrame()
        pnts = self._translate_point_location(locations)
        data_types = self._figure_out_data_types(data_types, 'temporal')
        for name, pnt in pnts.items():
            wkt = self._point_as_wkt(self._coerce_into_point(pnt))
            df1 = pd.DataFrame()
            for dtype in data_types:
                if self.cache.contains('time_series', dtype, wkt):
                    vals = self.cache.get('time_series', dtype, wkt)
                else:
                    dx, dy, ox, oy, ncol, nrow, _ = self._grid_info(dtype)
                    n, m = self._get_xy_index(pnt, dx, dy, ox, oy, ncol, nrow)
                    if n is None:
                        continue
                    vals = self._value(dtype, (slice(None), n, m))
                    self.cache.set(vals, 'time_series', dtype, wkt)
                vals = np.column_stack((self.times(dtype, fmt=time_fmt), vals))
                df2 = pd.DataFrame(vals, columns=['time', f'{name}/{dtype}'])
                df2.set_index('time', inplace=True)
                df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2
            df = pd.concat([df, df1], axis=1) if not df.empty else df1

        return df

    def section(self, locations: LineStringLocation, data_types: Union[str, list[str], None] = None,
                time: TimeLike = -1, **kwargs) -> pd.DataFrame:
        """Extracts section data for the given locations and data types.

        The ``locations`` can be a list of ``x, y`` tuple points, or a Well Known Text (WKT) line string. It can also
        be a dictionary of key, line-string pairs where the key is the name that will be used in the column name in
        the resulting DataFrame.

        The ``locations`` argument can also be a single GIS file path e.g. Shapefile or GPKG (but any format supported
        by GDAL is also supported). GPKG's should follow the TUFLOW convention if specifying the layer name within
        the database ``database.gpkg >> layer``. If the GIS layer has a field called ``name``, ``label``, or ``ID``
        then this will be used as the column name in the resulting DataFrame.

        The resulting DataFrame will use multi-index columns since the data is not guaranteed to have the same
        index. The level 1 index will be the label, and the level 2 index will be the data type. The offset will
        always be the first column within the level 2 index.

        Parameters
        ----------
        locations : list[Point] | str | PathLike
            The location to extract the section data for.
        data_types : str | list[str]
            The data types to extract the section data for.
        time : TimeLike
            The time to extract the section data for.

        Returns
        -------
        pd.DataFrame
            The section data.

        Examples
        --------
        Get a water level section from a line defined in a shapefile at time 0.5 hrs:

        >>> grid = ... # Assume grid is a loaded grid result instance
        >>> grid.section('/path/to/line.shp', 'water level', 0.5)
               offset  Line 1/water level
        0    0.000000           45.994362
        1    1.495967           45.994362
        2    1.495967           45.636654
        3    4.159921           45.636654
        4    4.159921           45.592628
        5    6.804385           45.592628
        6    6.804385           45.624744
        7    6.823876           45.624744
        8    6.823876           45.583813
        9    9.487831           45.583813
        10   9.487831           45.560959
        """
        df = pd.DataFrame()
        lines = self._translate_line_string_location(locations)
        if data_types is None:
            data_types = [self._info.iloc[0]['data_type']]
        else:
            data_types = self._figure_out_data_types(data_types, None)
        for name, line in lines.items():
            df1 = pd.DataFrame()
            wkt = self._linestring_as_wkt(self._coerce_into_line(line))
            if GRIDLINE_METHOD == 'legacy':
                gridline = GridLine(*self._grid_info(data_types[0]))
                nm = np.array([(x.offsets[0], x.offsets[1], x.n, x.m) for x in gridline.cells_along_line(line)])
                mask = np.full(nm.shape[0], True, dtype=bool)
                rows = nm[:, 2].flatten().astype(int)
                cols = nm[:, 3].flatten().astype(int)
                offsets = nm[:, :2].flatten()
            else:
                if self.cache.contains('gridline', wkt):
                    nm, intersections = self.cache.get('gridline', wkt)
                else:
                    nm, intersections = self.gridline(line, *self._grid_info(data_types[0]))
                    self.cache.set((nm, intersections), 'gridline', wkt)
                mask = nm[:, 0] >= 0
                rows = nm[mask, 0].flatten().astype(int)
                cols = nm[mask, 1].flatten().astype(int)
                offsets = np.repeat(intersections[:, 0], 2)[1:-1]
            for dtype in data_types:
                val = np.full(nm.shape[0], np.nan)
                if self._is_static(dtype):
                    val[mask] = self._surface(dtype, -1)[rows, cols]
                else:
                    times = self.times(dtype, fmt='absolute') if isinstance(time, datetime) else self.times(dtype)
                    timeidx = self._closest_time_index(times, time, method='closest')
                    val[mask] = self._surface(dtype, timeidx)[rows, cols]
                df2 = pd.DataFrame(np.repeat(val, 2), columns=[dtype], index=offsets)
                df2.index.name = 'offset'
                df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2

            df = self._merge_line_dataframe(df, df1, name, reset_index=True)

        return df

    def curtain(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Not supported for ``Grid`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support curtain plotting.')

    def profile(self, locations: PointLocation, data_types: Union[str, list[str]],
                time: TimeLike, **kwargs) -> pd.DataFrame:
        """Not supported for ``Grid`` results. Raises a :code:`NotImplementedError`."""
        raise NotImplementedError(f'{__class__.__name__} does not support vertical profile plotting.')

    @staticmethod
    def _get_xy_index(pnt: Point, dx: float, dy: float, ox: float, oy: float, ncol: int, nrow: int):
        x, y = pnt
        if x < ox or x > ox + ncol * dx or pnt[1] < oy or pnt[1] > oy + nrow * dy:
            return None, None
        m = int((x - ox) / dx)
        n = int((y - oy) / dy)
        return n, m

    def _grid_info(self, dtype: str) -> tuple[float, float, float, float, int, int, float]:
        return self._info[self._info['data_type'] == dtype].iloc[0, :][['dx', 'dy', 'ox', 'oy', 'ncol', 'nrow', 'nodatavalue']].values

    def _is_static(self, dtype: str) -> bool:
        return self._info[self._info['data_type'] == dtype].iloc[0]['static']

    @staticmethod
    def gridline(line: list[tuple[float, float]],
                 dx: float,
                 dy: float,
                 ox: float,
                 oy: float,
                 nrow: int,
                 ncol: int,
                 *args, **kwargs
                 ) -> tuple[np.ndarray, np.ndarray]:
        cells = np.array([])
        intersections = np.array([])
        line = LineStringMixin._coerce_into_line(line)
        for i in range(1, line.shape[0]):
            seg = line[i - 1:i + 1, :2]
            cells_, intersections_ = Grid.gridline_segment(seg, dx, dy, ox, oy, nrow, ncol)

            if cells.size == 0:
                cells = cells_
                intersections = intersections_
            else:
                if cells_.size > 0:
                    cells = np.vstack([cells, cells_])
                if intersections_.size > 0:
                    intersections_[:, 0] += intersections[-1, 0]
                    intersections = np.vstack([intersections, intersections_[1:, :]])

        return cells, intersections

    @staticmethod
    def gridline_segment(line: np.ndarray,
                         dx: float,
                         dy: float,
                         ox: float,
                         oy: float,
                         nrow: int,
                         ncol: int,
                         ) -> tuple[np.ndarray, np.ndarray]:
        def clip_segment_to_aabb(x0_, y0_, x1_, y1_, xmin_, xmax_, ymin_, ymax_):
            dx = x1_ - x0_
            dy = y1_ - y0_

            p = np.array([-dx, dx, -dy, dy])
            q = np.array([x0_ - xmin_, xmax_ - x0_, y0_ - ymin_, ymax_ - y0_])

            t0, t1 = 0.0, 1.0

            for pi, qi in zip(p, q):
                if pi == 0:
                    if qi < 0:
                        return None
                else:
                    t = qi / pi
                    if pi < 0:
                        t0 = max(t0, t)
                    else:
                        t1 = min(t1, t)

            if t0 > t1:
                return None

            return t0, t1

        p0 = line[0]
        p1 = line[1]
        x0, y0 = p0
        x1, y1 = p1

        # Direction
        vx = x1 - x0
        vy = y1 - y0

        # Grid extent
        xmin, xmax = ox, ox + ncol * dx
        ymin, ymax = oy, oy + nrow * dy

        clip = clip_segment_to_aabb(x0, y0, x1, y1, xmin, xmax, ymin, ymax)

        intersections = []
        cells = []

        if clip is None:  # line is completely outside
            intersections = np.array([
                [x0, y0, 0.0],
                [x1, y1, 1.0]
            ])
            cells = np.array([[-1, -1]])
            return cells, intersections

        t0, t1 = clip

        # Add outside start
        if t0 > 0:
            intersections.append([x0, y0])
            cells.append([-1, -1])

        x_lines = ox + np.arange(0, ncol + 1) * dx
        y_lines = oy + np.arange(0, nrow + 1) * dy

        t_x = (x_lines - x0) / vx if vx != 0 else np.empty(0)
        t_y = (y_lines - y0) / vy if vy != 0 else np.empty(0)

        t_cross = np.concatenate([t_x, t_y])
        t_cross = t_cross[(t_cross > t0) & (t_cross < t1)]
        t_cross = np.unique(t_cross)
        t_cross.sort()

        # Build full ordered t sequence for inside portion
        t_inside = np.concatenate([[t0], t_cross, [t1]])

        # Entry point
        intersections.append([x0 + t0 * vx, y0 + t0 * vy])

        for ta, tb in zip(t_inside[:-1], t_inside[1:]):
            tmid = 0.5 * (ta + tb)
            xm = x0 + tmid * vx
            ym = y0 + tmid * vy

            col = int(np.floor((xm - ox) / dx))
            row = int(np.floor((ym - oy) / dy))

            cells.append([row, col])
            intersections.append([x0 + tb * vx, y0 + tb * vy])

        # Add outside end
        if t1 < 1:
            intersections.append([x1, y1])
            cells.append([-1, -1])

        intersections = np.array(intersections)
        intersections = np.column_stack((
            np.linalg.norm(intersections - np.array([x0, y0]), axis=1),
            intersections
        ))

        return np.array(cells), intersections
