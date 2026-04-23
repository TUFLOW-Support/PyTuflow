import abc
import re
from abc import ABC
from collections import OrderedDict
from collections.abc import Iterable
from typing import Union

import numpy as np
try:
    import pandas as pd
except ImportError:
    from .pymesh.stubs import pandas as pd

from .output import Output, PlotExtractionLocation
from .._pytuflow_types import PathLike
from ..util import gis
from ..util import pytuflow_logging
from .pymesh import PointMixin, LineStringMixin
from .._tmf import Geom, Feature

try:
    import shapely
    from shapely import LineString, MultiLineString, Point, MultiPoint
except ImportError:
    shapely = None
    LineString = str
    MultiLineString = str
    Point = str
    MultiPoint = str

try:
    import geopandas as gpd
    from geopandas import GeoDataFrame
except ImportError:
    gpd = None
    GeoDataFrame = str

logger = pytuflow_logging.get_logger()

PointLike = tuple[float, float] | str | Point | MultiPoint | Geom | Feature
LineStringLike = list[PointLike] | tuple[PointLike] | LineString | MultiLineString | Geom | Feature

Points = list[PointLike]
LineStrings = list[LineStringLike]

PointLocation = PointLike | Points | PathLike | GeoDataFrame
LineStringLocation = LineStringLike | LineStrings | PathLike | GeoDataFrame


