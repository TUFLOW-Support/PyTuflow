import typing
from pathlib import Path

from . import PyMesh, PyNCMeshGeometry, PyNCMeshDataExtractor, QgisMeshGeometry, QgisDataExtractor


class PyNCMesh(PyMesh):

    def __init__(self, fpath: str | Path, geom_driver: str = None, engine: str = None, mesh: typing.Any = None):
        super().__init__()
        self.fpath = Path(fpath)

        if not geom_driver and engine == 'qgis':
            geom_driver = 'qgis'
        elif not geom_driver and not engine:
            if not self.pv_available() and not self.qgis_available():
                raise ValueError('Neither PyVista nor QGIS python bindings were found.')

        if (geom_driver and geom_driver.lower() == 'qgis') or (geom_driver is None and not self.pv_available()):
            if not self.qgis_available():
                raise ValueError("QGIS python bindings not found.")
            if not self.qgis_initialized():
                raise ValueError('QGIS application has not been initialized.')
            self.geom = QgisMeshGeometry(fpath)
            if mesh is not None:
                self.geom.lyr = mesh
        else:
            self.geom = PyNCMeshGeometry(fpath)

        if engine == 'qgis':
            if not self.qgis_available():
                raise ValueError("QGIS python bindings not found.")
            if not self.qgis_initialized():
                raise ValueError('QGIS application has not been initialized.')
            self.extractor = QgisDataExtractor(fpath, extra_datasets=[], layer=self.geom.lyr)
            self.geom.lyr = self.extractor.lyr
        else:
            self.extractor = PyNCMeshDataExtractor(fpath, engine)

        self.geom.spherical = self.extractor.spherical()
        self.name = self.fpath.stem
        with self.extractor.open():
            for dtype in self.data_types():
                if dtype.lower() != 'bed elevation':
                    ref_time = self.reference_time_(dtype)
                    if ref_time is not None:
                        self.has_inherent_reference_time = True
                        self.reference_time = ref_time
                    break

    def translate_data_type(self, data_type: str) -> tuple[str, ...]:
        data_type = super().translate_data_type(data_type)
        if self.extractor.NAME == 'QgisDataExtractor':
            return data_type
        if len(data_type) == 1 and data_type[0].lower() == 'v':
            return 'V_x', 'V_y'
        return data_type
