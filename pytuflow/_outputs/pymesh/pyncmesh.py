import typing
from pathlib import Path
import numpy as np

from . import PyMesh, PyNCMeshGeometry, PyNCMeshDataExtractor, QgisMeshGeometry, QgisDataExtractor
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
        with self.extractors[0].open():
            data_types = set(self.data_types())
            self._data_type_to_extractor.append(data_types)
            for dtype in data_types.copy():
                if dtype.lower() != 'bed elevation':
                    dtype_translated = self.translate_data_type(dtype)
                    for dtype_translated_ in dtype_translated:
                        if dtype_translated_ not in data_types:
                            data_types.add(dtype_translated_)
                    ref_time = self.reference_time_(dtype)
                    if ref_time is not None:
                        self.has_inherent_reference_time = True
                        self.reference_time = ref_time
                    break
        
    @property
    def shared_active_flags(self) -> bool:
        return True

    def translate_data_type(self, data_type: str) -> tuple[str, ...]:
        data_type_ = super().translate_data_type(data_type)
        for i, extractor in enumerate(self.extractors):
            if isinstance(extractor, PyNCMeshDataExtractor):
                data_type_ = tuple([extractor.long_name_to_variable.get(x, x) for x in data_type_])
                if data_type_ == data_type and i + 1 < len(self.extractors):
                    continue
            if extractor.NAME == 'QgisDataExtractor':
                return data_type_
            if len(data_type_) == 1 and data_type_[0].lower() == 'v':
                return 'V_x', 'V_y'
            return data_type_
        raise ValueError(f'Could not translate data_type: {data_type}')
