from calendar import day_abbr
from typing import Generator, Union, Any
import numpy as np

from qgis.core import QgsMeshDatasetValue, QgsMeshDataBlock, QgsMesh3dDataBlock, QgsMeshDatasetIndex

from .mesh_result import MeshResult


class VectorMeshResult(MeshResult):

    def _value_from_weightings(self,
                               data_blocks: list['QgsMeshDatasetValue'],
                               weightings: tuple[float, float, float]) -> tuple[float, float]:
        """
        Extracts the vector (x, y) values from a list of QgsMeshDatasetValue
        objects and applies interpolation weightings.
        """
        x, y = 0, 0
        for db, w in zip(data_blocks, weightings):
            x += db.x() * w
            y += db.y() * w
        return x, y

    def _value_from_vertex(self, data_block: 'QgsMeshDatasetValue') -> tuple[float, float]:
        """Returns the value from a mesh vertex."""
        return data_block.x(), data_block.y()

    def _value_from_face_block(
            self,
            value_block: Union['QgsMeshDatasetValue', 'QgsMeshDataBlock']
    ) -> Any:
        """Returns the value from a mesh face."""
        if isinstance(value_block, QgsMeshDatasetValue):  # 2d
            return value_block.x(), value_block.y()
        elif value_block.isValid():  # 3d
            if len(value_block.values()) > 1:  # vector result
                return value_block.values()[0], value_block.values()[1]

        return np.nan, np.nan

    def _convert_vector_values(self, values: list[float]) -> list[tuple[float, float]]:
        return [(values[i], values[i + 1]) for i in range(0, len(values), 2)]
