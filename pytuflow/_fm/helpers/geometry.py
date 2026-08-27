import typing
from math import atan2, cos, sin, pi
import numpy as np
try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

# from fm_to_estry.helpers.log import Log


class Point:
    """Simple class for Point geometry.

    Attributes
    ----------
    x : float
        x coordinate
    y : float
        y coordinate
    xy : np.ndarray
        x, y coordinates as numpy array
    """

    def __init__(self, x: float, y: float):
        """
        Parameters
        ----------
        x : float
            x coordinate
        y : float
            y coordinate
        """
        #: float: x-coordinate
        self.x = x
        #: float: y-coordinate
        self.y = y
        #: np.ndarray: x, y coordinates as a numpy array
        self.xy = np.array([x, y])
        #: int: number of points
        self.np = 1
        self._pos = -1

    def __repr__(self) -> str:
        return f'Point(x={self.x}, y={self.y})'

    def __eq__(self, other):
        eq = False
        if isinstance(other, Point):
            return np.allclose(self.x, other.x) and np.allclose(self.y, other.y)

    def to_wkt(self) -> str:
        """Returns a WKT representation of the point.

        Returns
        -------
        str
            WKT representation of the point
        """

        return 'POINT ({0} {1})'.format(self.x, self.y)

    @staticmethod
    def from_wkt(wkt: str) -> 'Point':
        """Creates a Point object from a WKT representation.

        Parameters
        ----------
        wkt : str
            WKT representation of the point

        Returns
        -------
        Point
            Point object
        """
        wkt = wkt.replace('POINT (', '').replace(')', '')
        x, y = wkt.split(' ')
        return Point(float(x), float(y))


