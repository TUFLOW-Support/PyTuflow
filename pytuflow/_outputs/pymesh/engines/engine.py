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
        yield self

    def open_reader(self):
        pass

    def close(self):
        pass

    def iterate(self, data_path: str = '') -> typing.Generator[str, None, None]:
        pass

    def get_name(self) -> str:
        return self.fpath.stem

    def is_xmdf(self) -> bool:
        pass

    def get_property(self, data_path: str, property_name: str) -> typing.Any:
        pass

    def data_shape(self, data_path: str) -> tuple[int, ...]:
        pass

    def data(self, data_path: str, idx: typing.Any = None) -> np.ndarray:
        pass

    @staticmethod
    def _to_contiguous(idx: typing.Any) -> tuple[typing.Any, typing.Any]:
        """Convert fancy indexing to contiguous slices, returning (contiguous_idx, post_idx).

        post_idx is None when no fancy indexing was present.
        """
        dims = idx if isinstance(idx, tuple) else (idx,)
        contiguous, post_idx, has_fancy = [], [], False

        for dim in dims:
            if isinstance(dim, (list, np.ndarray)):
                arr = np.asarray(dim)
                if arr.dtype == bool:
                    arr = np.where(arr)[0]
                mn = int(arr.min())
                contiguous.append(slice(mn, int(arr.max()) + 1))
                post_idx.append(arr - mn)
                has_fancy = True
            else:
                contiguous.append(dim)
                # Scalar integers squeeze their dimension; don't add a post-index entry for them
                if not isinstance(dim, (int, np.integer)):
                    post_idx.append(slice(None))

        def _unpack(seq):
            return seq[0] if len(seq) == 1 else tuple(seq)

        return _unpack(contiguous), (_unpack(post_idx) if has_fancy else None)
