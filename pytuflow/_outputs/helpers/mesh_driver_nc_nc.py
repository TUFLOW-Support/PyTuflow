import re
from datetime import datetime
from pathlib import Path
from typing import Generator

from .mesh_driver_nc import NCMeshDriver, has_nc, Dataset
from .mesh_driver import DatasetGroup


class NCMeshDriverNC(NCMeshDriver):

    def __init__(self, mesh: Path):
        super().__init__(mesh)
        self.driver_name = 'nc_nc'
        self.valid = has_nc
        if self.valid:
            with Dataset(self.mesh) as nc:
                self.has_inherent_reference_time, self.units, self.reference_time = self.parse_reference_time(nc['ResTime'].units)

    def data_groups(self) -> Generator[DatasetGroup, None, None]:
        if not has_nc:
            raise ImportError('netCDF4 not available')

        skip_var = ['ResTime', 'cell_Nvert', 'cell_node', 'NL', 'idx2', 'idx3', 'cell_X',
                    'cell_Y', 'cell_Zb', 'cell_A', 'node_X', 'node_Y', 'node_Zb', 'layerface_Z', 'stat']

        yield DatasetGroup('Bed Elevation', 'scalar', [0.])

        with Dataset(self.mesh) as nc:
            times = nc['ResTime'][:].tolist()
            for var_name, var in nc.variables.items():
                if var_name in skip_var:
                    continue
                type_ = 'scalar'
                if var_name[-2:] == '_x':
                    name_y = var_name.replace('_x', '_y')
                    if name_y in nc.variables:
                        skip_var.append(name_y)
                        type_ = 'vector'

                if hasattr(var, 'long_name'):
                    name = var.long_name
                    if name and name[:2] == 'x_' and type_ == 'vector':
                        name = name[2:]
                else:
                    name = var_name
                    if name[-2:] == '_x' and type_ == 'vector':
                        name = name[:-2]

                yield DatasetGroup(name, type_, times)

    @staticmethod
    def parse_reference_time(string):
        if 'hour' in string:
            units = 'h'
        elif 'second' in string:
            units = 's'
        else:
            units = string.split(' ')[0]

        if re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', string):
            return True, units, datetime.strptime(re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', string)[0],
                                                  '%Y-%m-%d %H:%M:%S')
        elif re.findall(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', string):
            return True, units, datetime.strptime(re.findall(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', string)[0],
                                                  '%Y-%m-%dT%H:%M:%S')

        return False, units, datetime(1990, 1, 1)  # a default value
