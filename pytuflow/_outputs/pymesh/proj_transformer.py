import typing

from pyproj import CRS, Transformer
import numpy as np


def proj_transformer(points: np.ndarray) -> tuple[typing.Callable, typing.Callable]:
    """Returns a proj transformer that will convert spherical to a local cartesian projection.

    Parameters
    ----------
    points : np.ndarray
        Array of 2D vectors in lon/lat.

    Returns
    -------
    typing.Callable, typing.Callable
        callable transformer function that converts lon/lat to local cartesian in meters, and it's inverse callable.
    """
    lon0 = np.mean(points[:,0])
    lat0 = np.mean(points[:,1])

    crs_local = CRS.from_proj4(
        f"+proj=aeqd +lat_0={lat0} +lon_0={lon0} +ellps=WGS84"
    )

    transformer = Transformer.from_crs(
        "EPSG:4326", crs_local, always_xy=True
    )
    transformer_inv = Transformer.from_crs(
        crs_local, "EPSG:4326", always_xy=True
    )

    # Project lon/lat → meters
    return lambda x: np.column_stack((transformer.transform(x[:,0], x[:,1]))), \
              lambda x: np.column_stack((transformer_inv.transform(x[:,0], x[:,1])))