class Line:
    """Simple class for Line geometry (can be polyline).

    The :code:`__getitem__` method allows for slicing of the line into line segments. The line can also
    be iterated over, returning each line segment.

    Attributes
    ----------
    x : list[float]
        x coordinates
    y : list[float]
        y coordinates
    points : list[Point]
        list of Point objects
    np : int
        number of points
    xy : np.ndarray
        x, y coordinates as a 2D numpy array

    Examples
    --------
    >>> line = Line(x=[0, 1, 2, 3], y=[0, 1, 2, 3])
    >>> line[0]
    Line(points=[Point(x=0, y=0), Point(x=1, y=1)])
    >>> line[1:3]  # a slice will return a list of Line objects
    [Line(points=[Point(x=1, y=1), Point(x=2, y=2)]), Line(points=[Point(x=2, y=2), Point(x=3, y=3)])]
    """

    def __init__(self, x: list[float] = (), y: list[float] = (), points: list[Point] = ()):
        """Can be initialised by individual x and y lists, or by a list of Point objects. Can only
        use one of the two methods.

        Parameters
        ----------
        x : list[float], optional
            x coordinates
        y : list[float], optional
            y coordinates
        points : list[Point], optional
            list of Point objects
        """
        if x and y:
            #: list[float]: x coordinates
            self.x = x
            #: list[float]: y coordinates
            self.y = y
            #: list[Point]: list of Point objects
            self.points = [Point(x[i], y[i]) for i in range(len(x))]
        elif points:
            self.points = points
            self.x = [x.x for x in points]
            self.y = [x.y for x in points]

        #: int: number of points
        self.np = len(self.points)
        #: np.ndarray: x, y coordinates as a 2D numpy array
        self.xy = np.array([(self.x[i], self.y[i]) for i in range(self.np)])

    def __repr__(self) -> str:
        return f'Line(points={self.points})'

    def __eq__(self, other):
        eq = False
        if isinstance(other, Line):
            return self.points == other.points

    def __getitem__(self, item):
        """Returns a line segment at the requested index.

        :param item: int
        :return: Line
        """
        if isinstance(item, slice):
            i = item.start if item.start is not None else 0
            j = item.stop if item.stop is not None else self.np - 1
            k = item.step if item.step is not None else 1
            if k < 0:
                return [self[n] for n in range(j-1, i-1, k)]
            return [self[n] for n in range(i, j, k)]
        if item < 0:
            item = len(self.points) + item - 1
        return Line(points=self.points[item:item + 2])

    def __next__(self):
        self._pos += 1
        if self._pos < len(self.points) - 1:
            return self[self._pos]
        self._pos = -1
        raise StopIteration

    def __iter__(self):
        self._pos = -1
        while True:
            try:
                yield next(self)
            except StopIteration:
                break


    @staticmethod
    def from_wkt(wkt: str) -> 'Line':
        """Creates a Line object from a WKT representation of the linestring.

        Parameters
        ----------
        wkt : str
            WKT representation of the line

        Returns
        -------
        Line
            Line object
        """

        wkt = wkt.replace('LINESTRING (', '').replace(')', '').replace('"', '')
        points = [Point(float(x.strip().split(' ')[0]), float(x.strip().split(' ')[1])) for x in wkt.split(',')]
        return Line(points=points)

    def to_wkt(self) -> str:
        """Returns a WKT representation of the line.

        Returns
        -------
        str
            WKT representation of the line
        """

        return 'LINESTRING ({0})'.format(', '.join(['{0} {1}'.format(x.x, x.y) for x in self.points]))

    def mid_point(self) -> Point:
        """Returns the mid-point of the polyline (the point at the half-way point along the line).

        Returns
        -------
        Point
            Mid-point of the polyline
        """

        return self.position_along_line(self.length() / 2.)

    def length(self) -> float:
        """Returns the total length of the polyline. No complicated calculations are done to account for
        curvature of the earth.

        Returns
        -------
        float
            Total length of the polyline
        """
        return sum([np.sqrt(x[0] ** 2 + x[1] ** 2) for x in np.diff(self.xy, axis=0)])

    def length_of_segment(self, segment_index: int) -> float:
        """Returns the length of the line segment and segment_index.

        Parameters
        ----------
        segment_index : int
            index of the segment

        Returns
        -------
        float
            Length of the segment
        """
        return [np.sqrt(x[0] ** 2 + x[1] ** 2) for x in np.diff(self.xy, axis=0)][segment_index]

    def segment_index(self, distance: float) -> int:
        """Returns the segment index at a distance along the line.

        Parameters
        ----------
        distance : float
            distance along the line

        Returns
        -------
        int
            segment index
        """
        total_length = 0
        for i in range(self.np - 1):
            total_length += self.length_of_segment(i)
            if distance < total_length:
                return i

        return self.np - 2

    def angle(self, segment_index: int) -> float:
        """Returns the angle of the segment at segment index. The return is in radians from horizontal in a
        counter-clockwise direction.

        Parameters
        ----------
        segment_index : int
            index of the segment

        Returns
        -------
        float
            Angle of the segment in radians from horizontal in a counter-clockwise direction
        """
        return calculate_angle(*self.points[segment_index:segment_index + 2])

    def position_along_line(self, distance: float) -> Point:
        """Returns the x,y position along the line as a Point based on
        the distance from the start of the line.

        If distance is greater than the total length of the line, the distance
        is extrapolated based on the angle of the last segment.

        Parameters
        ----------
        distance : float
            distance along the line

        Returns
        -------
        Point
            Point at the distance along the line
        """

        total_length = 0
        for i in range(self.np-1):
            total_length += self.length_of_segment(i)
            if distance <= total_length:
                along_segment = self.length_of_segment(i) - total_length + distance
                angle = self.angle(i)
                return Point(get_x(self.x[i], angle, along_segment), get_y(self.y[i], angle, along_segment))

        additional_distance = distance - self.length()
        angle = self.angle(self.np - 1)
        return Point(get_x(self.x[self.np - 1], angle, additional_distance),
                     get_y(self.y[self.np - 1], angle, additional_distance))

    def segment_from_point(self, point: Point, atol=0.01) -> int:
        """Returns the closest line segment index to a given point (within a tolerance).

        Parameters
        ----------
        point : Point
            point to find the closest segment to
        atol : float, optional
            absolute tolerance for the distance between the point and the line segment

        Returns
        -------
        int
            index of the closest line segment
        """
        for i, seg in enumerate(self):
            buffer = seg.buffer(atol)
            if buffer.contains(point):
                return i

    def buffer(self, distance: float) -> 'Polygon':
        """Create a buffer around the line at a given buffer width.

        Parameters
        ----------
        distance : float
            buffer width

        Returns
        -------
        Polygon
            buffer around the line
        """
        points = []
        for seg in self:
            line1 = get_right_angle_line(seg, seg.points[0], distance, False)
            line2 = get_right_angle_line(seg, seg.points[1], distance, False)
            points.append(line1.points[0])
            points.append(line2.points[0])
        for seg in self[::-1]:
            line1 = get_right_angle_line(seg, seg.points[1], distance, False)
            line2 = get_right_angle_line(seg, seg.points[0], distance, False)
            points.append(line1.points[1])
            points.append(line2.points[1])
        return Polygon(points=points)

    def intersect(self, line: 'Line') -> bool:
        """Returns whether the line intersects with another line.

        Parameters
        ----------
        line : Line
            line to check for intersection

        Returns
        -------
        bool
            True if the line intersects with the other line, False otherwise
        """
        o1 = self._orientation(self.points[0], self.points[1], line.points[0])
        o2 = self._orientation(self.points[0], self.points[1], line.points[1])
        o3 = self._orientation(line.points[0], line.points[1], self.points[0])
        o4 = self._orientation(line.points[0], line.points[1], self.points[1])

        if o1 != o2 and o3 != o4:
            return True

        if o1 == 0 and self._on_segment(self.points[0], line.points[0], self.points[1]):
            return True
        if o2 == 0 and self._on_segment(self.points[0], line.points[1], self.points[1]):
            return True
        if o3 == 0 and self._on_segment(line.points[0], self.points[0], line.points[1]):
            return True
        if o4 == 0 and self._on_segment(line.points[0], self.points[1], line.points[1]):
            return True

        return False

    def _on_segment(self, p: Point, q: Point, r: Point) -> bool:
        return q.x <= max(p.x, r.x) and q.x >= min(p.x, r.x) and q.y <= max(p.y, r.y) and q.y >= min(p.y, r.y)

    def _orientation(self, p: Point, q: Point, r: Point) -> int:
        val = (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y)
        if val == 0:
            return 0  # collinear
        return 1 if val > 0 else 2


