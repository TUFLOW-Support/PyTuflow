import contextlib
import typing

import numpy as np

try:
    from netCDF4 import Dataset, Group
except ImportError:
    from ..stubs.netCDF4 import Dataset, Group

from . import DatasetEngine


class NCEngine(DatasetEngine):
    ENGINE_NAME = 'NetCDF4'

    def __contains__(self, data_path: str) -> bool:
        with self.open():
            paths = data_path.split('/')
            item = paths.pop()
            grp, _ = self._group('/'.join(paths))
            if grp.groups:
                return item in grp.groups
            return item in grp.variables

    @staticmethod
    def available() -> bool:
        return '.stubs' not in Dataset.__module__

    @contextlib.contextmanager
    def open(self) -> typing.Generator['NCEngine', None, None]:
        if self.hnd is not None:
            yield self
            return
        try:
            self.hnd = Dataset(self.fpath, 'r')
            yield self
        finally:
            self.close()

    def open_reader(self):
        if self.hnd is None:
            self.hnd = Dataset(self.fpath, 'r')

    def close(self):
        if self.hnd is not None:
            self.hnd.close()
            self.hnd = None

    def get_name(self) -> str:
        with self.open():
            return list(self.hnd.groups.keys())[0]

    def is_xmdf(self) -> bool:
        with self.open():
            if 'File Type' in self.hnd.ncattrs() and \
               self.hnd.getncattr('File Type').upper() == 'XMDF':
                return True
            return False

    def get_property(self, data_path: str, property_name: str) -> typing.Any:
        with self.open():
            grp, varname = self._group(data_path)
            if varname:
                return grp.variables[varname].getncattr(property_name)
            return grp.getncattr(property_name)

    def iterate(self, data_path: str = '') -> typing.Generator[str, None, None]:
        with self.open():
            grp, _ = self._group(data_path)
            if grp.groups:
                yield from grp.groups.keys()
            else:
                yield from grp.variables.keys()

    def data_shape(self, data_path: str) -> tuple[int, ...]:
        with self.open():
            grp, varname = self._group(data_path)
            return grp.variables[varname].shape

    def dimension_names(self, data_path: str) -> tuple[str, ...]:
        if self.is_xmdf():
            return ()
        with self.open():
            grp, varname = self._group(data_path)
            return grp.variables[varname].dimensions

    def data(self, data_path: str, idx: typing.Any = None) -> np.ndarray:
        with self.open():
            grp, varname = self._group(data_path)
            if idx is None:
                a = grp.variables[varname][:]
            else:
                a = grp.variables[varname][idx]
            if np.ma.isMaskedArray(a):
                a_ = np.array(a)
                if np.ma.is_masked(a):
                    a_[a.mask] = np.nan
                a = a_
            return a

    def _group(self, data_path: str) -> tuple[Group | Dataset, str]:
        with self.open():
            paths = data_path.split('/')
            grp = self.hnd
            for p in paths:
                for g in grp.groups.keys():
                    if g.lower() == p.lower():
                        grp = grp.groups[g]
                        break
            varname = paths.pop()
            for var in grp.variables.keys():
                if var.lower() == varname.lower():
                    return grp, var
            return grp, ''
