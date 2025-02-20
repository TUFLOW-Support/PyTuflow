from pathlib import Path

import numpy as np


class MeshDriver:

    def __init__(self, mesh: Path):
        self.mesh = mesh

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.mesh.stem}>'

    def __str__(self):
        return self.__repr__()


class DatasetGroup:

    def __init__(self, name: str, type_: str, times: list[float]):
        self.name = name
        self.type = type_
        self.times = np.array(times)

    def __repr__(self):
        return f'<{self.__class__.__name__} {self.name} ({self.type})>'
