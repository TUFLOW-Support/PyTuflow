from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from ..map_output import LineString, Point

try:
    import shapely
    has_shapely = True
except ImportError:
    shapely = None
    has_shapely = False


class CellIntersect:

    def __init__(self, m: int, n: int, offsets: tuple[float, float]):
        self.m = m
        self.n = n
        self.offsets = offsets


class GridLine:

    def __init__(self, dx: float, dy: float, ox: float, oy: float, ncol: int, nrow: int):
        self.dx = dx
        self.dy = dy
        self.ox = ox
        self.oy = oy
        self.ncol = ncol
        self.nrow = nrow
        if not has_shapely:
            raise ImportError('Shapely is not installed.')

    def cells_along_line(self, line: 'LineString') -> Generator[CellIntersect, None, None]:
        offset = 0.
        for i in range(len(line) - 1):
            p0, p1 = line[i], line[i + 1]

            if not self.in_grid(p0):  # first point is outside grid
                p_intersect = self.grid_intersect_point(p0, p1, start=True)
                d1 = offset
                d2 = offset + shapely.distance(shapely.Point(p0), shapely.Point(p_intersect))
                yield CellIntersect(-1, -1, (d1, d2))

            octant = self._octant(p0, p1)
            inter = None
            for inter in self._gridline(p0, p1, octant):
                inter.offsets = (inter.offsets[0] + offset, inter.offsets[1] + offset)
                yield inter

            offset = inter.offsets[1]

            if not self.in_grid(p1):  # last point is outside grid
                p_intersect = self.grid_intersect_point(p0, p1, start=False)
                d1 = offset
                d2 = offset + shapely.distance(shapely.Point(p_intersect), shapely.Point(p1))
                offset = d2
                yield CellIntersect(-1, -1, (d1, d2))

    def _gridline(self, p0: 'Point', p1: 'Point', octant: int) -> Generator[CellIntersect, None, None]:
        p0_, p1_ = self._to_grid_coords(p0, p1) # (m, n)
        if p0_ == (-1, -1) or p1_ == (-1, -1):
            return
        if octant in [1, 4, 5, 8]:
            x0, x1, y0, y1 = p0_[0], p1_[0], p0_[1], p1_[1]
        else:  # [2, 3, 6, 7]
            x0, x1, y0, y1 = p0_[1], p1_[1], p0_[0], p1_[0]
        dx = x1 - x0
        dy = y1 - y0
        xi, yi = 1, 1
        if dx < 0:
            xi = -1
        if dy < 0:
            yi = -1
        dx, dy = abs(dx), abs(dy)
        d = 2 * dy - dx
        n = y0
        for m in range(x0, x1 + xi, xi):
            # check line intersects cell and also check cells on either side.
            if self._intersects(m, n - yi, p0, p1, octant):
                m_, n_ = self._octant_coords(m, n - yi, octant)
                offsets = self._offsets(m, n - yi, p0, p1, octant)
                yield CellIntersect(m_, n_, offsets)
            if self._intersects(m, n, p0, p1, octant):
                m_, n_ = self._octant_coords(m, n, octant)
                offsets = self._offsets(m, n, p0, p1, octant)
                yield CellIntersect(m_, n_, offsets)
            if self._intersects(m, n + yi, p0, p1, octant):
                m_, n_ = self._octant_coords(m, n + yi, octant)
                offsets = self._offsets(m, n + yi, p0, p1, octant)
                yield CellIntersect(m_, n_, offsets)

            if d > 0:
                n += yi
                d = d + (2 * (dy - dx))
            else:
                d += 2 * dy

    def to_mn(self, p: 'Point') -> tuple[int, int]:
        m = min(max(int((p[0] - self.ox) / self.dx), 0), self.ncol - 1)
        n = min(max(int((p[1] - self.oy) / self.dy), 0), self.nrow - 1)
        return m, n

    def in_grid(self, p: 'Point') -> bool:
        return self.ox <= p[0] <= self.ox + self.ncol * self.dx and self.oy <= p[1] <= self.oy + self.nrow * self.dy

    def grid_intersect_point(self, p0: 'Point', p1: 'Point', start: bool) -> 'Point':
        """start=True - return the first intersection point, start=False - return the last intersection point."""
        linestring = shapely.LineString([p0, p1])
        poly = shapely.Polygon([(self.ox, self.oy),
                                (self.ox + self.ncol * self.dx, self.oy),
                                (self.ox + self.ncol * self.dx, self.oy + self.nrow * self.dy),
                                (self.ox, self.oy + self.nrow * self.dy)])
        intersection = shapely.intersection(linestring, poly)
        if intersection.is_empty:
            return (-1, -1)
        if start:
            return intersection.coords[0]
        return intersection.coords[1]

    def _to_grid_coords(self, p0: 'Point', p1: 'Point') -> tuple['Point', 'Point']:
        if self.in_grid(p0) and self.in_grid(p1):
            return self.to_mn(p0), self.to_mn(p1)

        linestring = shapely.LineString([p0, p1])
        poly = shapely.Polygon([(self.ox, self.oy),
                                (self.ox + self.ncol * self.dx, self.oy),
                                (self.ox + self.ncol * self.dx, self.oy + self.nrow * self.dy),
                                (self.ox, self.oy + self.nrow * self.dy)])
        intersection = shapely.intersection(linestring, poly)
        if intersection.is_empty:
            return (-1, -1), (-1, -1)

        if self.in_grid(p0):
            p0_mn = self.to_mn(p0)
        else:
            p0_mn = self.to_mn(intersection.coords[0])
        if self.in_grid(p1):
            p1_mn = self.to_mn(p1)
        else:
            p1_mn = self.to_mn(intersection.coords[1])

        return p0_mn, p1_mn

    @staticmethod
    def _octant_coords(m: int, n: int, octant: int) -> tuple[int, int]:
        """Returns coordinates considering the octant - x, y could be flipped."""
        if octant in [1, 4, 5, 8]:
            return m, n
        else:  # [2, 3, 6, 7]
            return n, m

    def _intersects(self, n: int, m: int, p0: 'Point', p1: 'Point', octant: int) -> bool:
        """Check if the line intersects the cell. p0 and p1 are in grid indexes."""
        m, n = self._octant_coords(m, n, octant)
        if m < 0 or m >= self.ncol or n < 0 or n >= self.nrow:
            return False
        poly = self._nm_to_polygon(n, m)
        linestring = shapely.LineString([p0, p1])
        return shapely.intersects(poly, linestring)

    def _offsets(self, n: int, m: int, p0: 'Point', p1: 'Point', octant: int) -> tuple[float, float]:
        n, m = self._octant_coords(n, m, octant)
        poly = self._nm_to_polygon(n, m)
        linestring = shapely.LineString([p0, p1])
        intersection = shapely.intersection(poly, linestring)
        if intersection.geom_type == 'Point':
            d1 = shapely.distance(shapely.Point(p0), intersection)
            return d1, d1
        elif intersection.geom_type == 'LineString':
            d1 = shapely.distance(shapely.Point(p0), shapely.Point(intersection.coords[0]))
            d2 = d1 + intersection.length
            return d1, d2
        return -1, -1

    def _nm_to_polygon(self, n: int, m: int) -> shapely.Polygon:
        x = self.ox + n * self.dx
        y = self.oy + m * self.dy
        return shapely.Polygon([(x, y), (x + self.dx, y), (x + self.dx, y + self.dy), (x, y + self.dy)])

    @staticmethod
    def _octant(p0: 'Point', p1: 'Point') -> int:
        """Return the octant of the line segment.

       Convention:
           1 = +dx, +dy, dx larger
           2 = +dx, +dy, dy larger
           3 = -dx, +dy, dy larger
           4 = -dx, +dy, dx larger
           5 = -dx, -dy, dx larger
           6 = -dx, -dy, dy larger
           7 = +dx, -dy, dy larger
           8 = +dx, -dy, dx larger
       """
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        dx_larger = abs(dx) >= abs(dy)

        if dx > 0 and dy > 0 and dx_larger:
            return 1
        elif dx > 0 and dy > 0:
            return 2
        elif dx < 0 and dy > 0 and not dx_larger:
            return 3
        elif dx < 0 and dy > 0:
            return 4
        elif dx < 0 and dx_larger:
            return 5
        elif dx < 0:
            return 6
        elif not dx_larger:
            return 7
        else:
            return 8
