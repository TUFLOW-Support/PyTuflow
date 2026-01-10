from pathlib import Path

from . import PyMesh, Py2dm, PyXMDFDataExtractor, QgisMeshGeometry, QgisDataExtractor
from .mesh3d import Mesh3DMixin, GLTFMixin, AlembicMixin


class PyXMDF(PyMesh, Mesh3DMixin, GLTFMixin, AlembicMixin):

    def __init__(self, fpath: Path | str, twodm: Path | str = None, geom_driver: str = None, engine: str = None):
        super().__init__()
        self.fpath = Path(fpath)
        if not twodm:
            twodm = self.fpath.with_suffix('.2dm')
        if (geom_driver and geom_driver.lower()) == 'qgis' or (geom_driver is None and not self.pv_available()):
            self.geom = QgisMeshGeometry(twodm)
        else:
            self.geom = Py2dm(twodm)
        if engine == 'qgis':
            self.extractor = QgisDataExtractor(twodm, [fpath])
            self.geom.lyr = self.extractor.lyr
        else:
            self.extractor = PyXMDFDataExtractor(fpath, engine)
        self.name = twodm.stem
        for dtype in self.data_types():
            if dtype.lower() != 'bed elevation':
                ref_time = self.reference_time_(dtype)
                if ref_time is not None:
                    self.has_inherent_reference_time = True
                    self.reference_time = ref_time
                    break