class Polygon:
    """Simple class for Polygon geometry.

    Attributes
    ----------
    x : list[float]
        x coordinates
    y : list[float]
        y coordinates
    points : list[Point]
        list of Point objects
    np : int
        number of points
    xy : np.ndarray
        x, y coordinates as a 2D numpy array
    """

    def __init__(self, x: list[float] = (), y: list[float] = (), points: list[Point] = ()):
        """Can be initialised by individual x and y lists, or by a list of Point objects. Can only
        use one of the two methods.

        Parameters
        ----------
        x : list[float], optional
            x coordinates
        y : list[float], optional
            y coordinates
        points : list[Point], optional
            list of Point objects
        """
        if x and y:
            #: list[float]: x coordinates
            self.x = x
            #: list[float]: y coordinates
            self.y = y
            #: list[Point]: list of Point objects
            self.points = [Point(x[i], y[i]) for i in range(len(x))]
        elif points:
            self.points = points
            self.x = [x.x for x in points]
            self.y = [x.y for x in points]

        #: int: number of points
        self.np = len(self.points)
        #: np.ndarray: x, y coordinates as a 2D numpy array
        self.xy = np.array([(self.x[i], self.y[i]) for i in range(self.np)])

    def to_wkt(self) -> str:
        """Returns a WKT representation of the polygon.

        Returns
        -------
        str
            WKT representation of the polygon
        """
        return 'POLYGON (({0}))'.format(', '.join(['{0} {1}'.format(x.x, x.y) for x in self.points]))

    def contains(self, p: Point) -> bool:
        """Returns whether a point is contained within the polygon.

        Parameters
        ----------
        p : Point
            point to check for containment

        Returns
        -------
        bool
            True if the point is contained within the polygon, False otherwise
        """
        if self.np < 3:
            return False
        line = Line(points=[p, Point(1e6, p.y)])
        count = 0
        for i in range(self.np):
            if line.intersect(Line(points=[self.points[i], self.points[(i + 1) % self.np]])):
                count += 1
        return count % 2 == 1


def calculate_angle(p1: Point, p2: Point) -> float:
    """
    Calculates angle in radians of line.

    :param p1: Point
    :param p2: Point
    :return: float
    """

    return atan2((p2.y - p1.y), (p2.x - p1.x))


def get_x(origin: float, angle: float, dist: float) -> float:
    """
    Calculates x coordinate location given an origin, angle, and distance (vector product magniture).

    :param origin: float
    :param angle: float
    :param dist: float
    :return: float
    """

    cosang = cos(angle)
    dx = dist * cosang

    return origin + dx


def get_y(origin: float, angle: float, dist: float) -> float:
    """
    Calculates y coordinate location given an origin, angle, and distance (vector product magniture).

    :param origin: float
    :param angle: float
    :param dist: float
    :return: float
    """

    sinang = sin(angle)
    dy = dist * sinang

    return origin + dy


