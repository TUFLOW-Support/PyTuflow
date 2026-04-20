import contextlib
import typing

import numpy as np

try:
    import h5py
except ImportError:
    from ..stubs import h5py

from . import DatasetEngine


class H5Engine(DatasetEngine):
    ENGINE_NAME = 'h5py'

    def __contains__(self, data_path: str) -> bool:
        with self.open():
            path = self._case_correct_path(data_path)
            if len(path) != len(data_path):
                return False
            path = path.split('/')
            varname = path.pop()
            path = '/'.join(path)
            return varname in list(self.hnd[path].keys()) if path else varname in list(self.hnd.keys())

    @staticmethod
    def available() -> bool:
        return '.stubs' not in h5py.__name__

    @contextlib.contextmanager
    def open(self) -> typing.Generator['H5Engine', None, None]:
        if self.hnd is not None:
            yield self
            return
        try:
            self.hnd = h5py.File(self.fpath, 'r')
            yield self
        finally:
            self.close()
            self.hnd = None

    def open_reader(self):
        if self.hnd is None:
            self.hnd = h5py.File(self.fpath, 'r')

    def close(self):
        if self.hnd is not None:
            self.hnd.close()
            self.hnd = None

    def get_name(self) -> str:
        with self.open():
            return [x for x in self.hnd.keys() if x not in ['File Type', 'File Version']][0]

    def is_xmdf(self) -> bool:
        with self.open():
            return 'File Type' in self.hnd and self.hnd['File Type'][0].decode('utf-8').upper() == 'XMDF'

    def get_property(self, data_path: str, property_name: str) -> typing.Any:
        with self.open():
            path = self._case_correct_path(data_path)
            if path:
                prop = self.hnd[path].attrs[property_name]
            else:
                prop = self.hnd.attrs[property_name]
            if isinstance(prop, np.ndarray):
                if prop.dtype.type is np.bytes_:
                    ret = tuple([p.decode('utf-8') for p in prop])
                    if len(ret) == 1:
                        return ret[0]
                    return ret
                return tuple(prop.tolist())
            elif isinstance(prop, bytes):
                return prop.decode('utf-8')
            return prop

    def iterate(self, data_path: str = '') -> typing.Generator[str, None, None]:
        with self.open():
            path = self._case_correct_path(data_path)
            if path:
                yield from self.hnd[path].keys()
            else:
                for k in self.hnd.keys():
                    if '_Netcdf4Dimid' not in self.hnd[k].attrs.keys():
                        yield k

    def data_shape(self, data_path: str) -> tuple[int, ...]:
        with self.open():
            path = self._case_correct_path(data_path)
            return self.hnd[path].shape

    def dimension_names(self, data_path: str) -> tuple[str, ...]:
        if self.is_xmdf():
            return ()
        with self.open():
            prop = self.get_property(data_path, 'DIMENSION_LIST')
            return tuple([self.hnd[x[0]].name.strip('/') for x in prop])

    def data(self, data_path: str, idx: typing.Any = None) -> np.ndarray:
        with self.open():
            path = self._case_correct_path(data_path)
            if idx is None:
                return self.hnd[path][:]
            else:
                contiguous, post_idx = self._to_contiguous(idx)
                a = self.hnd[path][contiguous]
                if post_idx is not None:
                    return np.asarray(a)[post_idx]
                return a

    def _case_correct_path(self, data_path: str) -> str:
        # assume file is already open
        paths = data_path.split('/')
        ret_path = ''
        grp = self.hnd
        for p in paths:
            for g in grp.keys():
                if g.lower() == p.lower():
                    ret_path = f'{ret_path}/{g}' if ret_path else g
                    grp = grp[g]
                    break
        return ret_path
