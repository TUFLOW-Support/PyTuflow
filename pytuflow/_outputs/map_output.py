import re
from collections.abc import Iterable

from .output import Output
from .._pytuflow_types import PathLike
from ..util._util.gis import point_gis_file_to_dict, line_gis_file_to_dict

Point = tuple[float, float] | str
LineString = list[Point] | tuple[Point]

Points = list[Point]
LineStrings = list[LineString]

PointLocation = Points | PathLike
LineStringLocation = LineStrings | PathLike


class MapOutput(Output):

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

    def _list_depth(self, lst: Iterable) -> int:
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
