import typing

import numpy as np
try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

try:
    import shapely
except ImportError:
    from ..stubs import shapely

try:
    import geopandas as gpd
except ImportError:
    from ..stubs import geopandas as gpd

try:
    import vtk
except ImportError:
    from ..stubs import vtk


LineStringLike = typing.Iterable[float | typing.Iterable[float] | tuple[float,...]] | shapely.LineString | vtk.vtkDataArray | vtk.vtkPoints


class LineStringMixin:

    @staticmethod
    def _coerce_into_line(linestring: LineStringLike) -> np.ndarray:
        if isinstance(linestring, np.ndarray):
            return linestring.reshape((-1, 2))
        elif isinstance(linestring, (shapely.LineString, gpd.GeoSeries)):
            if isinstance(linestring, gpd.GeoSeries):
                linestring = linestring.iloc[0]
            return np.array(linestring.coords)
        elif isinstance(linestring, (pd.DataFrame, pd.Series)):
            return linestring.to_numpy().reshape((-1, 2))
        elif isinstance(linestring, (vtk.vtkDataArray, vtk.vtkPoints)):
            if isinstance(linestring, vtk.vtkPoints):
                linestring = linestring.GetData()
            return np.array([linestring.GetTuple(x) for x in range(linestring.GetNumberOfTuples())]).reshape((-1, 2))
        return np.array(linestring).reshape((-1, 2))

    @staticmethod
    def _linestring_as_wkt(linestring: np.ndarray) -> str:
        return 'LINESTRING({0})'.format(', '.join([f'{x[0]:.6f} {x[1]:.6f}' for x in linestring]))
