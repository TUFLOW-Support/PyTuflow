import typing

import numpy as np
import pandas as pd

try:
    import shapely
except ImportError:
    from ..stubs import shapely

try:
    import vtk
except ImportError:
    from ..stubs import vtk


PointLike = tuple[float,...] | typing.Iterable[float] | shapely.Point | vtk.vtkDataArray


class PointMixin:

    @staticmethod
    def _coerce_into_point(value: PointLike) -> np.ndarray:
        if isinstance(value, np.ndarray):
            return value.flatten()
        elif isinstance(value, shapely.Point):
            return np.array([value.x, value.y])
        elif isinstance(value, vtk.vtkDataArray):
            return np.array(value.GetTuple(0)).flatten()
        elif isinstance(value, (pd.Series, pd.DataFrame)):
            return value.to_numpy().flatten()
        return np.array(value)

    @staticmethod
    def _point_as_wkt(value: PointLike) -> str:
        point = PointMixin._coerce_into_point(value)
        return f'POINT ({point[0]:.6f} {point[1]:.6f})'
