import typing
from pathlib import Path
import numpy as np

from . import PyMesh, PyDataExtractor, PyNCMeshGeometry, PyNCMeshDataExtractor, QgisMeshGeometry, QgisDataExtractor
from .mesh3d import Mesh3DMixin, GLTFMixin


class PyNCMesh(PyMesh, Mesh3DMixin, GLTFMixin):

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

        if engine == 'qgis' or (engine is None and not self.external_engine_available() and self.qgis_available()):
            if not self.qgis_available():
                raise ValueError("QGIS python bindings not found.")
            if not self.qgis_initialized():
                raise ValueError('QGIS application has not been initialized.')
            self.extractors = [QgisDataExtractor(fpath, extra_datasets=[], layer=self.geom.lyr)]
            self.geom.lyr = self.extractors[0].lyr
        elif self.external_engine_available():
            self.extractors = [PyNCMeshDataExtractor(fpath, engine)]
        else:
            raise ValueError('No suitable engine found for data extraction.')

        self.geom.spherical = self.extractors[0].spherical()
        self.name = self.fpath.stem
        self._preload(self.extractors[0])
        
    @property
    def shared_active_flags(self) -> bool:
        return True

    def translate_data_type(self, data_type: str) -> tuple[str, ...]:
        data_type_ = super().translate_data_type(data_type)
        for i, extractor in enumerate(self.extractors):
            if isinstance(extractor, PyNCMeshDataExtractor):
                data_type_1 = tuple([extractor.long_name_to_variable.get(x, x) for x in data_type_])
                if data_type_1 == data_type_ and i + 1 < len(self.extractors):
                    continue
                data_type_ = data_type_1
            if extractor.NAME == 'QgisDataExtractor':
                return data_type_
            if len(data_type_) == 1 and data_type_[0].lower() == 'v':
                return 'V_x', 'V_y'
            return data_type_
        raise ValueError(f'Could not translate data_type: {data_type}')
    
    def add_data(self, fpath: str | Path):
        existing_extractor = self.extractors[0]
        if existing_extractor.NAME == 'PyDataExtractor':
            new_extractor = PyNCMeshDataExtractor(fpath, existing_extractor.engine.ENGINE_NAME)
        else:
            new_extractor = QgisDataExtractor(fpath, extra_datasets=[], layer=None)
        self.extractors.append(new_extractor)
        self._data_types.clear()
        self._preload(new_extractor)
