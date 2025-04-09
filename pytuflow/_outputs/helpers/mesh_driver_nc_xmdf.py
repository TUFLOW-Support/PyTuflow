from pathlib import Path
from typing import Generator

from .mesh_driver_nc import NCMeshDriver, has_nc, Dataset
from .mesh_driver import DatasetGroup



class NCMeshDriverXmdf(NCMeshDriver):

    def __init__(self, mesh: Path, xmdf: Path):
        super().__init__(mesh)
        self.driver_name = 'nc_xmdf'
        self.xmdf = xmdf
        self.valid = has_nc

    def data_groups(self) -> Generator[DatasetGroup, None, None]:
        if not has_nc:
            raise ImportError('netCDF4 not available')

        yield DatasetGroup('Bed Elevation', 'scalar', [0.])

        with Dataset(self.xmdf) as nc:
            for res_name, res in nc.groups.items():
                for grpname, grp in res.groups.items():
                    for dtypename, dtype in grp.groups.items():
                        name = f'{dtypename}/{grpname}' if grpname.lower() in ['maximums', 'minimums'] else dtypename
                        type_ = 'vector' if 'vector' in dtype.Grouptype.lower() else 'scalar'
                        times = dtype.variables['Times'][:].tolist()
                        yield DatasetGroup(name, type_, times, 1)
