import re
from collections.abc import Iterable

from .output import Output
from .._pytuflow_types import PathLike
from ..util._util.gis import point_gis_file_to_dict

Point = tuple[float, float] | str
LineString = list[Point]

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


    def _wkt_point_to_tuple(self, point: str) -> tuple[float, float]:
        if not re.match(r'^POINT\s*\(\s*[-+]?\d*\.?\d+\s+[-+]?\d*\.?\d+\s*\)$', point):
            raise ValueError(f'Invalid WKT point string: {point}')
        return tuple([float(x) for x in re.split(r'\s+', point.strip('\n\t )').split('(')[1], 1)])