def get_right_angle_line(line: Line, centroid: Point, length: float, include_mid_point: bool, atol=1e-5,
                         snapping: str = 'all') -> Line:
    """Creates a line perpendicular to a given input line. The input line is only used to define
    the new line's angle. The centroid is used to define the new line's location. The new line will contain
    three points - start, end, centroid.

    Parameters
    ----------
    line : Line
        Used to define the angle of the new line. If :code:`snapping` is either :code:`all`, :code:`end_only`,
        or :code:`mid_only`, then the centroid point can be overriden by the snapping setting.
    centroid : Point
        The point at which the new line will be centred. Can be moved if snapping is enabled.
    length : float
        Length of the new line.
    include_mid_point : bool
        If True, the centroid point will be included in the new line, otherwise just the end points will be included.
    atol : float, optional
        snapping tolerance if snapping is enabled. Default is 1e-5.
    snapping : str, optional
        If :code:`all`, the centroid can snap to the nearest vertex on the line. If :code:`mid_only`, the centroid can
        snap to the nearest internal vertices of the line. If :code:`end_only`, the centroid can snap to the
        nearest end-point.

    Returns
    -------
    Line
        New line perpendicular to the input line.
    """
    if not snapping or snapping.lower() in ['none', 'off']:
        close_points = np.array([])
    else:
        if snapping.lower() == 'all':
            a = line.xy
        elif snapping.lower() in ['mid_only'] and len(line.points) > 2:
            a = line.xy[1:-1]
        elif snapping.lower() in ['end_only']:
            a = np.append(line.xy[0:1], line.xy[-1:], axis=0)
        else:
            a = np.array([])
        if a.size:
            close_points = np.isclose(centroid.xy, a, atol=atol)
            close_points = (close_points[:] == [True, True]).all(1)
        else:
            close_points = np.array([False])
    if close_points.any():  # if centroid is close to any vertex along the line, adopt that vertex - looks nicer in GIS
        if close_points.sum() > 1:  # more than one, use the closest
            dists = np.linalg.norm(a - centroid.xy, axis=1)
            i = int(np.argmin(dists))
            close_points[:] = False
            close_points[i] = True
        else:
            i = np.where(close_points)[0][0]
        if snapping.lower() == 'mid_only':
            i += 1
        elif snapping.lower() == 'end_only' and i == 1:
            i = line.xy.shape[0] - 1
        centroid = Point(*a[close_points][0])
        if i == 0:  # first vertex
            ang = calculate_angle(line.points[0], line.points[1])
        elif i + 1 == len(line.points):  # last vertex
            ang = calculate_angle(line.points[-2], line.points[-1])
        else:  # internal vertex - take average angle of incoming and outgoing lines
            ang = (
                    calculate_angle(line.points[i - 1], line.points[i]) +
                    calculate_angle(line.points[i], line.points[i + 1])
                  ) / 2.
    else:
        if len(line.points) == 2:
            iseg = 0
        else:
            iseg = line.segment_from_point(centroid, 0.1)  # find segment closest to centroid
            if iseg is None:
                iseg = 0
        line_ = line[iseg]
        ang = calculate_angle(line_.points[0], line_.points[1])

    p1 = Point(get_x(centroid.x, ang + pi / 2., length / 2.), get_y(centroid.y, ang + pi / 2., length / 2.))
    p3 = Point(get_x(centroid.x, ang - pi / 2., length / 2.), get_y(centroid.y, ang - pi / 2., length / 2.))

    if include_mid_point:
        p2 = Point(centroid.x, centroid.y)
        return Line(points=[p1, p2, p3])

    return Line(points=[p1, p3])


def get_line_centroid(line: Line) -> Point:
    """
    Returns the centroid of a line that only contains 2 points.

    :param line: Line
    :return: Point
    """

    return Point((line.x[1] + line.x[0]) / 2., (line.y[1] + line.y[0]) / 2.)


def interpolate(a1: float, a2: float, a3: float, b1: float, b2: float) -> float:
    """
    Linear interpolation.

    a series represents where all (3) values are known.
    b series represents upper and lower known values and a mid unknown value

    :param a1: float - first bound of a
    :param a2: float - second bound of a
    :param a3: float - mid point of a
    :param b1: float - first bound of b
    :param b2: float - second bound of b
    :return: float - interpolated mid point of b
    """

    return (b2 - b1) / (a2 - a1) * (a3 - a1) + b1


def interpolate_hw_tables(hw1: typing.Union[pd.DataFrame, np.ndarray],
                          hw2: typing.Union[pd.DataFrame, np.ndarray],
                          weighting: list[float],
                          interp_levels: bool = False,
                          as_df: bool = False) -> typing.Union[pd.DataFrame, np.ndarray]:
    """
    Interpolate an HW table from an upstream and downstream HW table.

    The process is as follows:
        1. converts levels in the HW tables to depth
        2. combines the depth values from the two HW table into a single array of unique depths
        3. interpolates width / manning's values for the new depths for each array so they are like for like
        4. interpolates width and manning's values into a single array using weightings
        5. turns depths into levels using the weighted average of the upstream and downstream invert
            - if interp_levels=True then levels will also be interpolated using weightings, otherwise new depths
              will be added to the min of hw1 level - this is desirable in most cases as the inverts are
              determined from the 1d_nwk attributes.
        6. finally returns new HW table by combining new levels and interpolated width and manning's values

    :param hw1: np.ndarray - upstream HW table
    :param hw2: np.ndarray - downstream HW table
    :param weighting: list[float] - should sum to 1.0 e.g. [0.5, 0.5], order = [upstream, downstream]
    :return: np.ndarray
    """
    COLUMNS = ('h', 'w', 'n')
    if isinstance(hw1, pd.DataFrame):
        hw1 = hw1.to_numpy()
    if isinstance(hw2, pd.DataFrame):
        hw2 = hw2.to_numpy()

    has_n = hw1.shape[1] == 3 and hw2.shape[1] == 3

    # add depths to arrays
    hw1_dep = np.append(hw1, np.reshape(hw1[:,0] - np.amin(hw1[:, 0]), (hw1.shape[0], 1)), axis=1)
    hw2_dep = np.append(hw2, np.reshape(hw2[:,0] - np.amin(hw2[:, 0]), (hw2.shape[0], 1)), axis=1)

    # work out depths and levels for new hw table
    deps = np.sort(np.unique(np.round(np.concatenate((hw1_dep[:,-1], hw2_dep[:,-1]), 0), 4)))
    nval = deps.shape[0]
    if interp_levels:
        levels = np.reshape((deps + (np.amin(hw1[:, 0]) * weighting[0] + np.amin(hw2[:, 0]) * weighting[1])), (nval, 1))
    else:
        levels = np.reshape(deps + np.amin(hw1[:,0]), (nval, 1))

    # interpolate width and mannings based on new depths
    w1_interp = np.interp(deps, hw1_dep[:,-1], hw1_dep[:,1])
    w2_interp = np.interp(deps, hw2_dep[:,-1], hw2_dep[:,1])
    w_comb = np.reshape((w1_interp * weighting[0] + w2_interp * weighting[1]), (nval, 1))
    a = np.append(levels, w_comb, axis=1)
    if has_n:
        n1_interp = np.interp(deps, hw1_dep[:,-1], hw1_dep[:,2])
        n2_interp = np.interp(deps, hw2_dep[:,-1], hw2_dep[:,2])
        n_comb = np.reshape((n1_interp * weighting[0] + n2_interp * weighting[1]), (nval, 1))
        a = np.append(a, n_comb, axis=1)

    if as_df:
        return pd.DataFrame(a, columns=COLUMNS[:a.shape[1]])
    return a


