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

    def _vertical_iter(self, dataset_3d: 'QgsMesh3dDataBlock', interpolation: str) -> Generator[tuple[float, float], None, None]:
        vertical_levels = dataset_3d.verticalLevels()
        values = dataset_3d.values()
        if (len(vertical_levels) - 1) * 2 == len(values):  # vector
            values = [(values[i] ** 2 + values[i + 1] ** 2) ** 0.5 for i in range(0, len(values), 2)]
        if interpolation == 'stepped':
            x_ = sum([[x, x] for x in values], [])
            y_ = sum([[y, y] for y in vertical_levels], [])[1:-1]
        elif interpolation == 'linear':
            x_ = values
            y_ = [(vertical_levels[i] + x) / 2. for i, x in enumerate(vertical_levels[1:])]
        for x, y in zip(x_, y_):
            yield y, x

    # def _2d_elevations(self, dataset_index: 'QgsMeshDatasetIndex') -> Generator[float, None, None]:
    #     yield self.result_from_name(dataset_index, ['water level', 'water surface elevation'])
    #     yield self.bed_elevation()
