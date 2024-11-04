"""Geometry utilities.

This module contains light-weight geometry utilities that do not require GDAL. For more advanced geometries
(e.g. multi-part), or more advanced geometry algorithms, a more robust library should be used (e.g. Shapely, GDAL etc.).
"""

from math import cos, sin, asin, sqrt, radians

import numpy as np
import pandas as pd
from fm_to_estry.helpers.geometry import Point, Line, Polygon, get_right_angle_line


def calc_spherical_length(points: list[tuple[float, float]]) -> float:
    """Calculate the length of a line, in metres, defined by a series of points.

    Parameters
    ----------
    points : list[float]
        List of points in the form [(long1, lat1), (long2, lat2), ...].

    Returns
    -------
    float
    """
    df = pd.DataFrame(points, columns=['long', 'lat'])

    # convert decimal degrees to radians
    df['long'], df['lat'] = df['long'].map(radians), df['lat'].map(radians)

    # haversine formula
    df['dlong'] = df['long'].diff()
    df['dlat'] = df['lat'].diff()
    df['a'] = np.sin(df['dlat'] / 2) ** 2 + np.cos(df['lat']) * np.cos(df['lat']) * np.sin(df['dlong'] / 2) ** 2
    df['c'] = 2 * np.arcsin(np.sqrt(df['a']))
    df['km'] = 6371 * df['c']
    return df['km'].sum() * 1_000


Point.__module__ = 'pytuflow.util.geom'
Line.__module__ = 'pytuflow.util.geom'
Polygon.__module__ = 'pytuflow.util.geom'
get_right_angle_line.__module__ = 'pytuflow.util.geom'
