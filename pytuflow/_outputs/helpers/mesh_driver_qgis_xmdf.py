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
        if not has_qgis:
            raise ImportError('QGIS python libraries are not installed or cannot be imported.')
        if not QgsApplication.instance():
            raise RuntimeError('QGIS application instance not found.')

        self.lyr = QgsMeshLayer(str(self.mesh), self.xmdf.stem, 'mdal')
        if not self.lyr.isValid():
            raise RuntimeError(f'Failed to load mesh layer {self.mesh}')

        self.dp = self.lyr.dataProvider()
        success = self.dp.addDataset(str(self.xmdf))
        if not success:
            raise RuntimeError(f'Failed to load xmdf results onto 2dm: {self.xmdf}')

        super().load()
