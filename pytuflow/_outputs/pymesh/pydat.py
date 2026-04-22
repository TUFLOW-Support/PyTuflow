import typing
from pathlib import Path
import numpy as np

from . import PyMesh, Py2dm, PyDATDataExtractor, QgisMeshGeometry, QgisDataExtractor


class PyDAT(PyMesh):

    def __init__(self, fpaths: list[str | Path], twodm: str | Path, geom_driver: str = None, engine: str = None, mesh: typing.Any = None):
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
            if mesh:
                self.geom.lyr = mesh
        else:
            self.geom = Py2dm(twodm)

        if engine == 'qgis':
            if not self.qgis_available():
                raise ValueError("QGIS python bindings not found.")
            if not self.qgis_initialized():
                raise ValueError('QGIS application has not been initialized.')
            self.extractors = [QgisDataExtractor(twodm, fpaths, layer=self.geom.lyr)]
            self.geom.lyr = self.extractors[0].lyr
        else:
            self.extractors = [PyDATDataExtractor(fpaths)]

        self.name = twodm.stem
        self._preload(self.extractors[0])
    
    def add_data(self, fpath: str | Path):
        existing_extractor = self.extractors[0]
        if existing_extractor.NAME == 'PyDataExtractor':
            new_extractor = PyDATDataExtractor([fpath])
            self.extractors.append(new_extractor)
        else:
            existing_extractor.add_data(fpath)
            new_extractor = existing_extractor
        self._data_types.clear()
        self._preload(new_extractor)  