def clean_hw_table(section: np.ndarray, col_order: list[str]) -> np.ndarray:
    """
    RE-organises input array based on the col_order

    e.g.
    col_order = ['w', 'h', 'n']
    array will be reshuffled so the columns are correctly in the order 'h', 'w', 'n'

    Routine will also try and clean up the input arrays to make the final HW array TUFLOW
    compatible.
    It will:
        - remove any 0 width at the start of the array
        - remove duplicate elevations by adding 0.001 to the next elevation value
        - ensure elevation values always increase

    :param hw: np.ndarray
    :param col_order: list[str] - order of the 'h' 'w' 'n' columns in the input array e.g. ['w', 'h', 'n']
    :return: np.ndarray
    """

    col_order = [x.lower() for x in col_order]
    i = col_order.index('h')

    # order array from lowest elevation to highest
    section = section[section[:, i].argsort()]
    # remove duplicates
    section = np.append(
        np.array([x for i, x in enumerate(section[:-1]) if not np.allclose(x[:2], section[i + 1, :2])]),
        section[-1:, :], axis=0)
    diff = np.diff(section, axis=0)
    if np.any(diff[:, i] == 0.):
        for index in reversed(np.where(diff[:, i] == 0.)[0]):
            j = index + 1
            if j == 1:
                section = np.delete(section, 0, axis=0)
            else:
                inc = 0.001
                if section.shape[0] < j + 1:
                    while diff[j,i] < inc:
                        inc *= 0.5
                section[j,i] = section[j,i] + inc
    return_order = [col_order.index(x) for x in ['h', 'w', 'n'] if x in col_order]

    return section[:,return_order]


