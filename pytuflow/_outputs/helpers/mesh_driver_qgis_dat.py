from pathlib import Path
from typing import Generator

from .mesh_driver import DatasetGroup
from .mesh_driver_qgis import QgisMeshDriver

try:
    from qgis.core import QgsMeshLayer, QgsApplication
    has_qgis = True
except ImportError:
    has_qgis = False


class QgisDATMeshDriver(QgisMeshDriver):

    def __init__(self, mesh: Path, dats: list[Path]):
        super().__init__(mesh)
        self.driver_name = 'qgis_dat'
        self.dats = dats
        self.name = self.dats[0].stem.rsplit('_', 1)[0]

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.name}>'

    def load(self):
        self.init_mesh_layer(self.name)
        for dat in self.dats:
            success = self.dp.addDataset(str(dat))
            if not success:
                raise RuntimeError(f'Failed to load DAT results onto 2dm: {dat}')

        super().load()

    def data_groups(self) -> Generator[DatasetGroup, None, None]:
        for data_type_group in super().data_groups():
            data_type_group.name = data_type_group.name.replace(self.name, '').strip()
            if data_type_group.name.lower() == 'time':
                for special_time in self.special_times(data_type_group):
                    yield special_time
                return
            # noinspection PyUnresolvedReferences
            if data_type_group.times.tolist() in [[99999.], [-99999.]]:
                data_type_group.times = [0.]
            yield data_type_group

    @staticmethod
    def special_times(data_type_group: DatasetGroup) -> Generator[DatasetGroup, None, None]:
        for time in data_type_group.times:
            if time == 900001.:
                name = 'tmax water level'
            elif time == 900002.:
                name = 'tmax velocity'
            elif 100000 < time < 200000 and time != 111111.0:
                val = time - 100000.0
                name = f'time of cutoff {val}'
            elif 200000 < time < 300000 and time != 222222.0:
                val = time - 200000.0
                name = f'time exceeding cutoff {val}'
            else:
                name = f'special time unknown: {time}'

            yield DatasetGroup(name, 'scalar', [0.], 1)
