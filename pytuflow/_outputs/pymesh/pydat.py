from pathlib import Path

from . import PyMesh, Py2dm, PyDATDataExtractor, QgisMeshGeometry, QgisDataExtractor


class PyDAT(PyMesh):

    def __init__(self, fpaths: list[str | Path], twodm: str | Path, geom_driver: str = None, engine: str = None):
        super().__init__()

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
            self.geom = QgisMeshGeometry(twodm)
        else:
            self.geom = Py2dm(twodm)

        if engine == 'qgis':
            if not self.qgis_available():
                raise ValueError("QGIS python bindings not found.")
            if not self.qgis_initialized():
                raise ValueError('QGIS application has not been initialized.')
            self.extractor = QgisDataExtractor(twodm, fpaths)
            self.geom.lyr = self.extractor.lyr
        else:
            self.extractor = PyDATDataExtractor(fpaths, self._map_wet_dry_to_verts)

        self.name = twodm.stem

    def data_types(self) -> list[str]:
        if not self._data_types:
            data_types = self.extractor.data_types()
            self._data_types = ['Bed Elevation'] + data_types if self.geom.has_z else data_types
        return self._data_types
