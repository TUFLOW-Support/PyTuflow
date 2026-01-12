from pathlib import Path

from . import PyMesh, Py2dm, PyDATDataExtractor, QgisMeshGeometry, QgisDataExtractor


class PyDAT(PyMesh):

    def __init__(self, fpaths: list[str | Path], twodm: str | Path, geom_driver: str = None, engine: str = None):
        super().__init__()
        if (geom_driver and geom_driver.lower()) == 'qgis' or (geom_driver is None and not self.pv_available()):
            self.geom = QgisMeshGeometry(twodm)
        else:
            self.geom = Py2dm(twodm)
        if engine == 'qgis':
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
