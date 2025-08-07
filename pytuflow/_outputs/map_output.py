import re
from collections.abc import Iterable
from typing import Union

import numpy as np
import pandas as pd

from .output import Output
from .._pytuflow_types import PathLike
from ..util._util.gis import point_gis_file_to_dict, line_gis_file_to_dict
from ..util._util.logging import get_logger


logger = get_logger()

Point = tuple[float, float] | str
LineString = list[Point] | tuple[Point]

Points = list[Point]
LineStrings = list[LineString]

PointLocation = Point | Points | PathLike
LineStringLocation = LineStrings | PathLike


class MapOutput(Output):

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

    def _filter(self, filter_by: str) -> pd.DataFrame:
        filter_by = [x.strip().lower() for x in filter_by.split('/')] if filter_by else []

        while 'section' in filter_by:  # section is everything
            filter_by.remove('section')

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
        if 'temporal' in filter_by or 'timeseries' in filter_by:
            ctx.append('temporal')
            df_ = df[~df['static']]
            df3 = pd.concat([df3, df_]) if not df3.empty else df_
            while 'temporal' in filter_by:
                filter_by.remove('temporal')
            while 'timeseries' in filter_by:
                filter_by.remove('timeseries')
        if ctx:
            df = df3

        # 2d/3d datasets
        ctx = []
        df4 = pd.DataFrame()
        if '2d' in filter_by:
            ctx.append('2d')
            df4 = df[~df['3d']]
            while '2d' in filter_by:
                filter_by.remove('2d')
        if '3d' in filter_by:
            ctx.append('3d')
            df_ = df[df['3d']]
            df4 = pd.concat([df4, df_]) if not df4.empty else df_
            while '3d' in filter_by:
                filter_by.remove('3d')
        if ctx:
            df = df4

        # data type
        if filter_by:
            ctx = [self._get_standard_data_type_name(x) for x in filter_by]
            df = df[df['data_type'].isin(ctx)] if ctx else pd.DataFrame()

        return df

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

        return point_gis_file_to_dict(locations)

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

        return line_gis_file_to_dict(locations)  # assume it is a file path

    def _wkt_point_to_tuple(self, point: str) -> tuple[float, float]:
        if not re.match(r'^POINT\s*\(\s*[-+]?\d*\.?\d+\s+[-+]?\d*\.?\d+\s*\)$', point):
            raise ValueError(f'Invalid WKT point string: {point}')
        return tuple([float(x) for x in re.split(r'\s+', point.strip('\n\t )').split('(')[1], 1)])

    def _wkt_line_to_list(self, line: str) -> list[tuple[float, float]]:
        if not re.match(r'^LINESTRING\s*\(\s*[-+]?\d*\.?\d+\s+[-+]?\d*\.?\d+\s*(,\s*[-+]?\d*\.?\d+\s+[-+]?\d*\.?\d+\s*)*\)$', line):
            raise ValueError(f'Invalid WKT line-string string: {line}')
        return [tuple([float(x) for x in p.split()]) for p in re.split(r'\s*,\s*', line.strip('\n\t )').split('(')[1])]

    @staticmethod
    def _list_depth(lst: Iterable) -> int:
        def is_bottom(lst: Iterable) -> bool:
            return all(isinstance(x, (float, int, str)) for x in lst)

        dep = 1
        lst_ = lst
        while not is_bottom(lst_):
            dep += 1
            try:
                lst_ = lst_[0]
            except (TypeError, IndexError):
                break

        return dep
