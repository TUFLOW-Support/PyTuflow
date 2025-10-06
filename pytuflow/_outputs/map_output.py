import re
from abc import ABC
from collections.abc import Iterable
from typing import Union

import numpy as np
import pandas as pd

from .output import Output
from .._pytuflow_types import PathLike
from ..util import gis
from ..util import pytuflow_logging


logger = pytuflow_logging.get_logger()

Point = tuple[float, float] | str
LineString = list[Point] | tuple[Point]

Points = list[Point]
LineStrings = list[LineString]

PointLocation = Point | Points | PathLike
LineStringLocation = LineStrings | PathLike


class MapOutput(Output, ABC):
    ATTRIBUTE_TYPES = {'scalar': ['scalar'], 'vector': ['vector']}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._info = pd.DataFrame(columns=['data_type', 'type', 'is_max', 'is_min', 'static', '3d', 'start', 'end', 'dt'])

    @staticmethod
    def _get_standard_data_type_name(name: str) -> str:
        """Override base method to consider explicit calls to max, min, and time of max datasets."""
        name1 = name.split('/')[0].strip()
        name1 = re.sub(r'\sMaximums$', '', name1, flags=re.IGNORECASE)
        name1 = re.sub(r'^hazard_', '', name1, flags=re.IGNORECASE)
        stnd_name = Output._get_standard_data_type_name(name1)
        if not re.findall(r'(max|peak|min)', name, re.IGNORECASE):
            return stnd_name

        if re.findall(r'(tmax|time[\s_-]+of[\s_-](?:peak|max))', name, re.IGNORECASE):
            return 'tmax ' + stnd_name

        if re.findall(r'(max|peak)', name, re.IGNORECASE):
            if stnd_name.startswith('maximum_'):
                stnd_name = stnd_name[8:]
            return 'max ' + stnd_name

        if re.findall(r'(tmin|time[\s_-]+of[\s_-]+min)', name, re.IGNORECASE):
            if stnd_name.startswith('minimum_'):
                stnd_name = stnd_name[8:]
            return 'tmin ' + stnd_name

        return 'min ' + stnd_name

    def _overview_dataframe(self) -> pd.DataFrame:
        return self._info.copy()

    @staticmethod
    def _replace_aliases(filter_by: str) -> str:
        """Replace aliases in the filter_by string."""
        filter_by = [x.strip().lower() for x in filter_by.split('/')] if filter_by else []
        while 'section' in filter_by:
            filter_by.remove('section')
        return '/'.join(filter_by)

    def _filter(self, filter_by: str, filtered_something: bool = False, df: pd.DataFrame = None,
                ignore_excess_filters: bool = False) -> pd.DataFrame:
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
        if filter_by != 'temporal':
            valid_dtypes.extend(['max ' + x for x in self.data_types('max')])
            valid_dtypes.extend(['min ' + x for x in self.data_types('min')])
        dtypes1 = []
        for dtype in data_types:
            stnd = self._get_standard_data_type_name(dtype)
            if stnd not in valid_dtypes:
                logger.warning(f'Invalid data type: {dtype}. Skipping.')
                continue
            dtypes1.append(stnd)

        return dtypes1

    def _translate_point_location(self, locations: PointLocation) -> dict[str, Point]:
        """Translate, as in to understand, not a spatial translation."""
        if not locations:
            return {}

        pnts = {}
        i = 0
        if isinstance(locations, Iterable) and not isinstance(locations, str):  # assumes a list of points, does not support a list of files
            if len(locations) == 2 and all(isinstance(loc, (float, int)) for loc in locations):
                pnts['pnt1'] = tuple(locations)
                return pnts

            for loc in locations:
                i += 1
                key = f'pnt{i}'
                if isinstance(locations, dict):
                    key = loc
                    loc = locations[loc]
                if isinstance(loc, str):
                    pnts[key] = self._wkt_point_to_tuple(loc)
                elif isinstance(loc, Iterable):
                    pnts[key] = tuple(loc)

            return pnts

        if isinstance(locations, str):
            try:
                pnts['pnt1'] = self._wkt_point_to_tuple(locations)
                return pnts
            except ValueError:
                pass

        return gis.point_gis_file_to_dict(locations)

    def _translate_line_string_location(self, locations: LineStringLocation) -> dict[str, LineString]:
        if not locations:
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
            elif self._list_depth(locations) == 2:  # [(0, 0), (1, 1)] - a single line-string, not a list of line-strings
                lines['line1'] = locations
                return lines
            elif isinstance(locations, dict):
                for key, loc in locations.items():
                    if isinstance(loc, str):
                        lines[key] = self._wkt_line_to_list(loc)
                    elif isinstance(loc, Iterable):
                        lines[key] = loc
                return lines
            elif self._list_depth(locations) == 3:  # list of line-strings
                for loc in locations:
                    i += 1
                    key = f'line{i}'
                    lines[key] = loc
                return lines

        return gis.line_gis_file_to_dict(locations)  # assume it is a file path

    @staticmethod
    def _wkt_point_to_tuple(point: str) -> tuple[float, ...]:
        if not re.match(r'^POINT\s*\(\s*[-+]?\d*\.?\d+\s+[-+]?\d*\.?\d+\s*\)$', point):
            raise ValueError(f'Invalid WKT point string: {point}')
        return tuple([float(x) for x in re.split(r'\s+', point.strip('\n\t )').split('(')[1], 1)])

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
