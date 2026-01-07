from pathlib import Path

from . import PyMesh, Py2dm, PyDATDataExtractor


class PyDAT(PyMesh):

    def __init__(self, fpaths: list[str | Path], twodm: str | Path):
        super().__init__()
        self.geom = Py2dm(twodm)
        self.extractor = PyDATDataExtractor(fpaths, self._map_wet_dry_to_verts)
        self.name = twodm.stem
