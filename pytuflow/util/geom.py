"""Geometry utilities.

This module contains light-weight geometry utilities that do not require GDAL. For more advanced geometries
(e.g. multi-part), or more advanced geometry algorithms, a more robust library should be used (e.g. Shapely, GDAL etc.).
"""

from fm_to_estry.helpers.geometry import Point, Line, Polygon, get_right_angle_line


Point.__module__ = 'pytuflow.util.geom'
Line.__module__ = 'pytuflow.util.geom'
Polygon.__module__ = 'pytuflow.util.geom'
get_right_angle_line.__module__ = 'pytuflow.util.geom'
