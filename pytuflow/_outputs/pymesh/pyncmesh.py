from pathlib import Path

import numpy as np

from . import PyMesh, PyNCMeshGeometry, PyNCMeshDataExtractor, QgisMeshGeometry, QgisDataExtractor


class PyNCMesh(PyMesh):

    def __init__(self, fpath: str | Path, geom_driver: str = None, engine: str = None):
        super().__init__()
        self.fpath = Path(fpath)
        if (geom_driver and geom_driver.lower()) == 'qgis' or (geom_driver is None and not self.pv_available()):
            self.geom = QgisMeshGeometry(fpath)
        else:
            self.geom = PyNCMeshGeometry(fpath)
        if engine == 'qgis':
            self.extractor = QgisDataExtractor(fpath, extra_datasets=[])
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
