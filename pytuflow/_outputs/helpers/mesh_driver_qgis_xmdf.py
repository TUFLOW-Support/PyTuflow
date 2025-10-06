from pathlib import Path

from .mesh_driver_qgis import QgisMeshDriver

try:
    from qgis.core import QgsMeshLayer, QgsApplication
    has_qgis = True
except ImportError:
    has_qgis = False


class QgisXmdfMeshDriver(QgisMeshDriver):

    def __init__(self, mesh: Path, xmdf: Path):
        super().__init__(mesh)
        self.driver_name = 'qgis_xmdf'
        self.xmdf = xmdf

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.xmdf.stem}>'

    def load(self):
        self.init_mesh_layer(self.xmdf.stem)
        success = self.dp.addDataset(str(self.xmdf))
        if not success:
            raise RuntimeError(f'Failed to load xmdf results onto 2dm: {self.xmdf}')

        super().load()

    def group_index_from_name(self, data_type: str, **kwargs) -> int:
        vel_to_vec_vel = kwargs.get('vel_to_vec_vel', False)
        if vel_to_vec_vel and data_type == 'velocity':
            data_type = 'vector velocity'
        return super().group_index_from_name(data_type)
