from abc import abstractmethod
from datetime import datetime
from typing import Union

import numpy as np
import pandas as pd

from .helpers.grid_line import GridLine
from .map_output import MapOutput, PointLocation, Point, LineStringLocation
from .._pytuflow_types import PathLike, TimeLike


class Grid(MapOutput):
    """Abstract class for grid/raster outputs."""

    def __init__(self, fpath: PathLike):
        super().__init__(fpath)
        self._info = pd.DataFrame()

    @abstractmethod
    def _value(self, dtype: str, idx: tuple | int | np.ndarray | slice) -> float | np.ndarray:
        pass

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
        data_types = self._figure_out_data_types(data_types, None)
        for dtype in data_types:
            pass

    def data_point(self, locations: PointLocation, data_types: str | list[str],
                   time: TimeLike) -> float | tuple[float, float] | pd.DataFrame:
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
            df1 = pd.DataFrame()
            for dtype in data_types:
                dx, dy, ox, oy, ncol, nrow, _ = self._grid_info(dtype)
                n, m = self._get_xy_index(pnt, dx, dy, ox, oy, ncol, nrow)
                if n is None:
                    continue
                vals = self._value(dtype, (slice(None), n, m))
                vals = np.column_stack((self.times(dtype, fmt=time_fmt), vals))
                df2 = pd.DataFrame(vals, columns=['time', f'{name}/{dtype}'])
                df2.set_index('time', inplace=True)
                df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2
            df = pd.concat([df, df1], axis=1) if not df.empty else df1

        return df

    def section(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike, **kwargs) -> pd.DataFrame:
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
        data_types = self._figure_out_data_types(data_types, None)
        for name, line in lines.items():
            df1 = pd.DataFrame()
            for dtype in data_types:
                gridline = GridLine(*self._grid_info(dtype))
                nm = np.array([(x.offsets[0], x.offsets[1], x.n, x.m) for x in gridline.cells_along_line(line)])
                rows = nm[:, 2].flatten().astype(int)
                cols = nm[:, 3].flatten().astype(int)
                if self._is_static(dtype):
                    idx = (rows, cols)
                else:
                    times = self.times(dtype, fmt='absolute') if isinstance(time, datetime) else self.times(dtype)
                    timeidx = self._closest_time_index(times, time)
                    idx = (timeidx, rows, cols)

                val = self._value(dtype, idx)[rows, cols]
                offsets = nm[:, :2].flatten()
                val = np.column_stack((offsets, np.repeat(val, 2)))
                df2 = pd.DataFrame(val, columns=['offset', f'{name}/{dtype}'])
                df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2

            df = pd.concat([df, df1], axis=1) if not df.empty else df1

        return df

    @staticmethod
    def _get_xy_index(pnt: Point, dx: float, dy: float, ox: float, oy: float, ncol: int, nrow: int):
        x, y = pnt
        if x < ox or x > ox + ncol * dx or pnt[1] < oy or pnt[1] > oy + nrow * dy:
            return None, None
        n = int((x - ox) / dx)
        m = int((y - oy) / dy)
        return n, m

    def _grid_info(self, dtype: str) -> tuple[float, float, float, float, int, int, float]:
        return self._info[self._info['data_type'] == dtype].iloc[0, :][['dx', 'dy', 'ox', 'oy', 'ncol', 'nrow', 'nodatavalue']].values

    def _is_static(self, dtype: str) -> bool:
        return self._info[self._info['data_type'] == dtype].iloc[0]['static']