def create_hw_table(section: typing.Union[pd.DataFrame, np.ndarray],
                    as_df: bool = False) -> typing.Union[pd.DataFrame, np.ndarray]:
    """
    Creates an HW table from an array of coordinates (x, y, n) for a closed conduit.

    Assumes that coordinates are in order and it shouldn't matter what direction (clockwise, anticlockwise)
    since the tool just computes flow width. If down the track area is required, then a convention may be required.

    The output HW table will use the elevation values of the section and generally won't create new values
    except maybe at the end to close off the conduit.

    Mannings values for each elevation will be calculated as a weighted average based on the wetted perimeter.

    :param section: np.ndarray
    :return: np.ndarray
    """
    COLUMNS = ('h', 'w', 'n')
    if isinstance(section, pd.DataFrame):
        section = section.to_numpy()

    has_n = section.shape[1] == 3

    # get list of elevations for HW table
    elevations = np.unique(np.round(np.sort(section[:,1]), 4))

    # remove duplicate points
    if np.allclose(section[0,:2], section[-1,:2]):
        section_reordered = np.array([x for i, x in enumerate(section[:-1]) if not np.allclose(x[:2], section[i+1,:2])])
    else:
        section_reordered = np.array([x for i, x in enumerate(section) if i + 1 == section.shape[0] or not np.allclose(x[:2], section[i + 1, :2])])
    if not np.allclose(section[-1,:-1], section[0,:-1]):
        section_reordered = np.append(section_reordered, section[-1:,:], axis=0)
    section_reordered = np.round(section_reordered, 4)

    # reorder section data to go from max elevation to min elevation
    # (re-add duplicate point at end which will be the maximum elevation location)
    max_h = elevations[-1]
    imax = np.where(section_reordered[:,1] == max_h)[0][0]
    section_reordered = np.append(np.append(section_reordered[imax:, :], section_reordered[:imax, :], axis=0),
                                  section_reordered[imax:imax + 1, :], axis=0)
    imin = np.where(section_reordered[:, 1] == elevations[0])[0][0]

    # work out widths and weighted averaged manning values at elevation points
    if has_n:
        hw = [(elevations[0], 0, section_reordered[imin,2])]
    else:
        hw = [(elevations[0], 0)]
    for h in elevations:
        # work out indexes where elevation intersects section
        if h == max_h:
            intersects_i = np.where(np.diff(np.ma.masked_greater_equal(section_reordered, h).mask[:, 1]) == True)[0]
        else:
            intersects_i = np.where(np.diff(np.ma.masked_greater(section_reordered, h).mask[:, 1]) == True)[0]
        if len(intersects_i) % 2 != 0:
            Log.log('Should not be here [create_hw_table] length of intersect locations is an odd number')
            continue

        # interpolate x value of intersections
        intersects = [np.interp(h, section_reordered[i:i + 2, 1][np.argsort(section_reordered[i:i + 2, 1])],
                                section_reordered[i:i + 2, 0][np.argsort(section_reordered[i:i + 2, 1])]) for i in
                      intersects_i]

        # calculate width
        width = sum(intersects[i+1] - intersects[i] for i in range(0, len(intersects), 2))
        if width < 0:  # i think this can happen if order is clockwise direction
            width = abs(width)

        # calculate weighted average mannings values
        if has_n:
            lengths, mannings = [], []
            for i in range(0, len(intersects_i), 2):
                intst_1 = intersects_i[i]
                intst_2 = intersects_i[i+1] + 2
                diff = np.array(section_reordered[intst_1:intst_2,:-1])
                diff[0,0] = intersects[i]
                diff[0,1] = h
                diff[-1,0] = intersects[i+1]
                diff[-1,1] = h
                diff = np.diff(diff, axis=0)
                lengths.extend([np.sqrt(x[0] ** 2 + x[1] ** 2) for x in diff])
                mannings.extend(section_reordered[intst_1+1:intst_2,2].tolist())
            if sum(lengths) > 0:
                avg_mannings = sum([lengths[i] * mannings[i] for i in range(len(lengths))]) / sum(lengths)
            else:
                avg_mannings = section_reordered[imin,2]

        if has_n:
            hw.append((h, width, avg_mannings))
        else:
            hw.append((h, width))

    if has_n:
        hw.append((h, 0, hw[-1][-1]))
    else:
        hw.append((h, 0))

    a = clean_hw_table(np.array(hw), COLUMNS[:section.shape[1]])

    if as_df:
        return pd.DataFrame(a, columns=COLUMNS[:section.shape[1]])
    return a


def parabolic_arch_conduit(width: float, crown_height: float, springing_height: float,
                           as_df: bool = False) -> typing.Union[pd.DataFrame, np.ndarray]:
    """
    Create parabolic arch.

    Assumes that springing height is the same at both ends

    :param width: float
    :param crown_height: float
    :param springing_height: float
    :return: np.ndarray
    """

    den = (width / 2.) ** 2 * -width
    a = (width * (crown_height - springing_height)) / den
    b = (width ** 2 * (springing_height - crown_height)) / den
    c = ((width / 2.) ** 2 * (width * springing_height) + (width / 2.) * (-width ** 2 * springing_height)) / den
    y = lambda x: a * x ** 2 + b * x + c

    ninc = 21
    inc = width / ninc

    a = np.array([(inc * i, y(inc * i)) for i in range(ninc+1)])
    if as_df:
        return pd.DataFrame(a, columns=['x', 'z'])
    return a


def generate_bridge_section(input_section: typing.Union[pd.DataFrame, np.ndarray],
                            left_index: int, right_index: int,
                            piers: typing.Union[pd.DataFrame, np.ndarray],
                            include_mannings: bool = False, as_df: bool = False
                            ) -> typing.Union[pd.DataFrame, np.ndarray]:
    """

    :param input_section:
    :return:
    """
    if isinstance(input_section, pd.DataFrame):
        input_section = input_section.to_numpy()
    if isinstance(piers, pd.DataFrame):
        piers = piers.to_numpy()

    if piers.any():
        h_obvert = np.nanmax((np.nanmax(piers[:,1]), np.nanmax(piers[:,3])))
    else:
        if input_section.shape[1] == 3:
            h_obvert = np.nanmean(input_section[:,2])
            include_mannings = False
        else:
            h_obvert = np.nanmean(input_section[:,3])

    if include_mannings:
        # section = input_section[left_index:right_index + 1, :3] - (input_section[left_index, 0], 0, 0)
        section = input_section[left_index:right_index + 1, :3]
    else:
        # section = input_section[left_index:right_index+1,:2] - (input_section[left_index,0], 0)
        section = input_section[left_index:right_index+1,:2]

    if not section[section[:, 1] >= h_obvert].any():  # make sure cross section reaches obvert
        if include_mannings:
            section = np.insert(section, 0, [[section[0, 0], h_obvert, section[0, 2]]], axis=0)
        else:
            section = np.insert(section, 0, [[section[0,0], h_obvert]], axis=0)
    else:
        section = section[section[:,1] <= h_obvert]

    if as_df:
        columns = ['x', 'y']
        if include_mannings:
            columns.append('n')
        return pd.DataFrame(section, columns=columns)
    return section


