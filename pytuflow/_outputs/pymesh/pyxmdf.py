from pathlib import Path

from . import PyMesh, Py2dm, PyXMDFDataExtractor, QgisMeshGeometry
from .mesh3d import Mesh3DMixin, GLTFMixin, AlembicMixin


class PyXMDF(PyMesh, Mesh3DMixin, GLTFMixin, AlembicMixin):

    def __init__(self, fpath: Path | str, twodm: Path | str = None, engine: str = None):
        super().__init__()
        self.fpath = Path(fpath)
        if not twodm:
            twodm = self.fpath.with_suffix('.2dm')
        if (engine and engine.lower()) == 'qgis' or (engine is None and self.qgis_available()):
            self.geom = QgisMeshGeometry(twodm)
        else:
            self.geom = Py2dm(twodm)
        self.extractor = PyXMDFDataExtractor(fpath, engine)
        self.name = twodm.stem
        for dtype in self.data_types():
            if dtype.lower() != 'bed elevation':
                ref_time = self.reference_time_(dtype)
                if ref_time is not None:
                    self.has_inherent_reference_time = True
                    self.reference_time = ref_time
                break
