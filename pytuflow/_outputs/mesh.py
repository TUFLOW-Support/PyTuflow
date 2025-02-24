import re
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from .helpers.mesh_driver_qgis import QgisMeshDriver
from .helpers.mesh_driver_nc import NCMeshDriver
from .map_output import MapOutput, PointLocation, LineStringLocation
from .._pytuflow_types import PathLike, TimeLike
from ..util._util.logging import get_logger
from .output import Output


logger = get_logger()


class Mesh(MapOutput):
    """Abstract base class for Mesh outputs."""

    def __init__(self, fpath: PathLike):
        super().__init__(fpath)

        self.fpath = Path(fpath)
        self._driver = QgisMeshDriver(self.fpath)
        self._soft_load_driver = NCMeshDriver(self.fpath)  # QGIS driver cannot soft load (i.e. without loading 2dm)
        self._info = pd.DataFrame()
        self._loaded = False

    @staticmethod
    def _looks_like_this(fpath: Path) -> bool:
        return True

    @staticmethod
    def _looks_empty(driver: QgisMeshDriver) -> bool:
        return False

    @staticmethod
    def _get_standard_data_type_name(name: str) -> str:
        """Override base method to consider explicit calls to max, min, and time of max datasets."""
        name1 = name.split('/')[0]
        name1 = re.sub(r'\sMaximums$', '', name1)
        stnd_name = Output._get_standard_data_type_name(name1)
        if not re.findall(r'(max|peak|min)', name, re.IGNORECASE):
            return stnd_name

        if re.findall(r'(tmax|time[\s_-]+of[\s_-](?:peak|max))', name, re.IGNORECASE):
            return 'tmax ' + stnd_name

        if re.findall(r'(max|peak)', name, re.IGNORECASE):
            return 'max ' + stnd_name

        if re.findall(r'(tmin|time[\s_-]+of[\s_-]+min)', name, re.IGNORECASE):
            return 'tmin ' + stnd_name

        return 'min ' + stnd_name

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
        >>> mesh.data_types()
        ['bed level', 'depth', 'vector velocity', 'velocity', 'water level', 'time of peak h']

        Return only the data types that have maximum values:

        >>> mesh.data_types('max')
        ['depth', 'vector velocity', 'velocity', 'water level']
        """
        return super().data_types(filter_by)

    def time_series(self, locations: PointLocation, data_types: Union[str, list[str]],
                    time_fmt: str = 'relative', averaging_method: str = None) -> pd.DataFrame:
        """Extracts time-series data for the given locations and data types.

        The ``locations`` can be a single point in the form of a tuple ``(x, y)`` or in the Well Known Text (WKT)
        format. It can also be a list of point or a dictionary of points where the key will be used in the column name
        in the resulting DataFrame.

        The location can also be a GIS point file e.g. Shapefile or GPKG. GPKG's should follow the TUFLOW
        convention if specifying the layer name within the database ``database.gpkg >> layer``. If the GIS layer
        has a field called ``name`` or ``label`` then this will be used as the column name in the resulting DataFrame.

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

        >>> xmdf.time_series((293250, 6178030), 'water level')
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

        >>> xmdf.time_series('path/to/shapefile.shp', 'vel')
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
                df1 = self._driver.time_series(name, pnt, dtype, averaging_method)
                if df1.empty:
                    continue
                if not df.empty:
                    if np.isclose(df.index, df1.index, atol=0.0001, rtol=0).all():
                        df1.index = df.index
                    else:
                        raise ValueError('Time series index does not match between datasets.')
                df = pd.concat([df, df1], axis=1) if not df.empty else df1
        return df

    def section(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike, averaging_method: str = None) -> pd.DataFrame:
        """Extracts section data for the given locations and data types.

        The ``locations`` can be a list of ``x, y`` tuple points, or a Well Known Text (WKT) line string. It can also
        be a dictionary of key, line-string pairs where the key is the name that will be used in the column name in
        the resulting DataFrame.

        The ``locations`` argument can also be a single GIS file path e.g. Shapefile or GPKG. GPKG's should follow the
        TUFLOW convention if specifying the layer name within the database ``database.gpkg >> layer``. If the GIS layer
        has a field called ``name`` or ``label`` then this will be used as the column name in the resulting DataFrame.

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

        >>> xmdf.section([(293250, 6178030), (293500, 6178030)], 'water level', 1.5)
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

        >>> xmdf.section('path/to/shapefile.shp', ['bed level', 'max h'], -1)
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
                df2 = self._driver.section(line, dtype, time, averaging_method)
                if df2.empty:
                    continue
                df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2
            if df1.empty:
                continue
            df1.reset_index(inplace=True, drop=False)
            df1.columns = pd.MultiIndex.from_tuples([(name, x) for x in df1.columns])
            df = pd.concat([df, df1], axis=1) if not df.empty else df1

        return df

    def curtain(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        """Extracts curtain data for the given locations and data types.

        The ``locations`` can be a list of ``x, y`` tuple points, or a Well Known Text (WKT) line string. It can also
        be a dictionary of key, line-string pairs where the key is the name that will be used in the column name in
        the resulting DataFrame.

        The ``locations`` argument can also be a single GIS file path e.g. Shapefile or GPKG. GPKG's should follow the
        TUFLOW convention if specifying the layer name within the database ``database.gpkg >> layer``. If the GIS layer
        has a field called ``name`` or ``label`` then this will be used as the column name in the resulting DataFrame.

        The resulting DataFrame will be made up of 3 columns- ``X, Y, value`` data. The ``X, Y`` values represent
        cells in the vertical plane, and should be treated as groups of 4 which denote the corners of a cell. The
        ``value`` represents the data value at that cell, which will be returned as a single number for scalar
        results and a tuple for vector results.

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

        >>> mesh.curtain('path/to/shapefile.shp', 'velocity', 1.5)
                 Line_1
                      x          y  velocity
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
                df2 = self._driver.curtain(line, dtype, time)
                if df2.empty:
                    continue
                df1 = pd.concat([df1, df2[dtype]], axis=1) if not df1.empty else df2
            if df1.empty:
                continue
            df1.columns = pd.MultiIndex.from_tuples([(name, x) for x in df1.columns])
            df = pd.concat([df, df1], axis=1) if not df.empty else df1

        return df

    def profile(self, locations: PointLocation, data_types: Union[str, list[str]],
                time: TimeLike, interpolation: str = 'stepped') -> pd.DataFrame:
        """Extracts vertical profile data for the given locations and data types.

        The ``locations`` can be a single point in the form of a tuple ``(x, y)`` or in the Well Known Text (WKT)
        format. It can also be a list of point or a dictionary of points where the key will be used in the column name
        in the resulting DataFrame.

        The location can also be a GIS point file e.g. Shapefile or GPKG. GPKG's should follow the TUFLOW
        convention if specifying the layer name within the database ``database.gpkg >> layer``. If the GIS layer
        has a field called ``name`` or ``label`` then this will be used as the column name in the resulting DataFrame.

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
        Get The profile for a given point defined in a shapefile.
        """
        self._load()
        df = pd.DataFrame()
        pnts = self._translate_point_location(locations)
        data_types = self._figure_out_data_types(data_types, None)
        for name, pnt in pnts.items():
            df1 = pd.DataFrame()
            for dtype in data_types:
                df2 = self._driver.profile(pnt, dtype, time, interpolation)
                if df2.empty:
                    continue
                df1 = pd.concat([df1, df2], axis=1) if not df1.empty else df2
            if df1.empty:
                continue
            df1.reset_index(inplace=True, drop=False)
            df1.columns = pd.MultiIndex.from_tuples([(name, x) for x in df1.columns])
            df = pd.concat([df, df1], axis=1) if not df.empty else df1

        return df

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
        self.reference_time = driver.reference_time
        d = {'data_type': [], 'type': [], 'is_max': [], 'is_min': [], 'static': [], 'start': [], 'end': [], 'dt': []}
        for dtype in driver.data_groups():
            d['type'].append(dtype.type)
            d['is_min'].append('/minimums' in dtype.name.lower())
            d['is_max'].append('/maximums' in dtype.name.lower())
            d['data_type'].append(self._get_standard_data_type_name(dtype.name))
            d['start'].append(np.round(dtype.times[0], decimals=6))
            d['end'].append(np.round(dtype.times[-1], decimals=6))
            static = len(dtype.times) == 1
            d['static'].append(static)
            dt = 0.
            if not static:
                dif = np.diff(dtype.times)
                if np.isclose(dif[:-1], dif[0], atol=0.001, rtol=0).all():
                    dt = float(np.round(dif[0] * 3600., decimals=2))
                else:
                    dt = tuple(dtype.times)
            d['dt'].append(dt)

        self._info = pd.DataFrame(d)

    def _load(self):
        if self._loaded:
            return
        self._driver.load()
        self._loaded = True
