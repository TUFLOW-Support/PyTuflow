from pathlib import Path

from . import PyMesh, Py2dm, PyDATDataExtractor, QgisMeshGeometry


class PyDAT(PyMesh):

    def __init__(self, fpaths: list[str | Path], twodm: str | Path, geom_driver: str = None, engine: str = None):
        super().__init__()
        if (geom_driver and geom_driver.lower()) == 'qgis' or (geom_driver is None and not self.pv_available()):
            self.geom = QgisMeshGeometry(twodm)
        else:
            self.geom = Py2dm(twodm)
        if engine == 'qgis':
            pass
        else:
            self.extractor = PyDATDataExtractor(fpaths, self._map_wet_dry_to_verts)
        self.name = twodm.stem
