import json
from pathlib import Path
from collections import OrderedDict
from typing import Union

import numpy as np
import pandas as pd

from .map_output import MapOutput, PointLocation, LineStringLocation
from .mesh import Mesh
from .._pytuflow_types import PathLike, TimeLike
from .helpers.catch_providers import CATCHProvider


class CATCHJson(MapOutput):
    """Class for handling TUFLOW CATCH JSON output files.

    The ``CATCHJson`` class will only load header information from the output file on initialisation, this makes the
    class cheap to initialise. The class can be initialised and the methods :meth:`times` and
    :meth:`data_types` can be used without requiring QGIS libraries. However, extracting spatial data requires
    QGIS libraries to be available and QGIS to be initialised. The class will automatically load the full mesh
    the first time a spatial method is called which can cause the first time a spatial method is called to be slow.

    Parameters
    ----------
    fpath : PathLike
        Path to the NetCDF file.

    Examples
    --------
    >>> from pytuflow import CATCHJson
    >>> res = CATCHJson('./path/to/json')

    Get all the data types available in the JSON file:

    >>> res.data_types()
    ['bed level', 'velocity', 'water level', 'salinity', 'temperature']

    Extract the time-series at all the points contained in a shapefile:

    >>> res.time_series('path/to/shapefile.shp', 'water level')
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

    >>> res.time_series('path/to/shapefile.shp', 'velocity', averaging_method='sigma&0.1&0.9')
    time      pnt1/velocity
    0.000000       0.353553
    0.016667       0.353553
    0.033333       0.353553
    0.050000       0.353553
    0.066667       0.353553
    0.083333       0.353553

    Get water level section data using a shapefile:

    >>> res.section('path/to/shapefile.shp', 'water level', 1.0)
          line1
         offset water level
    0  0.000000         0.1
    1  0.605553         0.1
    2  0.605553         0.2
    3  1.614808         0.2
    4  1.614808         0.3
    5  2.220360         0.3

    Get a velocity curtain plot using a shapefile:

    >>> res.curtain('path/to/shapefile.shp', 'velocity', 0.5)
           line1
               x    y  velocity
    0   0.000000  0.0  0.282843
    1   0.605553  0.0  0.282843
    2   0.605553  0.5  0.282843
    3   0.000000  0.5  0.282843
    4   0.000000  0.5  0.424264
    5   0.605553  0.5  0.424264
    6   0.605553  1.0  0.424264
    7   0.000000  1.0  0.424264
    8   0.605553  0.0  0.565685
    9   1.614808  0.0  0.565685
    10  1.614808  0.5  0.565685
    11  0.605553  0.5  0.565685
    12  0.605553  0.5  0.707107
    13  1.614808  0.5  0.707107
    14  1.614808  1.0  0.707107
    15  0.605553  1.0  0.707107
    16  1.614808  0.0  0.848528
    17  2.220360  0.0  0.848528
    18  2.220360  0.5  0.848528
    19  1.614808  0.5  0.848528
    20  1.614808  0.5  0.989949
    21  2.220360  0.5  0.989949
    22  2.220360  1.0  0.989949
    23  1.614808  1.0  0.989949

    Get a velocity (vertical) profile plot using a point shapefile:

    >>> res.profile('path/to/shapefile.shp', 'velocity', 0.5)
           pnt1
      elevation  velocity
    0       0.0  0.282843
    1       0.5  0.282843
    2       0.5  0.424264
    3       1.0  0.424264
    """

    def __init__(self, fpath: PathLike | str):
        super().__init__(fpath)
        self._fpath = Path(fpath)
        self._data = {}
        self._providers = OrderedDict()
        self._idx_provider = None
        self._load_json(fpath)
        self._initial_load()

    @staticmethod
    def _looks_like_this(fpath: Path) -> bool:
        return True

    @staticmethod
    def _looks_empty(fpath: Path) -> bool:
        return False

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
        >>> res = CATCHJson('./path/to/json')
        >>> res.times()
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
        >>> res = CATCHJson('./path/to/json')
        >>> res.data_types()
        ['bed level', 'depth', 'vector velocity', 'velocity', 'water level', 'time of peak h']

        Return only the data types that have maximum values:

        >>> res.data_types('max')
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

        >>> res = CATCHJson('./path/to/json')
        >>> res.time_series((293250, 6178030), 'water level')
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

        >>> res.time_series('path/to/shapefile.shp', 'vel')
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
        df = pd.DataFrame()
        for provider in self._providers.values():
            if provider == self._idx_provider:
                continue
            df = provider.time_series(locations, data_types, time_fmt, averaging_method)
            if not df.empty:
                break
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

        >>> res = ... # Assume res is a loaded CATCHJson object
        >>> res.section([(293250, 6178030), (293500, 6178030)], 'water level', 1.5)
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

        >>> res.section('path/to/shapefile.shp', ['bed level', 'max h'], -1)
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
        df = pd.DataFrame()
        locations = self._translate_line_string_location(locations)
        data_types = self._figure_out_data_types(data_types, None)
        filter_by = '/'.join(data_types)

        # don't want to deal with multiple locations when stitching results together
        for loc, line in locations.items():
            loc = {loc: line}
            dfs = []
            df1 = pd.DataFrame()
            for provider in self._providers.values():
                if provider == self._idx_provider:
                    continue
                if not provider.data_types(filter_by):
                    continue
                df2 = provider.section(loc, data_types, time, averaging_method)
                if not df2.empty:
                    dfs.append((df2, provider.driver.start_end_locs.copy()))

            if dfs:
                for df2, start_end_locs in reversed(dfs):
                    for start_loc, end_loc in start_end_locs:
                        if df1.empty:
                            df1 = df2
                            break
                        else:
                            df1 = self._stamp_section(df1, df2, start_loc, end_loc)

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
        results and a tuple for vector results. Note, velocity will always be returned as vector (tuple) result.

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

        >>> res = ... # Assume res is a loaded CATCHJson object
        >>> res.curtain('path/to/shapefile.shp', 'velocity', 1.5)
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
        df = pd.DataFrame()
        locations = self._translate_line_string_location(locations)

        # don't want to deal with multiple locations when stitching results together
        for locname, line in locations.items():
            loc = {locname: line}
            dfs = []
            df1 = pd.DataFrame()
            for provider in self._providers.values():
                if provider == self._idx_provider:
                    continue
                df2 = provider.curtain(loc, data_types, time)
                if not df2.empty:
                    dfs.append((df2, provider.driver.start_end_locs.copy()))

            if dfs:
                for df2, start_end_locs in reversed(dfs):
                    for start_loc, end_loc in start_end_locs:
                        if df1.empty:
                            df1 = df2
                            break
                        else:
                            df1 = self._stamp_curtain(df1, df2, start_loc, end_loc)

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
        Get The profile for a given point defined in a shapefile:

        >>> res = ... # Assume res is a loaded CATCHJson object
        >>> res.profile('path/to/shapefile.shp', 'velocity', 1.5)
                       pnt1
          elevation  velocity
        0       0.0  0.282843
        1       0.5  0.282843
        2       0.5  0.424264
        3       1.0  0.424264
        """
        df = pd.DataFrame()
        for provider in self._providers.values():
            if provider == self._idx_provider:
                continue
            df = provider.profile(locations, data_types, time, interpolation)
            if not df.empty:
                break
        return df

    def _load_json(self, fpath: PathLike | str):
        if Path(fpath).is_file():
            with Path(fpath).open() as f:
                self._data = json.load(f, object_pairs_hook=OrderedDict)
        else:
            self._data = json.JSONDecoder(object_pairs_hook=OrderedDict).decode(fpath)

    def _initial_load(self):
        self.name = self._data.get('name')
        default_time_string = 'hours since 1990-01-01 00:00:00'
        self.reference_time, _ = self._parse_time_units_string(self._data.get('time units', default_time_string),
                                                        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
                                                        '%Y-%m-%d %H:%M:%S')
        self.units = self._data.get('units', 'metric')
        self._outputs = self._data.get('output data', {})
        self._result_types = [self._get_standard_data_type_name(x) for x in self._data.get('result types')]

        index_result_name = self._data.get('index')
        for res_name in self._data.get('outputs', []):
            output = self._data.get('output data', {}).get(res_name, {})
            provider = CATCHProvider.from_catch_json_output(self._fpath.parent, output)
            if res_name == index_result_name:
                self._idx_provider = provider
            if provider.has_inherent_reference_time:
                provider.time_offset = (provider.reference_time - self.reference_time).total_seconds()
            else:
                provider.reference_time = self.reference_time
            self._providers[res_name] = provider

        self._load_info()

    def _load_info(self):
        self._info = pd.DataFrame(columns=['data_type', 'type', 'is_max', 'is_min', 'static', 'start', 'end', 'dt'])
        for provider in self._providers.values():
            if provider == self._idx_provider:
                continue
            df = provider.info_with_corrected_times()
            self._info = pd.concat([self._info, df], axis=0) if not self._info.empty else df

        self._info = self._info.drop_duplicates()

    @staticmethod
    def _stamp_section(df1: pd.DataFrame, df2: pd.DataFrame, start_loc: float, end_loc: float) -> pd.DataFrame:
        """Inserts the second dataframe into the first dataframe based on the start and end locations."""
        # Cut out the desired section from the second dataframe that will be inserted into the first dataframe
        mask2 = (df2.iloc[:, 0] >= start_loc) & (df2.iloc[:, 0] <= end_loc)
        # If the second dataframe is empty, return the first dataframe
        if mask2.sum() == 0:
            return df1

        # the dataframe can have duplicate "offset" values, we only want the offsets "inside" the start/end locs
        # check for duplicate "offset" values at the start
        inds = np.where(mask2)
        i = 0
        if inds[0].size > 1:
            i, j = inds[0][:2]
            if np.isclose(df2.iloc[i, 0], df2.iloc[j, 0]):
                mask2[i] = False
                i += 1
        # check for duplicate "offset" values at the end
        inds = np.where(~mask2[i:])
        if inds[0].size:
            i += inds[0][0] - 1
            j = i - 1
            if np.isclose(df2.iloc[i, 0], df2.iloc[j, 0]):
                mask2[i] = False
        df2_ = df2[mask2]  # the dataframe with the desired section to be inserted

        # Get the part of the first dataframe that will be before the inserted section
        mask = df1.iloc[:, 0] <= start_loc
        # check for duplicate "offset" values
        inds = np.where(~mask)
        i = inds[0][0] if inds[0].size else df1.shape[0]
        if i > 2:
            if np.isclose(df1.iloc[i - 1, 0], df1.iloc[i - 2, 0]):
                i -= 1
        df = df1.iloc[:i,:] if not np.isclose(df1.iloc[0, 0], start_loc) else pd.DataFrame()

        # combine the first part of the first dataframe with the inserted section
        df = pd.concat([df, df2_], axis=0, ignore_index=True) if not df.empty else df2_
        if not inds[0].size:  # no part of the first dataframe is not before the inserted section
            return df

        # get the part of the first dataframe that will be after the inserted section
        mask = df1.iloc[:, 0] >= end_loc
        # check for duplicate "offset" values
        inds = np.where(mask)
        i = inds[0][0] if inds[0].size else df1.shape[0]
        if inds[0].size > 1:
            if np.isclose(df1.iloc[i,0], df1.iloc[i+1,0]):
                i += 1

        # combine the last part of the first dataframe with the inserted section
        if not np.isclose(df1.iloc[-1, 0], end_loc):
            df = pd.concat([df, df1.iloc[i:, :]], axis=0, ignore_index=True)

        return df

    @staticmethod
    def _stamp_curtain(df1: pd.DataFrame, df2: pd.DataFrame, start_loc: float, end_loc: float) -> pd.DataFrame:
        """Inserts the second dataframe into the first dataframe based on the start and end locations.
        Similar to the _stamp_section() method, but curtain data is a bit different and needs a custom method.
        """
        # Cut out the desired section from the second dataframe that will be inserted into the first dataframe
        mask2 = (df2.iloc[:, 0] >= start_loc) & (df2.iloc[:, 0] <= end_loc)
        df2_ = df2[mask2]  # the dataframe with the desired section to be inserted

        # Get the part of the first dataframe that will be before the inserted section
        mask = df1.iloc[:, 0] <= start_loc
        inds = np.where(~mask)
        if not inds[0].size:
            # no part of the first dataframe is not before the inserted section
            return pd.concat([df1, df2_], axis=0, ignore_index=True)
        df = pd.DataFrame()
        i = inds[0][0]
        if i > 0:
            val = df1.iloc[i-2, 0] if i > 1 else df1.iloc[0, 0]
            if not np.isclose(val, start_loc):  # the insert point is not in the first dataframe and requires inserting
                a = [[start_loc] + df1.iloc[i, 1:].tolist(),
                     [start_loc] + df1.iloc[i + 1, 1:].tolist(),
                     df1.iloc[i + 2, :].tolist()]
                df = pd.concat([df1.iloc[:i,:], pd.DataFrame(a, columns=df1.columns)], axis=0, ignore_index=True)
            elif not np.isclose(df1.iloc[i-1,0], start_loc):
                df = pd.concat([df, df1.iloc[:i, :]], axis=0, ignore_index=True)

        # combine the first part of the first dataframe with the inserted section
        df = pd.concat([df, df2_], axis=0, ignore_index=True) if not df.empty else df2_

        # get the part of the first dataframe that will be after the inserted section
        mask = df1.iloc[:, 0] >= end_loc
        inds = np.where(mask)
        if not inds or not inds[0].size:  # no part of the first dataframe is after the end location
            return df
        i = inds[0][0]
        val = df1.iloc[i, 0]
        if not np.isclose(val, end_loc):  # the insert point is not in the first dataframe and requires inserting
            a = [[end_loc] + df1.iloc[i - 1, 1:].tolist(),
                 df1.iloc[i, :].tolist(),
                 df1.iloc[i + 1, :].tolist(),
                 [end_loc] + df1.iloc[i + 2, 1:].tolist()]
            i += 3
            df = pd.concat([df, pd.DataFrame(a, columns=df.columns)], axis=0, ignore_index=True)

        # combine the last part of the first dataframe with the inserted section
        if not np.isclose(df1.iloc[-2,0], end_loc):
            df = pd.concat([df, df1.iloc[i:,:]], axis=0, ignore_index=True)

        return df
