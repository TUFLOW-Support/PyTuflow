import numpy as np
from pyproj import Geod

geod = Geod(ellps="WGS84")


def ellipsoid_distance(points, ref):
    """
    points: (N, 2) array of [lat, lon] in degrees
    ref:    (2,) array of [lat, lon] in degrees
    returns: (N,) distances in meters
    """
    lons1 = np.full(points.shape[0], ref[0,0])
    lats1 = np.full(points.shape[0], ref[0,1])

    lats2 = points[:, 1]
    lons2 = points[:, 0]

    is_point = False
    if lons1.size == 1:
        is_point = True
        lons1 = np.repeat(lons1, 2)
        lats1 = np.repeat(lats1, 2)
        lats2 = np.repeat(lats2, 2)
        lons2 = np.repeat(lons2, 2)

    _, _, dist = geod.inv(lons1, lats1, lons2, lats2)
    if is_point:
        dist = dist[:1]
    return dist
