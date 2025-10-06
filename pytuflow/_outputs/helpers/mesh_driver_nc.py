from datetime import datetime, timezone
from pathlib import Path

from .mesh_driver import MeshDriver

try:
    from netCDF4 import Dataset
    has_nc = True
except ImportError:
    has_nc = False
    Dataset = 'Dataset'


class NCMeshDriver(MeshDriver):

    def __init__(self, mesh: Path):
        super().__init__(mesh)
        self.reference_time = datetime(1990, 1, 1, tzinfo=timezone.utc)
        self.valid = False
