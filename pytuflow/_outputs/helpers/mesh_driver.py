from pathlib import Path
from typing import Generator

import numpy as np


class DatasetGroup:

    def __init__(self, name: str, type_: str, times: list[float], vert_lyr_count):
        self.name = name
        self.type = type_
        self.times = np.array(times)
        self.units = 'h'
        self.vert_lyr_count = vert_lyr_count

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.name} ({self.type})>'


class MeshDriver:

    def __init__(self, mesh: Path):
        self.mesh = mesh
        self.reference_time = None
        self.has_inherent_reference_time = False

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.mesh.stem}>'

    def __str__(self):
        return self.__repr__()

    def data_groups(self) -> Generator[DatasetGroup, None, None]:
        raise NotImplementedError
