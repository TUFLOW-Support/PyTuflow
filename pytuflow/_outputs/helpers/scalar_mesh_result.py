from typing import Union, Generator

import numpy as np
from qgis.core import QgsMeshDatasetValue, QgsMeshDataBlock, QgsMesh3dDataBlock, QgsMeshDatasetIndex

from .mesh_result import MeshResult


class ScalarMeshResult(MeshResult):

    def _value_from_weightings(self,
                               data_blocks: list['QgsMeshDatasetValue'],
                               weightings: tuple[float, float, float]) -> float:
        """Extracts the scalar value from a list of QgsMeshDatasetValue objects and applies interpolation weightings."""
        value = 0
        for db, w in zip(data_blocks, weightings):
            value += db.scalar() * w
        return value

    def _value_from_vertex(self, data_block: 'QgsMeshDatasetValue') -> float:
        """Returns the value from a mesh vertex."""
        return data_block.scalar()

    def _value_from_face_block(self, value_block: Union['QgsMeshDatasetValue', 'QgsMeshDataBlock']) -> float:
        """Returns the value from a mesh face."""
        if isinstance(value_block, QgsMeshDatasetValue):  # 2d
            return value_block.scalar()
        elif value_block.isValid():  # 3d
            if len(value_block.values()) > 1:  # vector result - return magnitude
                return (value_block.values()[0] ** 2 + value_block.values()[1] ** 2) ** 0.5
            else:  # scalar result
                return value_block.values()[0]

        return np.nan

    def _convert_vector_values(self, values: list[float]) -> list[float]:
        return [(values[i] ** 2 + values[i + 1] ** 2) ** 0.5 for i in range(0, len(values), 2)]
