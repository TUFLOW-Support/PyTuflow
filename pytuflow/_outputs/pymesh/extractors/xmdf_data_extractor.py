import contextlib
import typing
from datetime import datetime
from pathlib import Path

import numpy as np

from . import PyDataExtractor
from .. import H5Engine, NCEngine


class PyXMDFDataExtractor(PyDataExtractor):
    """Class for extracting data from XMDF files."""

    def __init__(self, fpath: str | Path, engine: str = None):
        if (H5Engine.available() and engine is None) or (engine and engine.lower() == 'h5py'):
            self.engine = H5Engine(fpath)
        elif (NCEngine.available() and engine is None) or (engine and engine.lower()) == 'netcdf4':
            self.engine = NCEngine(fpath)
        else:
            raise ImportError('Unable to find a library for reading XMDF files. Require NetCDF4 of h5py.')
        self.dataset_name = self.engine.get_name()

    @contextlib.contextmanager
    def open(self) -> typing.Generator['PyXMDFDataExtractor', None, None]:
        """Context manager for opening and closing the data extractor."""
        with self.engine.open():
            yield self

    def open_reader(self):
        self.engine.open_reader()

    def close_reader(self):
        self.engine.close()

    def times(self, data_type: str) -> np.ndarray:
        path = self._create_path(data_type, 'Times')
        times = self.engine.data(path)
        units = self.engine.get_property(self._create_path(data_type, ''), 'TimeUnits')
        if units[0].lower() == 's':
            return times / 3600.
        return times

    def data_types(self) -> list[str]:
        dtypes = []
        for key1 in self.engine.iterate(self.dataset_name):
            for key2 in self.engine.iterate(f'{self.dataset_name}/{key1}'):
                if key1.lower() == 'temporal':
                    dtypes.append(key2)
                else:
                    dtypes.append(f'{key2}/{key1}')
        return dtypes

    def reference_time(self, data_type: str) -> datetime:
        pass

    def is_vector(self, data_type: str) -> bool:
        return self.engine.get_property(self._create_path(data_type, ''), 'Grouptype') == 'DATASET VECTOR'

    def is_static(self, data_type: str) -> bool:
        return self.engine.data_shape(self._create_path(data_type, 'Times'))[0] == 1

    def maximum(self, data_type: str) -> float:
        path = self._create_path(data_type, 'Maxs')
        return float(np.nanmax(self.engine.data(path)))

    def minimum(self, data_type: str) -> float:
        path = self._create_path(data_type, 'Mins')
        return float(np.nanmin(self.engine.data(path)))

    def wd_flag(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> np.ndarray:
        path = self._create_path(data_type, 'Active')
        return self.engine.data(path, index).astype(bool)

    def data(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> np.ndarray:
        return self.engine.data(self._create_path(data_type, 'Values'), index)

    def _create_path(self, data_type: str, varname: str) -> str:
        if '/' in data_type:
            p1, p2 = data_type.split('/', 1)
            data_type = f'{p2}/{p1}'
        return f'{self.dataset_name}/{data_type}/{varname}' if '/' in data_type else f'{self.dataset_name}/Temporal/{data_type}/{varname}'.rstrip('/')