def calculate_bridge_flow_areas(input_section: np.ndarray, deck_level: np.ndarray, piers: np.ndarray,
                                skew: float, pier_alignment: str) -> np.ndarray:
    """

    :param input_section:
    :param piers:
    :return:
    """

    # bridge obvert
    if piers.any():
        h_obvert = np.nanmean((np.nanmean(deck_level), np.nanmean(piers[:, 1]), np.nanmean(piers[:, 3])))
    else:
        h_obvert = np.nanmean(deck_level)

    # pier elevations - interpolate pier elevations using x values
    if piers.any():
        pier_table = np.append(
            np.reshape(np.interp(piers[:, 0], input_section[:, 0], input_section[:, 1]), (piers.shape[0], 1)),
            np.reshape(np.interp(piers[:, 2], input_section[:, 0], input_section[:, 1]), (piers.shape[0], 1)), axis=1)

        # bridge pier thickness
        pier_table = np.append(pier_table, np.reshape(piers[:,2] - piers[:,0], (piers.shape[0], 1)), axis=1)

    # elevations for bridge loss table - all unique elevations from cross section and piers
    if piers.any():
        levels = np.unique(np.round(np.sort(
            np.append(np.append(input_section[:, 1], np.minimum(pier_table[:, 0], pier_table[:, 1])),
                      np.maximum(pier_table[:, 0], pier_table[:, 1]))), 3))
    else:
        levels = np.unique(np.round(np.sort(input_section[:, 1]), 3))
    levels = levels[levels <= h_obvert]

    # areas
    flow_area = []
    pier_area = []
    pier_adj = 1.
    qa_adj = 1.
    if skew > 0:
        qa_adj = np.cos(np.deg2rad(skew))
    if skew > 0 and pier_alignment == 'SKEW':
        pier_adj = max(1, 2 - qa_adj)
    for i, h in enumerate(levels):
        # if there is a pier at the invert of the cross section then need to consider this as blocked for losses
        if piers.any() and i == 0 and [x for x in pier_table if h >= x[0] and h >= x[1]]:
            h += 0.01

        # flow area - mirror along x-axis and convert level to depth so can use trapezoid rule function in numpy
        # https://en.wikipedia.org/wiki/File:Composite_trapezoidal_rule_illustration.png
        transformed_section = input_section * (1, -1) + (0, h)
        transformed_section = np.append(transformed_section[:,0:1], np.where(transformed_section[:,1:] < 0, 0., transformed_section[:,1:]), axis=1)
        
        if np.__version__ >= '2.0.0':
            qa = np.trapezoid(transformed_section[:,1], transformed_section[:,0])
        else:
            qa = np.trapz(transformed_section[:,1], transformed_section[:,0])
        qa *= qa_adj
        
        flow_area.append(qa)

        # pier area - assumes ground is a straight line between start and finish of pier
        if piers.any():
            pier_area.append(sum((max(h - x[0], 0.) + max(h - x[1], 0.)) * x[2] / 2. * pier_adj for x in pier_table))
        else:
            pier_area.append(0)

    return np.array([(levels[i], flow_area[i], pier_area[i]) for i in range(len(levels))])


def pier_loss(pier_configuration: int, blockage: float) -> float:
    """

    :param pier_configuration:
    :param blockage:
    :return:
    """

    j = [0, 0.01, 0.02, 0.04, 0.06, 0.08, 0.1, 0.12, 0.14, 0.16, 0.18]

    # delta K values for pier configurations
    k = np.array(
        [
            [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0.00879, 0.0192, 0.0418, 0.0714, 0.104, 0.139, 0.173, 0.208, 0.243, 0.278],
            [0, 0.0121, 0.028, 0.0651, 0.107, 0.153, 0.199, 0.245, 0.293, 0.341, 0.387],
            [0, 0.0148, 0.0335, 0.0769, 0.126, 0.177, 0.229, 0.279, 0.33, 0.385, 0.44],
            [0, 0.0173, 0.0409, 0.0951, 0.155, 0.218, 0.281, 0.343, 0.405, 0.467, 0.529],
            [0, 0.0201, 0.0481, 0.114, 0.187, 0.264, 0.341, 0.418, 0.495, 0.572, 0.649],
            [0, 0.0261, 0.0582, 0.136, 0.227, 0.32, 0.413, 0.506, 0.599, 0.692, 0.785],
            [0, 0.036, 0.0852, 0.207, 0.339, 0.471, 0.603, 0.735, 0.867, 0.99, 1.0],
            [0, 0.0467, 0.109, 0.26, 0.411, 0.562, 0.713, 0.864, 1., 1., 1.]
        ]
    )

    if blockage <= j[-1]:
        return np.interp(blockage, j, k[pier_configuration,:])
    elif blockage > j[-1]:  # extrapolate
        return min(1, interpolate(j[-2], j[-1], blockage, k[pier_configuration,-2], k[pier_configuration,-1]))
    else:
        return 0


