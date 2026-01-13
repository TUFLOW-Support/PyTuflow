import typing

import pandas as pd
import numpy as np

try:
    import shapely
except ImportError:
    shapely = None

from .transform import Transform2D


class AxisBox:

    def __init__(self):
        self.min = 9e29
        self.max = -9e29

    def __repr__(self) -> str:
        if self.valid:
            return f'({self.min}, {self.max})'
        return '( )'

    @property
    def valid(self) -> bool:
        return bool(self.min < 9e29 and self.max > -9e29)

    @property
    def size(self) -> float:
        if not self.valid:
            return 0
        return self.max - self.min

    @property
    def centroid(self) -> float:
        if not self.valid:
            return np.nan
        return self.min + self.size / 2

    def update_extents(self, values: pd.Series | np.ndarray):
        """Update axis extents with the values.

        Parameters
        ----------
        values : pd.Series | np.ndarray
            A pandas series containing the values from the given axis. E.g. the 'x' component from an array of vector3.
        """
        self.min = min(self.min, values.min())
        self.max = max(self.max, values.max())


class Bbox2D:

    def __init__(self, points: typing.Iterable[float] = None):
        if not isinstance(points, np.ndarray) and points is not None:
            points = np.array(points).reshape((-1, 2))
        self.x = AxisBox()
        self.y = AxisBox()
        if points is not None and points.size:
            self.update_extents(points)

    def __repr__(self) -> str:
        return f'<Bbox2D ({self.x.min} {self.y.min}), ({self.x.max} {self.y.max})>'

    @property
    def valid(self) -> bool:
        return self.x.valid and self.y.valid

    @property
    def centroid(self) -> tuple[float, float]:
        return self.x.centroid, self.x.centroid

    @property
    def size(self) -> tuple[float, float]:
        return self.x.size, self.y.size

    @property
    def width(self) -> float:
        return self.x.size

    @property
    def height(self) -> float:
        return self.y.size

    @property
    def bounds(self) -> tuple[float, ...]:
        return self.x.min, self.y.min, self.x.max, self.y.max

    def shapely_geom(self) -> 'Shapely.Geometry':
        if shapely is None:
            raise ImportError('Shapely is not installed.')
        return shapely.Polygon(
            (
                (self.x.min, self.y.min),
                (self.x.max, self.y.min),
                (self.x.max, self.y.max),
                (self.x.min, self.y.max)
             )
        )

    def update_extents(self, points: np.ndarray):
        """Update the bbox from the given points.

        Parameters
        ----------
        points : np.ndarray
            Numpy array containing vector 2D points. It is assumed that the first column is the 'x' vector
            component and the second column is the 'y' vector component.
        """
        self.x.update_extents(points[:,0])
        self.y.update_extents(points[:,1])

    def transform(self, transform: Transform2D) -> 'Bbox2D':
        a = np.array([
            (self.x.min, self.y.min),
            (self.x.max, self.y.min),
            (self.x.max, self.y.max),
            (self.x.min, self.y.max)
        ])
        a1 = transform.transform(a)
        bbox = Bbox2D(a1)
        return bbox