class MapOutput(Output, ABC, PointMixin, LineStringMixin):
    ATTRIBUTE_TYPES = {'scalar': ['scalar'], 'vector': ['vector']}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._info = pd.DataFrame(columns=['data_type', 'type', 'is_max', 'is_min', 'static', '3d', 'start', 'end', 'dt'])

    @abc.abstractmethod
    def load_into_memory(self, data_types: str | list[str]):
        """Load the given data types into memory. This loads the entire dataset, including all timesteps, which
        can greatly improve the speed of queries by removing the need for frequent and relatively expensive I/O operations.
        Any accompanying data will also be loaded, e.g. the active (wet/dry) flags.
        
        Loading data types into memory can be a relatively slow process, however it will speed up subsequent queries. 
        The speed up is relative to how many I/O operations a given method makes.
        e.g. The ``flux()`` method makes many I/O calls and it can typically be beneficial to load the relevant 
        results into memory if making more than two ``flux()`` calls on a result. On the other hand,
        the ``section()`` method  will typically only make two queries, one for the data and one for the active 
        flag. As a consequence, it may not be worth loading the data into memory for ``section()`` calls as 
        the cost of loading into memory outweighs the subsequent speed up. It will vary depending on the results,
        the calls being made, and where the results are located (e.g. locally or network drive).

        .. note::

            The maximum and temporal datasets are considered separate datasets e.g. loading ``water level`` into memory 
            will not load ``maximum water level`` and vise versa. It is also not supported in v1.0 mesh drivers.
        
        .. note::

            QGIS drivers, specifically the result extraction drivers, are much slower than ``h5py`` and ``netcdf4`` 
            for extracting entire data types results. In one test case, ``h5py`` took ~4.5 s to load both 
            ``vector velocity`` and ``depth``, whereas QGIS drivers took ~60 s. 
            This can still be beneficial if exporting hundreds of flux locations, however it is 
            much better to use a different driver if possible. Note, it is possible to use QGIS for geometry and ``netcdf4`` 
            for result extraction which will negate this problem. In fact, the TUFLOW Viewer V2 (part of the TUFLOW plugin 
            in QGIS) uses this capability and preferences ``netcdf4`` if it is available and QGIS for the geometry.

            This is not intended to disparage QGIS. Libraries such as ``h5py`` have been specifically optimised for 
            getting entire datasets from hdf5 files into Python. So naturally they are very quick at this task.
            General data extraction in QGIS, given single timesteps, are comparable to speeds in ``h5py``.

        Parameters
        ----------
        data_types : str | list[str]
            The result type(s) to load into memory.
        
        Examples
        --------
        Load a result type into memory to speed up ``flux()`` calls.

        >>> res = ... # assume res is a loaded mesh or grid result file
        >>> res.load_into_memory('vector unit flow')
        >>> df = res.flux('/path/to/flux_line.shp')

        If unit flow is not available, the depth and velocity will be needed. Note, just velocity is needed for 
        :class:`NCMesh<pytuflow.NCMesh>` results as the depth is stored within the vertical layer elevation data.

        >>> res.load_into_memory(['depth', 'vector velocity'])
        >>> df = res.flux('/path/to/flux_line.shp')
        """
        raise NotImplementedError

    @abc.abstractmethod
    def flux(self, locations: LineStringLocation, data_types: str | list[str] = 'unit flow',
             time_fmt: str = 'relative', use_unit_flow: bool = True, *args, **kwargs) -> pd.DataFrame:
        r"""Returns the flux across a line. Tracer data type(s) can be provided to calculate the mass flux of a constituent.
        By default, the routine will preference the use of unit flow, otherwise depth and velocity is used.

        Multiple flux calls on the same result can potentially be sped up by pre-loading the relevant results
        into memory. For example, loading ``vector unit flow`` into memory, or if unit flow does not exist
        in the result, then loading ``vector velocity`` and ``depth`` into memory (just ``velocity`` is required for
        :class:`NCMesh<pytuflow.NCMesh>` results).

        .. note::

            The ``flux`` calculation requires vector results. For HPC/Classic ``.xmdf`` results, these will be labelled
            ``vector unit flow`` and ``vector velocity`` (not ``unit flow`` and ``velocity``, these are scalar results).
            Make sure to choose the correct result types if loading results into memory.

        Does not currently support groundwater flux calculation.

        .. warning::

            The result of the ``flux()`` method should be used with care. Due to result interpolation, the resulting
            flux could be off by 10% or more. The error depends on variables such as the result format, the hydraulic engine 
            that created the results, whether SGS was used, and the line location.
            
            As an example, the TUFLOW HPC tutorial model was run at a 10 m cell size (the tutorial model is usually run at 5 m) 
            with SGS on. The peak flow from a PO line gave a result of 90 m\ :sup:`3`\ /s, and 
            the equivalent ``flux()`` call gave 81 m\ :sup:`3`\ /s using ``use_unit_flow=True``, and
            76 m\ :sup:`3`\ /s when using ``use_unit_flow=False``. That is an underprediction of 10% or more.

            The same test with a 5 m cell size, and with SGS turned off, resulted in ``XMDF.flux()`` predicting a much closer peak.
            The estimate peak was within 1% of the PO line. The ``NCGrid.flux()`` predicted even closer with a peak less 
            than 1% different. Other real world tests have shown that ``XMDF.flux()`` is typically within 5% of the PO 
            result given sufficient cell resolution across the flowpath and SGS is off (it is recommended to use the
            unit flow result if SGS is turned on, rather than use depth and velocity).

            The same test was run with TUFLOW FV using the NetCDF output format. In this case, the ``NCMesh.flux()`` method returned
            an estimate that was almost identical to the flux output from TUFLOW FV (the peak was within ~0.2%). This is due to the interpolation,
            or lack thereof in this instance. TUFLOW FV calculates both water level and velocity at the cell centre, and the NetCDF output
            writes values to the cell centre. Note, the ``NCMesh.flux()`` estimate is not guaranteed to always be this close, particularly when
            using spherical coordinates.

        Parameters
        ----------
        locations : LineString | list[LineString] | dict[str, LineString] | GeoDataFrame | str | PathLike
            The line(s) to extract the flux for. The location can be:
            
            - A linestring represented by a list of ``tuple[x, y]`` coordinates.
            - A linestring represented by a WKT string
            - A ``shapely.LineString`` object
            - A list of of LineStrings
            - A ``dict[str, LineString]`` where the ``str`` will be used as the ID in the resulting ``pd.DataFrame``
            - A ``geopandas.GeoDataFrame``
            - A path to a GIS file containing lines
        data_types : str | list[str], optional
            The result type(s) to extract the flux for. If left blank, the returned flux will be the flow across the line.
            If ``data_types`` are provided, this should typically be a tracer concentration (e.g. ``mg/L``). In these
            cases, the returned flux will the mass flux (``g/s``) across the line.
        time_fmt : str, optional
            The format for the time values. Options are 'relative' or 'absolute'.
        use_unit_flow : bool, optional
            Use unit flow if it is available. Otherwise the fallback is depth x velocity. The resulting data frame column name will have either ``(q)``
            if unit flow was used, or ``(d.v)`` if depth x velocity was used.

        Returns
        -------
        pd.DataFrame
            An array containing the extracted flux across the line.

        Examples
        --------
        Extract the flow across a line:

        >>> res = ... # assume res is a Mesh or NCGrid output
        >>> Q = res.flux('/path/to/line.shp')
        >>> Q
              locA/flux (q)
        time
        0.0        0.000000
        0.5        0.000000
        1.0       81.115922
        1.5       52.226762
        2.0       17.359964
        2.5        8.920063
        3.0        4.825885

        Extract the mass flux across a line:

        >>> Q_mass = res.flux('/path/to/line.shp', 'conc tracer1')
        >>> Q_mass
              locA/flux conc tracer1 (q)
        time
        0.0                     0.000000
        0.5                     0.000000
        1.0                    89.579868
        1.5                   123.392674
        2.0                   102.520215
        2.5                   101.631599
        3.0                   100.038073
        """
        raise NotImplementedError

    @staticmethod
    def _get_standard_data_type_name(name: str) -> str:
        """Override base method to consider explicit calls to max, min, and time of max datasets."""
        if name == 'q':
            return 'unit flow'

        name1 = name.split('/')[0].strip()
        name1 = re.sub(r'\sMaximums$', '', name1, flags=re.IGNORECASE)
        name1 = re.sub(r'^hazard_', '', name1, flags=re.IGNORECASE)
        stnd_name = Output._get_standard_data_type_name(name1)
        if stnd_name.startswith('conc wq_'):
            stnd_name = stnd_name[5:]
        if re.findall(r'^(?:max\s)?vector', name, flags=re.IGNORECASE):
            stnd_name = f'vector {stnd_name}'

        if not re.findall(r'(max|peak|min)', name, re.IGNORECASE):
            return stnd_name

        if re.findall(r'(tmax|time[\s_-]+of[\s_-](?:peak|max))', name, re.IGNORECASE):
            return 'tmax ' + stnd_name

        if re.findall(r'(max|peak)', name, re.IGNORECASE):
            if stnd_name.startswith('maximum_'):
                stnd_name = stnd_name[8:]
            new_name = 'max ' + stnd_name
            if len(re.findall(r'max', new_name, re.IGNORECASE)) > 1 and 'tmax' not in new_name:
                return stnd_name
            return new_name

        if re.findall(r'(tmin|time[\s_-]+of[\s_-]+min)', name, re.IGNORECASE):
            if stnd_name.startswith('minimum_'):
                stnd_name = stnd_name[8:]
            return 'tmin ' + stnd_name

        new_name = 'min ' + stnd_name
        if len(re.findall(r'min', new_name, re.IGNORECASE)) > 1 and 'tmin' not in new_name:
            return stnd_name
        return new_name

    def _overview_dataframe(self) -> pd.DataFrame:
        return self._info.copy()

    @staticmethod
    def _replace_aliases(filter_by: str) -> str:
        """Replace aliases in the filter_by string."""
        filter_by = [x.strip().lower() for x in filter_by.split('/')] if filter_by else []
        while 'section' in filter_by:
            filter_by.remove('section')
        while 'curtain' in filter_by:
            filter_by.remove('curtain')
        while 'profile' in filter_by:
            filter_by.remove('profile')
        while 'line' in filter_by:
            filter_by.remove('line')
        while 'point' in filter_by:
            filter_by.remove('point')
        return '/'.join(filter_by)

    def _filter(self, filter_by: str, filtered_something: bool = False, df: pd.DataFrame = None,
                ignore_excess_filters: bool = False) -> tuple[pd.DataFrame, dict[str, bool]]:
        # MapOutput always rebuilds from its own _overview_dataframe; the inherited
        # `filtered_something` and `df` parameters are intentionally not forwarded here
        # because map outputs use a different pre-filtering strategy (max/min, static,
        # 2d/3d) before delegating remaining tokens to the base _filter.
        filter_by = self._replace_aliases(filter_by)
        filter_by = [x.strip().lower() for x in filter_by.split('/')] if filter_by else []

        filtered_something = False
        df = self._overview_dataframe()

        # min/max
        max_min = {'is_max': {True: ['max', 'maximum']}, 'is_min': {True: ['min', 'minimum']}}
        for col_name, filter_dict in max_min.items():
            df, filtered_something_ = self._filter_generic(filter_by, df, filter_dict, col_name)
            if filtered_something_:
                filtered_something = True

        # static/temporal
        df, filtered_something_ = self._filter_generic(filter_by, df, {True: ['static']}, 'static')
        if filtered_something_:
            filtered_something = True
        df, filtered_something_ = self._filter_generic(filter_by, df, {True: ['temporal', 'timeseries']}, 'static', exclude=True)
        if filtered_something_:
            filtered_something = True

        # 2d/3d
        df, filtered_something_ = self._filter_generic(filter_by, df, {True: ['2d']}, '3d', exclude=True)
        if filtered_something_:
            filtered_something = True
        df, filtered_something_ = self._filter_generic(filter_by, df, {True: ['3d']},'3d')
        if filtered_something_:
            filtered_something = True

        filter_by = '/'.join(filter_by)
        return super()._filter(filter_by, filtered_something, df)

    def _figure_out_data_types(self, data_types: Union[str, list[str]], filter_by: str | None) -> list[str]:
        if not data_types:
            raise ValueError('No data types provided.')

        data_types = [data_types] if not isinstance(data_types, list) else data_types

        valid_dtypes = self.data_types(filter_by)

        dtypes1 = []
        for dtype in data_types:
            stnd = self._get_standard_data_type_name(dtype)
            if stnd not in valid_dtypes:
                logger.warning(f'Invalid data type: {dtype}. Skipping.')
                continue
            dtypes1.append(stnd)

        return dtypes1

    def _figure_out_data_types_game_mesh(self, data_types: str | list[str], filter_by: str | None) -> list[str]:
        """Allow for '-x' and '-y' suffixes to indicate vector components."""
        if isinstance(data_types, str):
            data_types = [data_types]

        data_types_ = []
        suffixes = []
        for dt in data_types:
            if dt.endswith('-x'):
                data_type_name = dt[:-2]
                suffix = '-x'
            elif dt.endswith('-y'):
                data_type_name = dt[:-2]
                suffix = '-y'
            else:
                data_type_name = dt
                suffix = ''
            data_types_.append(data_type_name)
            suffixes.append(suffix)

        data_types = self._figure_out_data_types(list(data_types_), filter_by)
        return [f'{dt}{sfx}' for dt, sfx in zip(data_types, suffixes)]

    def _translate_point_location(self, locations: PointLocation, name: str = '') -> dict[str, Point]:
        """Translate, as in to understand, not a spatial translation."""
        if gpd and isinstance(locations, (pd.DataFrame, np.ndarray)) and not locations.size:
            return {}
        if not isinstance(locations, (pd.DataFrame, np.ndarray)) and not locations:
            return {}

        pnts = {}
        i = 0
        if isinstance(locations, Iterable) and not isinstance(locations, str):  # assumes a list of points, does not support a list of files
            if isinstance(locations, str):
                try:
                    pnts['pnt1'] = self._wkt_point_to_tuple(locations)
                    return pnts
                except ValueError:
                    pass
            elif gpd and isinstance(locations, GeoDataFrame):
                for j, (_, feat) in enumerate(locations.iterrows()):
                    attrs = OrderedDict()
                    for col in locations.columns:
                        if col != 'geometry':
                            attrs[col] = feat[col]
                    geom = feat.geometry
                    feat = Feature(geom, attrs, geom.geom_type)
                    pnts.update(self._translate_point_location(feat, name=f'pnt{j + 1}'))
                return pnts
            elif isinstance(locations, dict):
                for key, loc in locations.items():
                    pnts.update(self._translate_point_location(loc, name=key))
                return pnts
            elif shapely and isinstance(locations[0], (LineString, MultiLineString, Geom, Feature)):
                for j, loc in enumerate(locations):
                    pnts.update(self._translate_point_location(loc), name=f'pnt{j+1}')
                return pnts
            elif len(locations) == 2 and all(isinstance(loc, (float, int)) for loc in locations):
                name = name if name else 'pnt1'
                pnts[name] = tuple(locations)
                return pnts
            else:
                for j, loc in enumerate(locations):
                    pnts.update(self._translate_point_location(loc, name=f'pnt{j + 1}'))
                return pnts
        elif shapely and isinstance(locations, Point):
            name = name if name else 'pnt1'
            pnts[name] = self._coerce_into_point(locations)
            return pnts
        elif shapely and isinstance(locations, MultiPoint):
            name = name if name else 'pnt1'
            multi = len(locations.geoms) > 1
            for j, loc in enumerate(locations.geoms):
                pnts[name if not multi else f'{name}{chr(97 + j)}'] = self._coerce_into_point(loc)
            return pnts
        elif isinstance(locations, Geom):
            if locations.geometry_type() not in ['Point', 'MultiPoint']:
                logger.warning(f'Geom with geometry type {locations.geometry_type()} cannot be translated to a point location. Skipping.')
                return {}
            name = name if name else 'pnt1'
            pnts_ = locations.points()
            multi = len(pnts_) > 1
            for j, loc in enumerate(pnts_):
                pnts[name if not multi else f'{name}{chr(97 + j)}'] = loc
            return pnts
        elif isinstance(locations, Feature):
            if locations.geom.geometry_type() not in ['Point', 'MultiPoint']:
                logger.warning(
                    f'Geom with geometry type {locations.geom.geometry_type()} cannot be translated to a point location. Skipping.')
                return {}
            id_fields = ['id', 'label', 'name']
            attr = OrderedDict([(k.lower(), v) for k, v in locations.attrs.items()])
            pnts_ = locations.geom.points()
            multi = len(pnts_) > 1
            name_ = None
            for id_field in id_fields:
                if id_field in attr:
                    name_ = attr[id_field]
                    break
            name_ = name_ if name_ else name
            name_ = name_ if name_ else 'pnt1'
            for j, loc in enumerate(pnts_):
                pnts[name_ if not multi else f'{name_}{chr(97 + j)}'] = loc
            return pnts
        elif isinstance(locations, str):
            name_ = name if name else 'pnt1'
            try:
                pnts[name_] = self._wkt_point_to_tuple(locations)
                return pnts
            except ValueError:
                pass

        return gis.point_gis_file_to_dict(locations)

    def _translate_line_string_location(self, locations: LineStringLocation, name: str = '') -> dict[str, LineString]:
        if gpd and isinstance(locations, (pd.DataFrame, np.ndarray)) and not locations.size:
            return {}
        elif not isinstance(locations, (pd.DataFrame, np.ndarray)) and not locations:
            return {}

        lines = {}
        i = 0
        if isinstance(locations, Iterable):
            if isinstance(locations, str):  # wkt line-string or path - try wkt first
                try:
                    lines['line1'] = self._wkt_line_to_list(locations)
                    return lines
                except ValueError:  # assume it's a path then
                    pass
            elif gpd and isinstance(locations, GeoDataFrame):
                for j, (_, feat) in enumerate(locations.iterrows()):
                    attrs = OrderedDict()
                    for col in locations.columns:
                        if col != 'geometry':
                            attrs[col] = feat[col]
                    geom = feat.geometry
                    feat = Feature(geom, attrs, geom.geom_type)
                    lines.update(self._translate_line_string_location(feat, name=f'line{j + 1}'))
                return lines
            elif isinstance(locations, dict):
                for key, loc in locations.items():
                    lines.update(self._translate_line_string_location(loc, name=key))
                return lines
            elif shapely and isinstance(locations[0], (LineString, MultiLineString, Geom, Feature)):
                for j, loc in enumerate(locations):
                    lines.update(self._translate_line_string_location(loc), name=f'line{j+1}')
                return lines
            elif self._list_depth(locations) == 2:  # [(0, 0), (1, 1)] - a single line-string, not a list of line-strings
                name_ = name if name else 'line1'
                lines[name_] = locations
                return lines
            elif self._list_depth(locations) == 3:  # list of line-strings
                for loc in locations:
                    i += 1
                    key = f'line{i}'
                    lines[key] = loc
                return lines
            else:
                for j, loc in enumerate(locations):
                    lines.update(self._translate_line_string_location(loc, name=f'line{j+1}'))
                return lines
        elif shapely and isinstance(locations, LineString):
            name = name if name else 'line1'
            lines[name] = self._coerce_into_line(locations)
            return lines
        elif shapely and isinstance(locations, MultiLineString):
            name = name if name else 'line1'
            multi = len(locations.geoms) > 1
            for j, loc in enumerate(locations.geoms):
                lines[name if not multi else f'{name}{chr(97 + j)}'] = self._coerce_into_line(loc)
            return lines
        elif isinstance(locations, Geom):
            if locations.geometry_type() not in ['LineString', 'MultiLineString']:
                logger.warning(f'Geom with geometry type {locations.geometry_type()} cannot be translated to a line-string location. Skipping.')
                return {}
            name = name if name else 'line1'
            lines_ = locations.lines()
            multi = len(lines_) > 1
            for j, loc in enumerate(lines_):
                lines[name if not multi else f'{name}{chr(97 + j)}'] = loc
            return lines
        elif isinstance(locations, Feature):
            if locations.geom.geometry_type() not in ['LineString', 'MultiLineString']:
                logger.warning(
                    f'Geom with geometry type {locations.geom.geometry_type()} cannot be translated to a line-string location. Skipping.')
                return {}
            id_fields = ['id', 'label', 'name']
            attr = OrderedDict([(k.lower(), v) for k, v in locations.attrs.items()])
            lines_ = locations.geom.lines()
            multi = len(lines_) > 1
            name_ = None
            for id_field in id_fields:
                if id_field in attr:
                    name_ = attr[id_field]
                    break
            name_ = name_ if name_ else name
            name_ = name_ if name_ else 'line1'
            for j, loc in enumerate(lines_):
                lines[name_ if not multi else f'{name_}{chr(97 + j)}'] = loc
            return lines
        elif isinstance(locations, str):
            try:
                lines['line1'] = self._wkt_line_to_list(locations)
                return lines
            except ValueError:
                pass


        return gis.line_gis_file_to_dict(locations)  # assume it is a file path

    @staticmethod
    def _wkt_point_to_tuple(point: str) -> tuple[float, ...]:
        if not re.match(r'^POINT\s*\(\s*[-+]?\d*\.?\d+\s+[-+]?\d*\.?\d+\s*\)$', point):
            raise ValueError(f'Invalid WKT point string: {point}')
        return tuple([float(x) for x in re.split(r'\s+', point.strip('\n\t )').split('(')[1], maxsplit=1)])

    @staticmethod
    def _wkt_line_to_list(line: str) -> list[tuple[float, ...]]:
        if not re.match(r'^LINESTRING\s*\(\s*[-+]?\d*\.?\d+\s+[-+]?\d*\.?\d+\s*(,\s*[-+]?\d*\.?\d+\s+[-+]?\d*\.?\d+\s*)*\)$', line):
            raise ValueError(f'Invalid WKT line-string string: {line}')
        return [tuple([float(x) for x in p.split()]) for p in re.split(r'\s*,\s*', line.strip('\n\t )').split('(')[1])]

    @staticmethod
    def _list_depth(lst: Iterable) -> int:
        def is_bottom(lst1: Iterable) -> bool:
            return all(isinstance(x, (float, int, str)) for x in lst1)

        dep = 1
        lst_ = lst
        while not is_bottom(lst_):
            dep += 1
            try:
                lst_ = lst_[0]
            except (TypeError, IndexError):
                break

        return dep

    @staticmethod
    def _calculate_time_step(times: np.ndarray) -> float | tuple[float, ...]:
        dif = np.diff(times)
        if np.isclose(dif[:-1], dif[0], atol=0.01, rtol=0).all():
            dt = float(np.round(dif[0], decimals=2))
        else:
            dt = tuple(times)
        return dt

    @staticmethod
    def _merge_line_dataframe(df1: pd.DataFrame, df2: pd.DataFrame, name: str, reset_index: bool) -> pd.DataFrame:
        if df2.empty:
            return df1
        if reset_index:
            df2.reset_index(inplace=True, drop=False)
        df2.columns = pd.MultiIndex.from_tuples([(name, x) for x in df2.columns])
        return pd.concat([df1, df2], axis=1) if not df1.empty else df2
