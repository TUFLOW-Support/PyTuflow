import typing
from pathlib import Path

from . import PyMesh, Py2dm, PyDataExtractor, PyXMDFDataExtractor, QgisMeshGeometry, QgisDataExtractor
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
            self.extractors = [PyXMDFDataExtractor(fpath, None)]
        elif engine == 'qgis' or (engine is None and not self.external_engine_available() and self.qgis_available()):
            if not self.qgis_available():
                raise ValueError("QGIS python bindings not found.")
            if not self.qgis_initialized():
                raise ValueError('QGIS application has not been initialized.')
            self.extractors = [QgisDataExtractor(twodm, [fpath], layer=self.geom.lyr)]
            self.geom.lyr = self.extractors[0].lyr
        elif self.external_engine_available():
            self.extractors = [PyXMDFDataExtractor(fpath, engine)]
        else:
            raise ValueError('No suitable engine found for data extraction.')

        self.name = twodm.stem
        self._preload(self.extractors[0])

    def add_data(self, fpath: str | Path):
        existing_extractor = self.extractors[0]
        if existing_extractor.NAME == 'PyDataExtractor':
            new_extractor = PyXMDFDataExtractor(fpath, existing_extractor.engine.ENGINE_NAME)
            self.extractors.append(new_extractor)
        else:
            existing_extractor.add_data(fpath)
            new_extractor = existing_extractor
        self._data_types.clear()
        self._preload(new_extractor)

    def _preload(self, extractor: PyDataExtractor):
        data_types = set(extractor.data_types())
        self._data_type_to_extractor.append(data_types)
        for dtype in data_types.copy():
            dtype_translated = self.translate_data_type(dtype)
            for dtype_translated_ in dtype_translated:
                if dtype_translated_ not in data_types:
                    data_types.add(dtype_translated_)
            if dtype.lower() != 'bed elevation':
                ref_time = self.reference_time_(dtype)
                if ref_time is not None:
                    self.has_inherent_reference_time = True
                    self.reference_time = ref_time
                    break
        
