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

    def _vertical_iter(
            self,
            dataset_3d: 'QgsMesh3dDataBlock',
            interpolation: str
    ) -> Generator[tuple[float, tuple[float, float]], None, None]:
        """Yields vertical level and vector (x, y) values from a 3d mesh dataset."""
        vertical_levels = dataset_3d.verticalLevels()
        z_values = [(vertical_levels[i] + x) / 2. for i, x in enumerate(dataset_3d.verticalLevels()[1:])]
        values = dataset_3d.values()
        if (len(vertical_levels) - 1) * 2 != len(values):  # not vector
            return
        values = [(values[i], values[i + 1]) for i in range(0, len(values), 2)]
        for z, value in zip(z_values, values):
            yield z, value

    # def _2d_elevations(self, dataset_index: 'QgsMeshDatasetIndex') -> Generator[float, None, None]:
    #     wl = self.result_from_name(dataset_index, ['water level', 'water surface elevation'])
    #     z = self.bed_elevation()
    #     yield (wl + z) / 2.
