import typing
from datetime import datetime
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from .helpers.mesh_driver_qgis import QgisMeshDriver
from .helpers.mesh_driver_nc import NCMeshDriver
from .map_output import MapOutput, PointLocation, LineStringLocation
from .._pytuflow_types import PathLike, TimeLike
from ..util import pytuflow_logging
from .pymesh import Bbox2D
from .pymesh.mesh3d import FormatConvention


logger = pytuflow_logging.get_logger()


class Mesh(MapOutput):
    """Abstract base class for Mesh outputs."""

    def __init__(self, fpath: PathLike):
        super().__init__(fpath)

        self.fpath = Path(fpath)
        self._driver = QgisMeshDriver(self.fpath)
        self._soft_load_driver = NCMeshDriver(self.fpath)  # QGIS driver cannot soft load (i.e. without loading 2dm)
        self._loaded = False

    @staticmethod
    def _looks_like_this(fpath: Path) -> bool:
        return True

    @staticmethod
    def _looks_empty(driver: QgisMeshDriver) -> bool:
        return False

    @property
    def spherical(self) -> bool:
        """Returns whether the mesh is in spherical coordinates.

        Returns
        -------
        bool
            True if the mesh is in spherical coordinates, False if it is in Cartesian coordinates.
        """
        if self._driver.DRIVER_SOURCE == 'python':
            return self._driver.geom.spherical
        raise NotImplementedError('v1.0 driver does contain spherical attribute information.')

    @spherical.setter
    def spherical(self, value: bool):
        """Sets whether the mesh is in spherical coordinates.

        Parameters
        ----------
        value : bool
            True if the mesh is in spherical coordinates, False if it is in Cartesian coordinates.
        """
        if self._driver.DRIVER_SOURCE == 'python':
            self._driver.geom.spherical = value
        else:
            raise NotImplementedError('v1.0 driver does contain spherical attribute information.')

    def times(self, filter_by: str = None, fmt: str = 'relative') -> list[TimeLike]:
        """Returns a list of times for the given filter.

        In almost all cases, the time index will be shared by all datasets, so the ``filter_by`` argument
        is not necessary.

        Parameters
        ----------
        filter_by : str, optional
            Filter the times by a given string.
        fmt : str, optional
            The format for the time values. Options are 'relative' or 'absolute'.

        Returns
        -------
        list[TimeLike]
            The list of times.

        Examples
        --------
        >>> mesh = ... # Assume mesh is a loaded Mesh result
        >>> mesh.times()
        [0.0, 0.016666666666666666, ..., 3.0]
        """
        return super().times(filter_by, fmt)

    def data_types(self, filter_by: str = None) -> list[str]:
        """Return the available data types for the given filter.

        The available filters are:

        * ``None`` - no filter, return all available data types
        * ``scalar/vector`` - filter by scalar or vector data types
        * ``max/min`` - filter by data types that have maximum or minimum values
        * ``static/temporal`` - filter by static or temporal data types
        * ``2d/3d`` - filter by 2D or 3D data types

        Filters can be combined by delimiting with a forward slash, e.g. ``'scalar/max'``.

        Parameters
        ----------
        filter_by : str, optional
            The filter to apply to the data types.

        Returns
        -------
        list[str]
            The list of data types available.

        Examples
        --------
        >>> mesh = ... # Assume mesh is a loaded Mesh result
        >>> mesh.data_types()
        ['bed level', 'depth', 'vector velocity', 'velocity', 'water level', 'time of peak h']

        Return only the data types that have maximum values:

        >>> mesh.data_types('max')
        ['depth', 'vector velocity', 'velocity', 'water level']
        """
        return super().data_types(filter_by)

    def maximum(self, data_types: str | list[str], averaging_method: str = None) -> float | pd.DataFrame:
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
        averaging_method : str, optional
            The depth-averaging method to use. Only applicable for 3D results. If set to ``None`` (the default),
            then the maximum will be calculated from all vertical levels. If a depth averaging method is used,
            then the maximum will be calculated from the depth-averaged data.

            The averaging methods are:

            * ``None``
            * ``singlelevel``
            * ``multilevel``
            * ``depth``
            * ``height``
            * ``elevation``
            * ``sigma``

            The averaging method parameters can be adjusted by building them into the method string in a URI style
            format. The format is as follows:

            ``<method>?dir=<dir>&<value1>&<value2>``

            The averaging method parameters can be adjusted by building them into the method string in a URI style
            format. The format is as follows:

            ``<method>?dir=<dir>&<value1>&<value2>``

            Where

            * ``<method>`` is the averaging method name
            * ``<dir>`` is the direction, ``top`` or ``bottom`` (i.e. from top or from bottom) - only used by certain
              averaging methods
            * ``<value1>``, ``<value2>``... are the values to be used in the averaging method (the number required to be
              passed depends on the averaging method)

            e.g. ``'singlelevel?dir=top&1'`` uses the single level averaging method and takes the first vertical layer
            from the top. Or ``'sigma&0.1&0.9'`` uses the sigma averaging method and averages values located between
            the 10th and 90th water column depth.

        Returns
        -------
        float | pd.DataFrame
            The maximum value(s) for the given data type(s).

        Examples
        --------
        Get the maximum water level for a given mesh:

        >>> mesh = ... # Assume mesh is a loaded Mesh result
        >>> mesh.maximum('water level')
        45.672345

        Get the maximum velocity and depth for multiple data types:

        >>> mesh.maximum(['vector velocity', 'depth'])
                          maximum
        vector velocity  1.234567
        depth            5.678901
        """
        self._load()
        data_types = self._figure_out_data_types(data_types, None)
        df = pd.DataFrame()
        if self._driver.DRIVER_SOURCE == 'python':
            for dtype in data_types:
                mx = self._driver.maximum(dtype, averaging_method)
                if len(data_types) == 1:
                    return mx
                df_ = pd.DataFrame([mx], columns=['maximum'], index=[dtype])
                df = pd.concat([df, df_], axis=0) if not df.empty else df_
            return df
        else:
            raise NotImplementedError('v1.0 driver does not support maximum data extraction.')

    def minimum(self, data_types: str | list[str], averaging_method: str = None) -> float | pd.DataFrame:
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
        averaging_method : str, optional
            The depth-averaging method to use. Only applicable for 3D results. If set to ``None`` (the default),
            then the minimum will be calculated from all vertical levels. If a depth averaging method is used,
            then the minimum will be calculated from the depth-averaged data.

            The averaging methods are:

            * ``None``
            * ``singlelevel``
            * ``multilevel``
            * ``depth``
            * ``height``
            * ``elevation``
            * ``sigma``

            The averaging method parameters can be adjusted by building them into the method string in a URI style
            format. The format is as follows:

            ``<method>?dir=<dir>&<value1>&<value2>``

            The averaging method parameters can be adjusted by building them into the method string in a URI style
            format. The format is as follows:

            ``<method>?dir=<dir>&<value1>&<value2>``

            Where

            * ``<method>`` is the averaging method name
            * ``<dir>`` is the direction, ``top`` or ``bottom`` (i.e. from top or from bottom) - only used by certain
              averaging methods
            * ``<value1>``, ``<value2>``... are the values to be used in the averaging method (the number required to be
              passed depends on the averaging method)

            e.g. ``'singlelevel?dir=top&1'`` uses the single level averaging method and takes the first vertical layer
            from the top. Or ``'sigma&0.1&0.9'`` uses the sigma averaging method and averages values located between
            the 10th and 90th water column depth.

        Returns
        -------
        float | pd.DataFrame
            The minimum value(s) for the given data type(s).

        Examples
        --------
        Get the minimum water level for a given mesh:

        >>> mesh = ... # Assume mesh is a loaded Mesh result
        >>> mesh.minimum('water level')
        33.456789

        Get the minimum velocity and depth for multiple data types:

        >>> mesh.minimum(['vector velocity', 'depth'])
                          minimum
        vector velocity  0.
        depth            0.
        """
        self._load()
        data_types = self._figure_out_data_types(data_types, None)
        df = pd.DataFrame()
        if self._driver.DRIVER_SOURCE == 'python':
            for dtype in data_types:
                mx = self._driver.minimum(dtype, averaging_method)
                if len(data_types) == 1:
                    return mx
                df_ = pd.DataFrame([mx], columns=['minimum'], index=[dtype])
                df = pd.concat([df, df_], axis=0) if not df.empty else df_
            return df
        else:
            raise NotImplementedError('v1.0 driver does not support minimum data extraction.')

    def data_point(self, locations: PointLocation, data_types: str | list[str] | None, time: TimeLike,
                   averaging_method: str = None) -> float | tuple[float, float] | pd.DataFrame:
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
        averaging_method : str, optional
            The depth-averaging method to use. Only applicable for 3D results.

            The averaging methods are:

            * ``singlelevel``
            * ``multilevel``
            * ``depth``
            * ``height``
            * ``elevation``
            * ``sigma``

            The averaging method parameters can be adjusted by building them into the method string in a URI style
            format. The format is as follows:

            ``<method>?dir=<dir>&<value1>&<value2>``

            Where

            * ``<method>`` is the averaging method name
            * ``<dir>`` is the direction, ``top`` or ``bottom`` (i.e. from top or from bottom) - only used by certain
              averaging methods
            * ``<value1>``, ``<value2>``... are the values to be used in the averaging method (the number required to be
              passed depends on the averaging method)

            e.g. ``'singlelevel?dir=top&1'`` uses the single level averaging method and takes the first vertical layer
            from the top. Or ``'sigma&0.1&0.9'`` uses the sigma averaging method and averages values located between
            the 10th and 90th water column depth.

        Returns
        -------
        float | tuple[float, float] | pd.DataFrame
            The data value(s) for the given location(s) and data type(s).

        Examples
        --------
        Get the water level data for a given point defined as ``(x, y)``:

        >>> mesh = ... # Assume mesh is a loaded Mesh result
        >>> mesh.data_point((293250, 6178030), 'water level', 1.5)
        42.723076

        Get velocity vector data for a given point defined as ``(x, y)``:

        >>> mesh.data_point((293250, 6178030), 'vector velocity', 1.5)
        (0.282843, 0.154213)

        Get the maximum water level and depth for multiple points defined in a shapefile. Time is passed as ``-1`` since
        it is a static dataset (it could be any time value since it won't affect the result):

        >>> mesh.data_point('/path/to/points.shp', ['max water level', 'max depth'], -1)
              max water level  max depth
        pnt1        40.501997   2.785571
        pnt2        43.221862   3.450053
        """
        self._load()
        pnts = self._translate_point_location(locations)
        data_types = self._figure_out_data_types(data_types, None)
        rows = []
        values1 = []
        val = np.nan
        for name, pnt in pnts.items():
            rows.append(name)
            values2 = []
            for dtype in data_types:
                if self._driver.DRIVER_SOURCE == 'python':
                    val = self._driver.data_point(pnt, dtype, time, depth_averaging=averaging_method, return_type='vector')
                else:
                    val = self._driver.data_point(pnt, dtype, time, averaging_method, return_type='vector')
                values2.append(val)
            values1.append(values2)
        if len(rows) == 1 and len(data_types) == 1:
            return val
        df = pd.DataFrame(values1[::-1]).rename(columns=dict(enumerate(data_types)), index=dict(enumerate(rows[::-1])))
        return df

    def time_series(self, locations: PointLocation, data_types: str | list[str] | None,
                    time_fmt: str = 'relative', averaging_method: str = None) -> pd.DataFrame:
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
            The format for the time values. Options are 'relative' or 'absolute'.
        averaging_method : str, optional
            The depth-averaging method to use. Only applicable for 3D results.

            The averaging methods are:

            * ``singlelevel``
            * ``multilevel``
            * ``depth``
            * ``height``
            * ``elevation``
            * ``sigma``

            The averaging method parameters can be adjusted by building them into the method string in a URI style
            format. The format is as follows:

            ``<method>?dir=<dir>&<value1>&<value2>``

            Where

            * ``<method>`` is the averaging method name
            * ``<dir>`` is the direction, ``top`` or ``bottom`` (i.e. from top or from bottom) - only used by certain
              averaging methods
            * ``<value1>``, ``<value2>``... are the values to be used in the averaging method (the number required to be
              passed depends on the averaging method)

            e.g. ``'singlelevel?dir=top&1'`` uses the single level averaging method and takes the first vertical layer
            from the top. Or ``'sigma&0.1&0.9'`` uses the sigma averaging method and averages values located between
            the 10th and 90th water column depth.

        Returns
        -------
        pd.DataFrame
            The time series data.

        Examples
        --------
        Get the water level time-series data for a given point defined as ``(x, y)``:

        >>> mesh = ... # Assume mesh is a loaded Mesh result
        >>> mesh.time_series((293250, 6178030), 'water level')
            time  pnt1/water level
        0.000000               NaN
        0.083333               NaN
        0.166667               NaN
        0.250000               NaN
        0.333333               NaN
        0.416667               NaN
        0.500000               NaN
        0.583333               NaN
        0.666667         41.561204
        0.750000         41.838923
        ...                    ...
        2.666667         41.278006
        2.750000         41.239387
        2.833334         41.201996
        2.916667         41.166462
        3.000000         41.128152

        Get velocity time-series using all the points within a shapefile:

        >>> mesh.time_series('path/to/shapefile.shp', 'vel')
            time  pnt1/velocity
        0.000000            NaN
        0.083333            NaN
        0.166667            NaN
        0.250000            NaN
        0.333333            NaN
        0.416667            NaN
        0.500000            NaN
        0.583333            NaN
        0.666667       0.975577
        0.750000       0.914921
        ...                 ...
        2.666667       0.320217
        2.750000       0.270925
        2.833334       0.233793
        2.916667       0.206761
        3.000000       0.183721
        """
        self._load()
        df = pd.DataFrame()
        pnts = self._translate_point_location(locations)
        data_types = self._figure_out_data_types(data_types, 'temporal')
        for name, pnt in pnts.items():
            for dtype in data_types:
                if self._driver.DRIVER_SOURCE == 'python':
                    a = self._driver.time_series(pnt, dtype, averaging_method)
                    if a.size:
                        a = a.reshape(a.shape[0], -1)
                        if a.shape[1] > 2:
                            a = np.append(a[:,[0]], np.linalg.norm(a[:,1:], axis=1).reshape(-1, 1), axis=1)
                        df1 = pd.DataFrame(a[:,1], index=a[:,0], columns=[f'{name}/{dtype}'])
                        df1.index.name = 'time'
                    else:
                        df1 = pd.DataFrame()
                else:
                    df1 = self._driver.time_series(name, pnt, dtype, averaging_method)
                if df1.empty:
                    continue
                if not df.empty:
                    if np.isclose(df.index, df1.index, atol=0.0001, rtol=0).all():
                        df1.index = df.index
                    else:
                        raise ValueError('Time series index does not match between datasets.')
                df = pd.concat([df, df1], axis=1) if not df.empty else df1

        if time_fmt == 'absolute':
            df.index = self.reference_time + pd.to_timedelta(df.index, unit='h')

        return df

    def section(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike, averaging_method: str = None) -> pd.DataFrame:
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
        averaging_method : str, optional
            The depth-averaging method to use. Only applicable for 3D results. If None is provided for a 3D result,
            the current rendering method will be used.

            The averaging methods are:

            * ``singlelevel``
            * ``multilevel``
            * ``depth``
            * ``height``
            * ``elevation``
            * ``sigma``

            The averaging method parameters can be adjusted by building them into the method string in a URI style
            format. The format is as follows:

            ``<method>?dir=<dir>&<value1>&<value2>``

            Where

            * ``<method>`` is the averaging method name
            * ``<dir>`` is the direction, `top` or ``bottom`` (i.e. from top or from bottom) - only used by certain
              averaging methods
            * ``<value1>``, ``<value2>``... are the values to be used in the averaging method (the number required to be
              passed depends on the averaging method)

            e.g. ``'singlelevel?dir=top&1'`` uses the single level averaging method and takes the first vertical layer
            from the top. Or ``'sigma&0.1&0.9'`` uses the sigma averaging method and averages values located between
            the 10th and 90th water column depth.

        Returns
        -------
        pd.DataFrame
            The section data.

        Examples
        --------
        Get the water level section data for a given line string defined as a list of points:

        >>> mesh = ... # Assume mesh is a loaded Mesh result
        >>> mesh.section([(293250, 6178030), (293500, 6178030)], 'water level', 1.5)
                 line1
                offset water level
        0     0.000000   42.724101
        1     1.706732   42.723076
        2     4.624017   42.722228
        3     7.191697   42.722665
        4    11.116369   42.723587
        5    16.251266   42.723855
        6    21.386370   42.723230
        7    25.869978   42.722765
        8    28.437221   42.722449
        9    31.656245   42.721945
        10   36.791135   42.721079

        Get the bed level and max water level data using a shapefile to define the locations (both datasets are
        static and therefore the time argument won't have any effect):

        >>> mesh.section('path/to/shapefile.shp', ['bed level', 'max h'], -1)
               Line_1                                 Line_2
               offset  bed level max water level      offset  bed level max water level
        0    0.000000  43.646312             NaN    0.000000  43.112894             NaN
        1    0.145704  43.645835             NaN    2.213407  43.088104             NaN
        2    2.801012  43.647998             NaN    6.926959  43.035811             NaN
        3    7.819650  43.643313             NaN   11.926842  42.987500             NaN
        4   12.838279  43.634620             NaN   16.926803  42.950000             NaN
        5   17.856980  43.626645             NaN   21.926729  42.916000             NaN
        6   22.875678  43.615949             NaN   26.926655  42.888000             NaN
        7   25.941652  43.611225             NaN   31.926952  42.865499             NaN
        8   28.451249  43.603039             NaN   36.926835  42.846001             NaN
        9   32.913571  43.591435             NaN   41.926869  42.829500             NaN
        10  37.932185  43.578406             NaN   46.926830  42.812500             NaN
        11  42.950809  43.569102             NaN   51.926756  42.795000       42.443355
        12  47.969530  43.577088             NaN   56.926682  42.777190       42.443967
        13  52.988495  43.666201             NaN   61.926643  42.760000       42.444545
        14  58.007149  43.773129             NaN   66.926940  42.744000       42.445528
        15  63.026036  43.897195             NaN   71.926823  42.730500       42.447615
        16  68.044737  43.612406             NaN   76.926857  42.719000       42.449872
        17  73.063420  42.849014       42.834780   81.926818  42.708500       42.452022
        """
        self._load()
        df = pd.DataFrame()
        lines = self._translate_line_string_location(locations)
        data_types = self._figure_out_data_types(data_types, None)
        for name, line in lines.items():
            df1 = pd.DataFrame()
            for dtype in data_types:
                if self._driver.DRIVER_SOURCE == 'python':
                    a = self._driver.section(line, dtype, time, averaging_method)
                    a = a.reshape(a.shape[0], -1)
                    if a.shape[1] > 2:
                        a = np.append(a[:, [0]], np.linalg.norm(a[:, 1:], axis=1).reshape(-1, 1), axis=1)
                    df2 = pd.DataFrame(a[:,1], index=a[:,0], columns=[dtype])
                    df2.index.name = 'offset'
                else:
                    df2 = self._driver.section(line, dtype, time, averaging_method)
                if df2.empty:
                    continue
                df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2
            df = self._merge_line_dataframe(df, df1, name, reset_index=True)

        return df

    def curtain(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Extracts curtain data for the given locations and data types.

        The ``locations`` can be a list of ``x, y`` tuple points, or a Well Known Text (WKT) line string. It can also
        be a dictionary of key, line-string pairs where the key is the name that will be used in the column name in
        the resulting DataFrame.

        The ``locations`` argument can also be a single GIS file path e.g. Shapefile or GPKG (but any format supported
        by GDAL is also supported). GPKG's should follow the TUFLOW convention if specifying the layer name within
        the database ``database.gpkg >> layer``. If the GIS layer has a field called ``name``, ``label``, or ``ID``
        then this will be used as the column name in the resulting DataFrame.

        The resulting DataFrame will be made up of 3 columns- ``X, Y, value`` data. The ``X, Y`` values represent
        cells in the vertical plane, and should be treated as groups of 4 which denote the corners of a cell. The
        ``value`` represents the data value at that cell, which will be returned as a single number for scalar
        results and a tuple for vector results. Note, velocity will always be returned as vector (tuple) result.
        Vector results will also return a fourth column which will be the vector results projected onto the direction
        of the linestring. The direction of the line is the local Y-axis and the perpendicular
        direction is the local X-axis.

        The resulting DataFrame will use multi-index columns since the data is not guaranteed to have the same
        index. The level 1 index will be the label, and the level 2 index will be the data type. The ``X,Y`` offsets
        will always be the first two columns within the level 2 index.

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
        Get the velocity (scalar) curtain data for a given line string defined as in a shapefile:

        >>> mesh = ... # Assume mesh is a loaded Mesh result
        >>> mesh.curtain('path/to/shapefile.shp', 'salinity', 1.5)
                 Line_1
                      x          y  salinity
        0     53.431056  42.898541  0.009024
        1     57.991636  42.898541  0.009024
        2     57.991636  42.939461  0.009024
        3     53.431056  42.939461  0.009024
        4     57.991636  42.884058  0.010111
        ..          ...        ...       ...
        199  257.097906  42.754025  0.049965
        200  258.743717  42.759825  0.028459
        201  263.876694  42.759825  0.028459
        202  263.876694  42.875885  0.028459
        203  258.743717  42.875885  0.028459
        """
        self._load()
        df = pd.DataFrame()
        lines = self._translate_line_string_location(locations)
        data_types = self._figure_out_data_types(data_types, None)
        for name, line in lines.items():
            df1 = pd.DataFrame()
            for dtype in data_types:
                if self._driver.DRIVER_SOURCE == 'python':
                    a = self._driver.curtain(line, dtype, time)
                    if a.shape[1] == 3:
                        df2 = pd.DataFrame(a, columns=['x', 'y', dtype])
                    else:
                        a = a.reshape(-1, 6)
                        df2 = pd.DataFrame(a[:,:2], columns=['x', 'y'])
                        df2[dtype] = list(map(tuple, a[:,2:4].tolist()))
                        df2[f'{dtype}_local'] = list(map(tuple, a[:,4:].tolist()))
                else:
                    df2 = self._driver.curtain(line, dtype, time)
                if df2.empty:
                    continue
                df1 = pd.concat([df1, df2[dtype]], axis=1) if not df1.empty else df2
            df = self._merge_line_dataframe(df, df1, name, reset_index=False)

        return df

    def profile(self, locations: PointLocation, data_types: Union[str, list[str]],
                time: TimeLike, interpolation: str = 'stepped') -> pd.DataFrame:
        """Extracts vertical profile data for the given locations and data types.

        The ``locations`` can be a single point in the form of a tuple ``(x, y)`` or in the Well Known Text (WKT)
        format. It can also be a list of points, or a dictionary of points where the key will be used in the column name
        in the resulting DataFrame.

        The ``locations`` argument can also be a single GIS file path e.g. Shapefile or GPKG (but any format supported
        by GDAL is also supported). GPKG's should follow the TUFLOW convention if specifying the layer name within
        the database ``database.gpkg >> layer``. If the GIS layer has a field called ``name``, ``label``, or ``ID``
        then this will be used as the column name in the resulting DataFrame.

        The returned DataFrame will use multi-index columns as the data is not guaranteed to have the same index.
        The level 1 index will be the label, and the level 2 index will be the data type. The elevation will always
        be the first column within the level 2 index.

        Parameters
        ----------
        locations : Point | list[Point] | dict[str, Point] | PathLike
            The location to extract the time series data for.
        data_types : str | list[str]
            The data types to extract the time series data for.
        time : TimeLike
            The time to extract the time series data for.
        interpolation : str, optional
            The interpolation method to use. Options are 'stepped' or 'linear'. Linear interpolation
            should not be used for 2D results.

        Returns
        -------
        pd.DataFrame
            The time series data.

        Examples
        --------
        Get The profile for a given point defined in a shapefile:

        >>> mesh = ... # Assume mesh is a loaded Mesh result
        >>> mesh.profile('path/to/shapefile.shp', 'velocity', 1.5)
                       pnt1
          elevation  velocity
        0       0.0  0.282843
        1       0.5  0.282843
        2       0.5  0.424264
        3       1.0  0.424264
        """
        self._load()
        df = pd.DataFrame()
        pnts = self._translate_point_location(locations)
        data_types = self._figure_out_data_types(data_types, None)
        for name, pnt in pnts.items():
            df1 = pd.DataFrame()
            for dtype in data_types:
                if self._driver.DRIVER_SOURCE == 'python':
                    a = self._driver.profile(pnt, dtype, time)
                    if a.size:
                        a = a.reshape(a.shape[0], -1)
                        if a.shape[1] > 2:
                            a = np.append(a[:, [0]], np.linalg.norm(a[:, 1:], axis=1).reshape(-1, 1), axis=1)
                        df2 = pd.DataFrame(a[:,1], index=a[:,0], columns=[dtype])
                        df2.index.name = 'elevation'
                    else:
                        df2 = pd.DataFrame()
                else:
                    df2 = self._driver.profile(pnt, dtype, time, interpolation)
                if interpolation.lower() == 'linear' and df2.shape[0] > 2:
                    df2 = df2.sort_index()
                    df3 = pd.DataFrame()
                    df3['elevation'] = df2.index.dropna().unique().tolist()
                    df3[dtype] = np.interp(
                        df3['elevation'],
                        df2.index,
                        df2[dtype],
                    )
                    df2 = df3.set_index('elevation').sort_index(ascending=False)
                if df2.empty:
                    continue
                df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2
            if df1.empty:
                continue
            df1.reset_index(inplace=True, drop=False)
            df1.columns = pd.MultiIndex.from_tuples([(name, x) for x in df1.columns])
            df = pd.concat([df, df1], axis=1) if not df.empty else df1

        return df

    def to_gltf(self,
                output_path: Path | str,
                time: TimeLike,
                data_types: typing.Iterable[str] = ('Depth', 'Vector Velocity-x', 'Vector Velocity-y'),
                uv_projection_extent: typing.Iterable[float] | Bbox2D = (),
                ):
        """Exports the mesh to a glTF 2.0 file for visualisation in compatible software.
        Both ``.gltf`` and ``.glb`` formats are supported.

        .. admonition:: Experimental Feature
            :class: warning

            gLTF export is an experimental feature and may not work for all formats and drivers.
            It requires the ``pygltf`` library to be installed.

        Parameters
        ----------
        output_path : Path | str
            The output file path for the glTF file.
        time : float
            The time to export the data for.
        data_types : Array[str], optional
            The provided data types will be exported into the mesh vertex colour (i.e. the RGB channels). The
            data types will be re-mapped to the 0-1 range for the colour channels by using the maximum value as
            returned by the ``maximum()`` method. The default data types are ``Depth``, ``Vector Velocity-x``,
            and ``Vector Velocity-y`` (i.e. depth will be packed into the red channel, velocity x into green,
            and velocity y into blue).
        uv_projection_extent : Array[float], optional
            The extent to use for UV projection of textures onto the mesh. The format is
            ``(min_x, min_y, max_x, max_y)``. If not provided, the mesh bounding box will be used except for
            TUFLOW HPC/Classic XMDF results which will use the model domain extent as defined in the ``.2dm``.
            For HPC/Classic models, this matches the output grid setting ``Grid Output Origin == MODEL ORIGIN``.
        """
        if not hasattr(self._driver, 'to_gltf'):
            raise NotImplementedError('The current driver does not support exporting to glTF format.')
        self._load()

        data_types = self._figure_out_data_types_game_mesh(data_types, None)

        dtype = self.data_types('temporal')
        if not dtype:
            time_index = -1  # assume static datasets
        else:
            time_index = self._driver._find_time_index(dtype[0], time)

        self._driver.to_gltf(
            output_path,
            time_index=time_index,
            data_types=data_types,
            uv_projection_extent=uv_projection_extent
        )

    def to_alembic(self,
                   output_path: Path | str,
                   time_sample_frequency: int = 1,
                   data_types: typing.Iterable[str] = ('Depth', 'Vector Velocity-x', 'Vector Velocity-y'),
                   uv_projection_extent: typing.Iterable[float] | Bbox2D = (),
                   time_sampling: float = 1 / 24,
                   format_convention: FormatConvention = FormatConvention.OpenGL
                   ):
        """Exports the mesh to an Alembic file for visualisation in compatible software.

        .. admonition:: Experimental Feature
            :class: warning

            Alembic export is an experimental feature and may not work for all formats and drivers.
            It requires the ``pyalembic`` library to be installed.

        Parameters
        ----------
        output_path : Path | str
            The output file path for the Alembic file.
        time_sample_frequency : int, optional
            The frequency in which to sample the time steps in the mesh file. A value of 1 means every time step
            will be exported, a value of 2 means every second time step will be exported, and so on. Default is 1.
        data_types : Array[str], optional
            The provided data types will be exported into the mesh vertex colour (i.e. the RGB channels). The
            data types will be re-mapped to the 0-1 range for the colour channels by using the maximum value as
            returned by the ``maximum()`` method. The default data types are ``Depth``, ``Vector Velocity-x``,
            and ``Vector Velocity-y`` (i.e. depth will be packed into the red channel, velocity x into green,
            and velocity y into blue).
        uv_projection_extent : Array[float], optional
            The extent to use for UV projection of textures onto the mesh. The format is
            ``(min_x, min_y, max_x, max_y)``. If not provided, the mesh bounding box will be used except for
            TUFLOW HPC/Classic XMDF results which will use the model domain extent as defined in the ``.2dm``.
            For HPC/Classic models, this matches the output grid setting ``Grid Output Origin == MODEL ORIGIN``.
        time_sampling : float, optional
            The time sampling interval in seconds. Default is 1/24 (i.e. each output time step represents a separate
            frame in a 24 fps sequence).
        format_convention : FormatConvention, optional
            The format convention to use for the Alembic file. Default is ``FormatConvention.Blender``.
        """
        if not hasattr(self._driver, 'to_alembic'):
            raise NotImplementedError('The current driver does not support exporting to Alembic format.')
        self._load()

        data_types = self._figure_out_data_types_game_mesh(data_types, None)

        self._driver.to_alembic(
            output_path,
            time_sample_frequency,
            data_types,
            uv_projection_extent,
            time_sampling,
            format_convention
        )

    def _initial_load(self):
        # attempt doing a "soft" load initially, loading the whole 2dm is expensive and not relevant to info in
        # the xmdf until we need to extract spatial data - requires netCDF4 library
        self.name = self.fpath.stem
        if self._soft_load_driver.valid:
            driver = self._soft_load_driver
        else:
            self._driver.load()
            self._loaded = True
            driver = self._driver

        d = {'data_type': [], 'type': [], 'is_max': [], 'is_min': [], 'static': [], '3d': [], 'start': [], 'end': [], 'dt': []}
        for dtype in driver.data_groups():
            d['type'].append(dtype.type)
            d['is_min'].append('/minimums' in dtype.name.lower())
            d['is_max'].append('/maximums' in dtype.name.lower())
            d['data_type'].append(self._get_standard_data_type_name(dtype.name))
            d['start'].append(np.round(dtype.times[0], decimals=6))
            d['end'].append(np.round(dtype.times[-1], decimals=6))
            static = len(dtype.times) == 1
            d['static'].append(static)
            d['3d'].append(dtype.vert_lyr_count > 1)
            dt = 0.
            if not static:
                dt = self._calculate_time_step(np.array(dtype.times) * 3600.)
            d['dt'].append(dt)

        self._info = pd.DataFrame(d)

        self.has_reference_time = driver.has_inherent_reference_time
        if self.has_reference_time:
            self.reference_time = driver.reference_time

    def _load(self):
        if self._loaded:
            return
        self._driver.load()
        self._loaded = True
