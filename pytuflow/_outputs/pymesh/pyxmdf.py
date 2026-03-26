import typing
from pathlib import Path

from . import PyMesh, Py2dm, PyXMDFDataExtractor, QgisMeshGeometry, QgisDataExtractor
from .mesh3d import Mesh3DMixin, GLTFMixin, AlembicMixin


class PyXMDF(PyMesh, Mesh3DMixin, GLTFMixin, AlembicMixin):

    def __init__(self, fpath: Path | str, twodm: Path | str = None, geom_driver: str = None, engine: str = None, mesh: typing.Any = None):
        super().__init__()
        self.fpath = Path(fpath)
        if not twodm:
            twodm = self.fpath.with_suffix('.2dm')

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
            if mesh is not None:
                self.geom.lyr = mesh
        else:
            self.geom = Py2dm(twodm)

        if fpath.suffix.lower() == '.2dm':  # won't use netcdf4 or h5py
            self.extractor = PyXMDFDataExtractor(fpath, None)
        elif engine == 'qgis' or (engine is None and not self.external_engine_available() and self.qgis_available()):
            if not self.qgis_available():
                raise ValueError("QGIS python bindings not found.")
            if not self.qgis_initialized():
                raise ValueError('QGIS application has not been initialized.')
            self.extractor = QgisDataExtractor(twodm, [fpath], layer=self.geom.lyr)
            self.geom.lyr = self.extractor.lyr
        elif self.external_engine_available():
            self.extractor = PyXMDFDataExtractor(fpath, engine)
        else:
            raise ValueError('No suitable engine found for data extraction.')

        self.name = twodm.stem
        for dtype in self.data_types():
            if dtype.lower() != 'bed elevation':
                ref_time = self.reference_time_(dtype)
                if ref_time is not None:
                    self.has_inherent_reference_time = True
                    self.reference_time = ref_time
                    break
