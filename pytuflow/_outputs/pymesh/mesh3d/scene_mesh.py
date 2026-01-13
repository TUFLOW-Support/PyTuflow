from enum import Enum

import numpy as np


class FormatConvention(Enum):
    OpenGL = 0  # right-hand: +x = right, +y = up, -z = forward
    OpenGL_2 = 1
    Unreal = 2  # left-hand: +x = forward, +y = right, +z = up - also uses cm
    Unity = 3  # left-hand: +x = right, +y = up, +z = forward
    Blender = 4  # right-hand: +x = right, +y = forward, +z = up



class Blob:

    def __init__(self, n: int, type):
        self.start_pos = 0
        self.data: np.ndarray = np.array([])
        self.buf = None
        self.n = n
        self.type = type

    def __bool__(self) -> bool:
        return bool(self.data.size)

    def size(self) -> int:
        return self.data.size

    def count(self) -> int:
        return self.data.size // self.n

    def blob_size(self) -> int:
        if self.buf is None:
            self.buf = self.data.tobytes()
        return len(self.buf)

    def blob(self):
        if self.buf is None:
            self.buf = self.data.tobytes()
        return self.buf

    def min(self) -> float | int | list[float] | list[int]:
        if self.n == 1:
            return self.type(self.data.min())
        a = np.reshape(self.data, (-1, self.n))
        return [self.type(x) for x in a.min(axis=0).tolist()]

    def max(self) -> float | int | list[float] | list[int]:
        if self.n == 1:
            return self.type(self.data.max())
        a = np.reshape(self.data, (-1, self.n))
        return [self.type(x) for x in a.max(axis=0).tolist()]


class SceneMesh:

    def __init__(self):
        self.start_pos = 0
        self._inds = Blob(1, int)
        self._pos = Blob(3, float)
        self._uv = Blob(2, float)
        self._cd = Blob(3, float)
        self._face_counts = Blob(1, int)

    @property
    def inds(self) -> Blob:
        return self._inds

    @inds.setter
    def inds(self, data: np.ndarray):
        self._inds.data = data

    @property
    def pos(self) -> Blob:
        return self._pos

    @pos.setter
    def pos(self, data: np.ndarray):
        self._pos.data = data

    @property
    def uv(self) -> Blob:
        return self._uv

    @uv.setter
    def uv(self, data: np.ndarray):
        self._uv.data = data

    @property
    def cd(self) -> Blob:
        return self._cd

    @cd.setter
    def cd(self, data: np.ndarray):
        self._cd.data = data

    @property
    def face_counts(self) -> Blob:
        return self._face_counts

    @face_counts.setter
    def face_counts(self, data: np.ndarray):
        self._face_counts.data = data

    def blob_size(self) -> int:
        return self.inds.blob_size() + self.pos.blob_size() + self.cd.blob_size() + self.uv.blob_size()

    def blob(self):
        return self.inds.blob() + self.pos.blob() + self.cd.blob() + self.uv.blob()
