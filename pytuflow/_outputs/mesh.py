import typing
from datetime import datetime
from pathlib import Path
from typing import Union

import numpy as np
try:
    import pandas as pd
except ImportError:
    from .pymesh.stubs import pandas as pd

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

    def maximum(self, data_types: str | list[str], averaging_method: str = None,
                split_vector_components: bool = False) -> float | tuple[float, float] | pd.DataFrame:
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
        split_vector_components : bool, optional
            Whether to split vector components into separate x and y values and calculate maximums for each
            component separately. Only applicable for vector data types. Components are calculated separately
            and do not necessarily represent a single point in space and time and magnitudes should not be
            calculated from the returned values. Components will be returned as a tuple i.e. ``[vec-x, vec-y]``.

        Returns
        -------
        float | tuple[float, float] | pd.DataFrame
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
                mx = self._driver.maximum(dtype, averaging_method, split_vector_components)
                if len(data_types) == 1:
                    return mx
                df_ = pd.DataFrame([mx], columns=['maximum'], index=[dtype])
                df = pd.concat([df, df_], axis=0) if not df.empty else df_
            return df
        else:
            raise NotImplementedError('v1.0 driver does not support maximum data extraction.')

    def minimum(self, data_types: str | list[str], averaging_method: str = None,
                split_vector_components: bool = False) -> float | tuple[float, float] | pd.DataFrame:
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
        split_vector_components : bool, optional
            Whether to split vector components into separate x and y values and calculate minimums for each
            component separately. Only applicable for vector data types. Components are calculated separately
            and do not necessarily represent a single point in space and time and magnitudes should not be
            calculated from the returned values. Components will be returned as a tuple i.e. ``[vec-x, vec-y]``.

        Returns
        -------
        float | tuple[float, float] | pd.DataFrame
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
                mx = self._driver.minimum(dtype, averaging_method, split_vector_components)
                if len(data_types) == 1:
                    return mx
                df_ = pd.DataFrame([mx], columns=['minimum'], index=[dtype])
                df = pd.concat([df, df_], axis=0) if not df.empty else df_
            return df
        else:
            raise NotImplementedError('v1.0 driver does not support minimum data extraction.')

    def surface(self, data_type: str, time: TimeLike, averaging_method: str = 'sigma&0&1',
                to_vertex: bool = False, coord_scope: str = 'global') -> pd.DataFrame:
        """Returns the value for every cell/vertex at the specified time. A depth averaging method
        is required for 3D datasets (defaults to sigma averaging from 0 to 1).

        Parameters
        ----------
        data_type : str
            The data type to extract the surface data for.
        time : TimeLike
            The time to extract the surface data for.
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

        to_vertex : bool, optional
            Whether to interpolate the cell data to vertex data. Only applicable for cell-based datasets (e.g. NCMesh).
            For vertex-based datasets (e.g. XMDF), this parameter has no effect.
        coord_scope : str, optional
            The coordinate scope for the output coordinates. Options are:

            - ``"global"`` (default) - coordinates are unchanged from the input data (i.e. easting/northing or lon/lat)
            - ``"local"`` - coordinates are transformed to a local Cartesian coordinate system and the origin is moved
              to the centre of the mesh extent. This can be useful for visualisation purposes, especially when converting
              into 3D formats for viewing in programs like Blender, Unreal Engine, etc

        Returns
        -------
        pd.DataFrame
            The surface data as a DataFrame with columns for the coordinates, value(s), and active mask.

        Examples
        --------
        >>> mesh = ... # Assume mesh is a loaded Mesh result
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
        self._load()
        data_type = self._figure_out_data_types(data_type, None)[0]
        if self._driver.DRIVER_SOURCE != 'python':
            raise NotImplementedError('v1.0 driver does not support surface data extraction.')
        data, mask = self._driver.surface(data_type, time, averaging_method, to_vertex, coord_scope)
        columns = ['lon', 'lat'] if self._driver.extractor.spherical() and coord_scope != 'local' else ['x', 'y']
        df = pd.DataFrame(
            data,
            columns=columns + ['value-x', 'value-y'] if data.shape[1] == 4 else columns + ['value']
        )
        df['active'] = mask.flatten().astype(bool)
        return df

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
                mesh_geometry: str = '',
                time: TimeLike = -1,
                vertex_colour: list[str] = (),
                uv_projection_extent: list[float] | tuple[float] | np.ndarray | Bbox2D = (),
                location_ref: 'Mesh' = None,
                ):
        """Exports the mesh to a glTF 2.0 file for visualisation in compatible software.
        Both ``.gltf`` and ``.glb`` formats are supported.

        .. admonition:: Experimental Feature
            :class: warning

            gLTF export is an experimental feature and may not work for all formats and drivers. It may also be
            modified without warning in future releases.

        Parameters
        ----------
        output_path : Path | str
            The output file path for the glTF file.
        mesh_geometry : str, optional
            The data type to use for the mesh geometry, e.g. ``"water level"``. If not provided,
            the base mesh geometry will be used e.g. this will be the ``"Bed Elevation"`` for XMDF results.
        time : float | datetime
            The time to export the data for.
        vertex_colour : Array[str], optional
            The provided data types will be exported into the mesh vertex colours. This allows a maximum of 3 data types
            only, one in the red channel, blue channel, and green channel. Vector types require 2 channels and should
            use a suffix with either ``"-x"`` or ``"-y"`` (e.g. ``"Vector Velocity-x"`` for the x vector component).

            | The data types will be re-mapped to the 0-1 range for the colour channels by using the following formula

            | ``packed_value = (value - value_min) / (value_max - value_min)``.

            | The ``value_min`` and ``value_max`` are obtained using the :meth:`minimum()<pytuflow.XMDF.minimum>`
              and :meth:`maximum()<pytuflow.XMDF.maximum>` methods.

            | An example usage would be ``["Depth", "Vector Velocity-x", "Vector Velocity-y"]`` to pack depth into
              the red channel, velocity x into green, and velocity y into blue.
        uv_projection_extent : Array[float], optional
            The extent to use for UV projection of textures onto the mesh. The format is
            ``(min_x, min_y, max_x, max_y)``. If not provided, the mesh bounding box will be used except for
            TUFLOW HPC/Classic XMDF results which will use the model domain extent as defined in the ``.2dm``.
        location_ref : Mesh, optional
            The location reference to use when setting the geometry origin. By default, the mesh bounding box is
            used to set the geometry origin (it uses the centre of the bounding box). Another mesh result can be used
            to define the origin instead, which is useful when exporting multiple meshes that need to be aligned
            in 3D space.

        Examples
        --------
        The examples below show images of importing the exported glTF files into `Blender <https://www.blender.org/>`_
        for visualisation.

        Export an XMDF bed elevation:

        >>> from pytuflow import XMDF
        >>> xmdf = XMDF('/path/to/result.xmdf')
        >>> xmdf.to_gltf('/path/to/output/bed_elevation.glb')

        .. image:: ../assets/images/xmdf_bed_elevation_gltf_blender.png
            :alt: XMDF Bed Elevation in Blender
            :align: center
            :width: 720px

        | Export the maximum water level with the depth results in the vertex colours:

        >>> xmdf.to_gltf(
            output_path='/path/to/output/max_water_level.glb',
            mesh_geometry='max water level',
            vertex_colour=['max depth']
        )

        .. image:: ../assets/images/xmdf_max_water_level_gltf_blender.png
            :alt: XMDF Max Water Level in Blender
            :align: center
            :width: 720px

        | Export ``DEM_Z`` check file and use the XMDF result as a location reference so that they will align in
          local space.

        >>> from pytuflow import Grid
        >>> dem_z = Grid('/path/to/check/DEM_Z.tif')
        >>> dem_z.to_mesh().to_gltf(
            output_path='/path/to/check/dem_z.glb',
            location_ref=xmdf
        )

        .. image:: ../assets/images/xmdf_dem_z_gltf_blender.png
            :alt: XMDF DEM_Z and Max Water Level in Blender
            :align: center
            :width: 720px

        .. image:: ../assets/images/xmdf_combined_dem_z_water_level_gltf_blender.png
            :alt: XMDF DEM_Z and Max Water Level in Blender
            :align: center
            :width: 720px
        """
        if not hasattr(self._driver, 'to_gltf'):
            raise NotImplementedError('The current driver does not support exporting to glTF format.')
        self._load()

        if mesh_geometry:
            mesh_geometry = self._figure_out_data_types(mesh_geometry, None)[0]

        if vertex_colour:
            vertex_colour = self._figure_out_data_types_game_mesh(vertex_colour, None)
        else:
            vertex_colour = (mesh_geometry or self._driver.geom.data_type,)

        # the other mesh can provide a transform to align the geometry in 3D space
        transform = location_ref._driver.geom.trans if location_ref is not None else None

        self._driver.to_gltf(
            output_path,
            mesh_geometry,
            time,
            vertex_colour,
            uv_projection_extent,
            transform,
        )

    def to_alembic(self,
                   output_path: Path | str,
                   mesh_geometry: str = '',
                   vertex_colour: list[str] = (),
                   uv_projection_extent: list[float] | tuple[float] | np.ndarray | Bbox2D = (),
                   location_ref: 'Mesh' = None,
                   time_sample_frequency: int = 1,
                   time_sampling: float = 1 / 24,
                   export_for: str = 'opengl'
                   ):
        """Exports the mesh to an Alembic file for visualisation in compatible software.

        .. admonition:: Experimental Feature
            :class: warning

            Alembic export is an experimental feature and may not work for all formats and drivers. It may also be
            modified without warning in future releases. It requires the ``pyalembic`` library to be installed.

        Parameters
        ----------
        output_path : Path | str
            The output file path for the Alembic file.
        mesh_geometry : str, optional
            The data type to use for the mesh geometry, e.g. ``"water level"``. If not provided,
            the mesh geometry will be used e.g. this will be the ``"Bed Elevation"`` for XMDF results.
        vertex_colour : Array[str], optional
            The provided data types will be exported into the mesh vertex colours. This allows a maximum of 3 data types
            only, one in the red channel, blue channel, and green channel. Vector types require 2 channels and should
            use a suffix with either ``"-x"`` or ``"-y"`` (e.g. ``"Vector Velocity-x"`` for the x vector component).

            | The data types will be re-mapped to the 0-1 range for the colour channels by using the following formula

            | ``packed_value = (value - value_min) / (value_max - value_min)``.

            | The ``value_min`` and ``value_max`` are obtained using the :meth:`minimum()<pytuflow.XMDF.minimum>`
              and :meth:`maximum()<pytuflow.XMDF.maximum>` methods.

            | An example usage would be ``["Depth", "Vector Velocity-x", "Vector Velocity-y"]`` to pack depth into
              the red channel, velocity x into green, and velocity y into blue.
        uv_projection_extent : Array[float], optional
            The extent to use for UV projection of textures onto the mesh. The format is
            ``(min_x, min_y, max_x, max_y)``. If not provided, the mesh bounding box will be used except for
            TUFLOW HPC/Classic XMDF results which will use the model domain extent as defined in the ``.2dm``.
            For HPC/Classic models, this matches the output grid setting ``Grid Output Origin == MODEL ORIGIN``.
        location_ref : Mesh, optional
            The location reference to use when setting the geometry origin. By default, the mesh bounding box is
            used to set the geometry origin (it uses the centre of the bounding box). Another mesh result can be used
            to define the origin instead, which is useful when exporting multiple meshes that need to be aligned
            in 3D space.
        time_sample_frequency : int, optional
            The frequency in which to sample the time steps in the mesh file. A value of 1 means every time step
            will be exported, a value of 2 means every second time step will be exported, and so on. Default is 1.
        time_sampling : float, optional
            The time sampling interval in seconds. Default is 1/24 (i.e. each output time step represents a separate
            frame in a 24 fps sequence).
        export_for : str, optional
            An optional argument that will adjust the data to be more in keeping with certain software package
            conventions E.g. ``"unreal"`` will export the data with a Z-up coordinate system, left-hand rule,
            and in centimetres, whereas ``"opengl"`` will use a Y-up coordinate system, right-hand rule,
            and metres. Default is ``"opengl"``.

            Typically, the end software package can manipulate the data (automatically or manually by the user)
            to suit its own requirements, however this option is provided to make the import process easier.

            The options are:

            - ``"opengl"``
            - ``"unreal"``
            - ``"blender"``

        Examples
        --------
        The examples below show videos of the exported Alembic files in `Blender <https://www.blender.org/>`_
        for visualisation.

        Export the water level from an XMDF result with depth and vector velocity as vertex colours:

        >>> from pytuflow import XMDF
        >>> xmdf = XMDF('/path/to/result.xmdf')
        >>> xmdf.to_alembic(
            output_path='/path/to/output/water_level.abc',
            mesh_geometry='water level',
            vertex_colour=['depth', 'vector velocity-x', 'vector velocity-y'],
            time_sampling=0.5,  # 0.5 second intervals
            export_for='blender'
        )

        .. video:: ../_static/videos/xmdf_water_level_alembic_blender.mp4
            :alt: XMDF Water Level Alembic in Blender
            :align: center
            :width: 720

        .. image:: ../assets/images/depth_velocity_blender_material.png
            :alt: Material setup for depth and velocity unpacking in Blender
            :align: center
            :width: 720px
        """
        if not hasattr(self._driver, 'to_alembic'):
            raise NotImplementedError('The current driver does not support exporting to Alembic format.')
        self._load()

        if mesh_geometry:
            mesh_geometry = self._figure_out_data_types(mesh_geometry, None)[0]

        if vertex_colour:
            vertex_colour = self._figure_out_data_types_game_mesh(vertex_colour, None)
        else:
            vertex_colour = (mesh_geometry or self._driver.geom.data_type,)

        # the other mesh can provide a transform to align the geometry in 3D space
        transform = location_ref._driver.geom.trans if location_ref is not None else None

        # convention for exporting
        d = {'opengl': FormatConvention.OpenGL, 'unreal': FormatConvention.Unreal, 'blender': FormatConvention.OpenGL_2}
        format_convention = d.get(export_for.lower())
        if format_convention is None:
            raise ValueError(f'Unsupported export_for value: {export_for}. Supported values are: {list(d.keys())}')

        self._driver.to_alembic(
            output_path,
            mesh_geometry,
            vertex_colour,
            uv_projection_extent,
            transform,
            time_sample_frequency,
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
