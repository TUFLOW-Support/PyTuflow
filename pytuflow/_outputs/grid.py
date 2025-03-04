from abc import abstractmethod
from datetime import datetime
from typing import Union

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
    def _value(self, n: int, m: int, timeidx: int, dtype: str) -> float:
        pass

    def time_series(self, locations: PointLocation, data_types: Union[str, list[str]],
                    time_fmt: str = 'relative') -> pd.DataFrame:
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

        >>> grid.time_series('/path/to/point.shp', 'water level')
        time     water level/pnt1
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
                vals = []
                dx, dy, ox, oy, ncol, nrow = self._grid_info(dtype)
                n, m = self._get_xy_index(pnt, dx, dy, ox, oy, ncol, nrow)
                if n is None:
                    continue
                for timeidx, time in enumerate(self.times(dtype, fmt=time_fmt)):
                    val = (time, self._value(n, m, timeidx, dtype))
                    vals.append(val)
                df2 = pd.DataFrame(vals, columns=['time', f'{dtype}/{name}'])
                df2.set_index('time', inplace=True)
                df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2
            df = pd.concat([df, df1], axis=1) if not df.empty else df1

        return df

    def section(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
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

        >>> grid.section('/path/to/line.shp', 'water level', 0.5)
               offset  water level/Line 1
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
                times = self.times(dtype, fmt='absolute') if isinstance(time, datetime) else self.times(dtype)
                timeidx = self._closest_time_index(times, time)
                d = []
                gridline = GridLine(*self._grid_info(dtype))
                for inter in gridline.cells_along_line(line):
                    val = self._value(inter.m, inter.n, timeidx, dtype)
                    d.append((inter.offsets[0], val))
                    d.append((inter.offsets[1], val))

                df2 = pd.DataFrame(d, columns=['offset', f'{dtype}/{name}'])
                df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2

            df = pd.concat([df, df1], axis=1) if not df.empty else df1

        return df

    def _get_xy_index(self, pnt: Point, dx: float, dy: float, ox: float, oy: float, ncol: int, nrow: int):
        x, y = pnt
        if x < ox or x > ox + ncol * dx or pnt[1] < oy or pnt[1] > oy + nrow * dy:
            return None, None
        n = int((x - ox) / dx)
        m = int((y - oy) / dy)
        return n, m

    def _grid_info(self, dtype: str) -> tuple[float, float, float, float, int, int]:
        return self._info[self._info['data_type'] == dtype].iloc[0, :][['dx', 'dy', 'ox', 'oy', 'ncol', 'nrow']].values
