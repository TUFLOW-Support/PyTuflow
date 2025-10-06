from pathlib import Path

from .mesh_driver_qgis import QgisMeshDriver

try:
    from qgis.core import QgsMeshLayer, QgsApplication
    has_qgis = True
except ImportError:
    has_qgis = False


class QgisNcMeshDriver(QgisMeshDriver):

    def __init__(self, mesh: Path):
        super().__init__(mesh)
        self.driver_name = 'qgis_nc'

    def load(self):
        self.init_mesh_layer(self.mesh.stem)
        super().load()