def generate_bridge_losses(input_section: typing.Union[pd.DataFrame, np.ndarray],
                           deck_level: typing.Union[pd.DataFrame, np.ndarray, float],
                           piers: typing.Union[pd.DataFrame, np.ndarray],
                           pier_coeff: float, skew: float, shape: str, shape_2: str, pier_config: float,
                           pier_alignment: str, npiers_qdir: int, as_df: bool = False
                           ) -> typing.Union[pd.DataFrame, np.ndarray]:
    """

    :param input_section:
    :param deck_level:
    :param piers:
    :param pier_coeff:
    :return:
    """

    # estimate of pier coeff to pier configuration
    pier_coeff_to_config = {
        0: 0,
        0.7: 1,
        0.9: 2,
        0.95: 3,
        1.05: 4,
        1.25: 5,
        1.75: 6,
        2.2: 7,
        2.5: 8
    }

    if isinstance(input_section, pd.DataFrame):
        input_section = input_section.to_numpy()
    if isinstance(deck_level, pd.DataFrame):
        deck_level = deck_level.to_numpy()
    if isinstance(deck_level, float):
        deck_level = np.full((input_section.shape[0], 1), deck_level)
    if isinstance(piers, pd.DataFrame):
        piers = piers.to_numpy()

    # elevation vs area table
    ha = calculate_bridge_flow_areas(input_section, deck_level, piers, skew, pier_alignment)
    if not ha.size:
        raise ValueError('Failed to calculate elevation vs flow area table')
    blockages = np.fromiter((y / x if x != 0 else 0 for x, y in ha[:,1:]), float)

    if pier_coeff and npiers_qdir == 0:
        pier_coeff = 0
    elif pier_coeff is None:
        if shape == 'COEF':
            if pier_config is not None:
                df = pd.DataFrame([[v, k] for k, v in pier_coeff_to_config.items()], columns=['config', 'coeff'])
                df.set_index('config', inplace=True)
                if pier_config not in df.index:
                    df.loc[pier_config] = np.nan
                    df.sort_index(inplace=True)
                    df.interpolate(method='index', inplace=True, limit_direction='both')
                pier_coeff = df.loc[pier_config, 'coeff']
            else:
                pier_coeff = 0
        elif npiers_qdir == 0 and not piers.any():
            pier_coeff = 0
        elif shape == 'SQUARE' and npiers_qdir < 3 and shape_2 == 'DIAPHRAM':
            pier_coeff = 1.05
        elif shape == 'SQUARE' and npiers_qdir < 3:
            pier_coeff = 1.25
        elif shape == 'SQUARE':
            pier_coeff = 2.2
        elif shape == 'CYLINDER' and npiers_qdir < 3 and shape_2 == 'DIAPHRAM':
            pier_coeff = 0.95
        elif shape == 'CYLINDER' and 1 < npiers_qdir < 3:
            pier_coeff = 1.05
        elif shape == 'CYLINDER' and npiers_qdir == 1:
            pier_coeff = 0.7
        elif shape == 'CYLINDER':
            pier_coeff = 1.75
        elif shape == 'RECTANGLE' and shape_2 in ['STRMLINE', 'SEMICIRCLE', 'TRAINGLE']:
            pier_coeff = 0.9
        elif shape == 'RECTANGLE':
            pier_coeff = 1.05
        elif shape == 'I':
            pier_coeff = 2.5
        else:
            pier_coeff = 0

    if pier_coeff in pier_coeff_to_config:
        f = lambda x: pier_loss(pier_coeff_to_config[pier_coeff], x)
    else:
        x1, y1 = [(x, y) for x, y in sorted(pier_coeff_to_config.items()) if x < pier_coeff][-1]
        x2, y2 = [(x, y) for x, y in sorted(pier_coeff_to_config.items()) if x > pier_coeff][0]
        f = lambda x: interpolate(x1, x2, pier_coeff, pier_loss(y1, x), pier_loss(y2, x))
    losses = np.fromiter((f(x) for x in blockages), float)

    a = np.insert(np.reshape(losses, (losses.shape[0], 1)), 0, ha[:,0], axis=1)
    if as_df:
        return pd.DataFrame(a, columns=['z', 'lc'])
    return a


if __name__ == '__main__':
    print('This file is not the entry point. Use fm_to_estry.py')
