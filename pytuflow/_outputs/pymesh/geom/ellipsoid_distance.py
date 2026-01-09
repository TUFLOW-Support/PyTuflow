import numpy as np
from pyproj import Geod

geod = Geod(ellps="WGS84")


def ellipsoid_distance(points, ref):
    """
    points: (N, 2) array of [lat, lon] in degrees
    ref:    (2,) array of [lat, lon] in degrees
    returns: (N,) distances in meters
    """
    lons1 = np.full(len(points), ref[0])
    lats1 = np.full(len(points), ref[1])

    lats2 = points[:, 1]
    lons2 = points[:, 0]

    _, _, dist = geod.inv(lons1, lats1, lons2, lats2)
    return dist
