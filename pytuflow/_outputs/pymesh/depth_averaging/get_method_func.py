import typing

import numpy as np

from .depth_averaging import single_level, multi_level, depth, elevation, sigma


def get_method_func(uri: str) -> typing.Callable:
    if uri is None:
        uri = 'sigma&0.0&1.0'
    if '?' in uri:
        method, uri = uri.split('?')
        dir_, uri = uri.split('&', 1)
        dir_ = dir_.split('=')[1]
    else:
        method, uri = uri.split('&', 1)
        dir_ = 'top'
    from_top = dir_.lower() == 'top'
    vals = uri.split('&')
    if method.lower() == 'singlelevel':
        val = int(vals[0])
        return lambda zlevels, values: single_level(val, zlevels, values, from_top)
    elif method.lower() == 'multilevel':
        levels = [int(v) for v in vals][:2]
        return lambda zlevels, values: multi_level(levels, zlevels, values, from_top)
    elif method.lower() == 'depth':
        depth_value = [float(x) for x in vals][:2]
        return lambda zlevels, values: depth(depth_value, zlevels, values, True)
    elif method.lower() == 'height':
        height_value = [float(x) for x in vals][:2]
        return lambda zlevels, values: depth(height_value, zlevels, values, False)
    elif method.lower() == 'elevation':
        elevation_value = [float(x) for x in vals][:2]
        return lambda zlevels, values: elevation(elevation_value, zlevels, values)
    elif method.lower() == 'sigma':
        fracs = [float(x) for x in vals][:2]
        return lambda zlevels, values: sigma(fracs, zlevels, values)
    return lambda a, b: np.nan
