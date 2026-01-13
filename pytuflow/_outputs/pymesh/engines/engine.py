import contextlib
import typing
from pathlib import Path

import numpy as np


class DatasetEngine:
    ENGINE_NAME = ''

    def __init__(self, fpath: Path | str):
        self.fpath = Path(fpath)
        self.hnd = None
        if not self.available():
            raise ImportError(f'{self.__class__.__name__} is not available.')

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self.fpath.stem}>'

    def __contains__(self, item: str) -> bool:
        return False

    @staticmethod
    def available() -> bool:
        return False

    @contextlib.contextmanager
    def open(self) -> 'DatasetEngine':
        pass

    def close(self):
        pass

    def iterate(self, data_path: str = '') -> typing.Generator[str, None, None]:
        pass

    def get_name(self) -> str:
        pass

    def is_xmdf(self) -> bool:
        pass

    def get_property(self, data_path: str, property_name: str) -> typing.Any:
        pass

    def data_shape(self, data_path: str) -> tuple[int, ...]:
        pass

    def data(self, data_path: str, idx: typing.Any = None) -> np.ndarray:
        pass
