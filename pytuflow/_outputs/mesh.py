from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from .helpers.mesh_driver_qgis import QgisMeshDriver
from .map_output import MapOutput, PointLocation, LineStringLocation
from .._pytuflow_types import PathLike, TimeLike
from ..util._util.logging import get_logger


logger = get_logger()


class Mesh(MapOutput):

    def __init__(self, fpath: PathLike):
        super().__init__(fpath)

        self.fpath = Path(fpath)
        self._driver = QgisMeshDriver(self.fpath)
        self._info = pd.DataFrame()

    @staticmethod
    def _looks_like_this(driver: QgisMeshDriver) -> bool:
        return True

    @staticmethod
    def _looks_empty(driver: QgisMeshDriver) -> bool:
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
                    time_fmt: str = 'relative') -> pd.DataFrame:
        """Extracts time series data for the given locations and data types.

        The location can be a single point in the form of a tuple ``(x, y)`` or in the Well Known Text (WKT) format.
        It can also be a list of point or a dictionary of points where the key will be used in the column name
        in the resulting DataFrame.

        The location can also be a GIS point file e.g. Shapefile or GPKG. GPKG's should follow the TUFLOW
        convention if specifying the layer name within the database ``database.gpkg >> layer``. If the GIS layer
        has a field called ``name`` then this will be used as the column name in the resulting DataFrame.

        Parameters
        ----------
        locations : Point | list[Point] | dict[str, Point] | PathLike
            The location to extract the time series data for.
        data_types : str | list[str]
            The data types to extract the time series data for.

        Returns
        -------
        pd.DataFrame
            The time series data.

        Examples
        --------
        Get the water level time-series data for a given point defined as ``(x, y)``:

        >>> xmdf.time_series((293250, 6178030), 'water level')
                time  pnt1/water level
        0   0.000000               NaN
        1   0.083333               NaN
        2   0.166667               NaN
        3   0.250000               NaN
        4   0.333333               NaN
        5   0.416667               NaN
        6   0.500000               NaN
        7   0.583333               NaN
        8   0.666667         41.561204
        9   0.750000         41.838923
        ...    ...                 ...
        32  2.666667         41.278006
        33  2.750000         41.239387
        34  2.833334         41.201996
        35  2.916667         41.166462
        36  3.000000         41.128152

        Get velocity time-series of the points with a shapefile:

        >>> xmdf.time_series('path/to/shapefile.shp', 'vel')
                time  pnt1/velocity
        0   0.000000            NaN
        1   0.083333            NaN
        2   0.166667            NaN
        3   0.250000            NaN
        4   0.333333            NaN
        5   0.416667            NaN
        6   0.500000            NaN
        7   0.583333            NaN
        8   0.666667       0.975577
        9   0.750000       0.914921
        ...    ...              ...
        32  2.666667       0.320217
        33  2.750000       0.270925
        34  2.833334       0.233793
        35  2.916667       0.206761
        36  3.000000       0.183721
        """
        df = pd.DataFrame()
        pnts = self._translate_point_location(locations)
        data_types = self._figure_out_data_types(data_types)
        for name, pnt in pnts.items():
            for dtype in data_types:
                df1 = self._driver.time_series(name, pnt, dtype)
                df = pd.concat([df, df1]) if not df.empty else df1
        return df

    def section(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        pass

    def curtain(self, locations: LineStringLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        pass

    def profile(self, locations: PointLocation, data_types: Union[str, list[str]],
                time: TimeLike) -> pd.DataFrame:
        pass

    def _filter(self, filter_by: str):
        filter_by = [x.strip().lower() for x in filter_by.split('/')] if filter_by else []

        # type - Scalar / Vector
        df = self._info.copy()
        ctx = []
        if 'scalar' in filter_by:
            ctx.append('scalar')
            while 'scalar' in filter_by:
                filter_by.remove('scalar')
        if 'vector' in filter_by:
            ctx.append('vector')
            while 'vector' in filter_by:
                filter_by.remove('vector')
        if ctx:
            df = self._info[self._info['type'].isin(ctx)] if ctx else pd.DataFrame()

        # max/mins
        ctx = []
        df2 = pd.DataFrame()
        if np.intersect1d(filter_by, ['max', 'maximum']).size:
            ctx.append('max')
            df2 = df[df['is_max']]
            filter_by = [x for x in filter_by if x not in ['max', 'maximum']]
        if np.intersect1d(filter_by, ['min', 'minimum']).size:
            ctx.append('min')
            df_ = df[df['is_min']]
            df2 = pd.concat([df2, df_]) if not df2.empty else df_
            filter_by = [x for x in filter_by if x not in ['min', 'minimum']]
        if ctx:
            df = df2

        # static/temporal
        ctx = []
        df3 = pd.DataFrame()
        if 'static' in filter_by:
            ctx.append('static')
            df3 = df[df['static']]
            while 'static' in filter_by:
                filter_by.remove('static')
        if 'temporal' in filter_by:
            ctx.append('temporal')
            df_ = df[~df['static']]
            df3 = pd.concat([df3, df_]) if not df3.empty else df_
            while 'temporal' in filter_by:
                filter_by.remove('temporal')
        if ctx:
            df = df3

        # data type
        if filter_by:
            ctx = [self._get_standard_data_type_name(x) for x in filter_by]
            df = df[df['data_type'].isin(ctx)] if ctx else pd.DataFrame()

        return df

    def _load(self):
        self.name = self.fpath.stem
        self.reference_time = self._driver.reference_time
        self._driver.load()
        d = {'data_type': [], 'type': [], 'is_max': [], 'is_min': [], 'static': [], 'start': [], 'end': [], 'dt': []}
        for dtype in self._driver.data_groups():
            d['type'].append(dtype.type)
            d['is_min'].append('/minimums' in dtype.name.lower())
            d['is_max'].append('/maximums' in dtype.name.lower())
            d['data_type'].append(self._get_standard_data_type_name(dtype.name.split('/')[0]))
            d['start'].append(dtype.times[0])
            d['end'].append(dtype.times[-1])
            static = len(dtype.times) == 1
            d['static'].append(static)
            dt = 0.
            if not static:
                dif = np.diff(dtype.times)
                if np.isclose(dif, dif[0], atol=0.001, rtol=0).all():
                    dt = float(np.round(dif[0] * 3600., decimals=2))
                else:
                    dt = dtype.times
            d['dt'].append(dt)

        self._info = pd.DataFrame(d)

    def _figure_out_data_types(self, data_types: Union[str, list[str]]) -> list[str]:
        if not data_types:
            raise ValueError('No data types provided.')

        data_types = [data_types] if not isinstance(data_types, list) else data_types

        valid_dtypes = self.data_types('temporal')
        dtypes1 = []
        for dtype in data_types:
            stnd = self._get_standard_data_type_name(dtype)
            if stnd not in valid_dtypes:
                logger.warning(f'Invalid data type: {dtype}. Skipping.')
                continue
            dtypes1.append(stnd)

        return dtypes1

