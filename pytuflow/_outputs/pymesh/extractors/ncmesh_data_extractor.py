import contextlib
import typing
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import PyDataExtractor
from ..engines import H5Engine, NCEngine


class PyNCMeshDataExtractor(PyDataExtractor):
    NON_RESULT_VARIABLES = [
        'restime',
        'cell_nvert',
        'cell_node',
        'nl',
        'idx2',
        'idx3',
        'cell_x',
        'cell_y',
        'cell_zb',
        'cell_a',
        'node_x',
        'node_y',
        'node_zb',
        'layerface_z',
        'stat'
    ]

    def __init__(self, fpath: str | Path, engine: str = None):
        if (H5Engine.available() and engine is None) or (engine and engine.lower() == 'h5py'):
            self.engine = H5Engine(fpath)
        elif (NCEngine.available() and engine is None) or (engine and engine.lower() == 'netcdf4'):
            self.engine = NCEngine(fpath)
        else:
            raise ImportError('Unable to find a library for reading NCMesh files. Require NetCDF4 of h5py.')

    @contextlib.contextmanager
    def open(self) -> typing.Generator['PyNCMeshDataExtractor', None, None]:
        """Context manager for opening and closing the data extractor."""
        with self.engine.open():
            yield self

    def times(self, data_type: str) -> np.ndarray:
        if self.is_static(data_type):
            return np.array([])
        return self.engine.data('ResTime')

    def data_types(self) -> list[str]:
        dtypes = []
        for variable in self.engine.iterate():
            if variable.lower() not in self.NON_RESULT_VARIABLES:
                if variable.lower().endswith('_x'):
                    dtypes.append(variable[:-2])
                elif variable.lower().endswith('_y'):
                    continue
                elif variable.lower() == 'zb':
                    continue
                else:
                    dtypes.append(variable)
        return ['Bed Elevation'] + dtypes

    def reference_time(self, data_type: str) -> datetime | None:
        units = self.engine.get_property('ResTime', 'units')
        if 'since' in units:
            ref_str = units.split('since')[1].strip()
            try:
                ref_time = datetime.fromisoformat(ref_str)
            except ValueError:
                ref_time = datetime.strptime(ref_str, '%Y-%m-%d %H:%M:%S')
            if ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=timezone.utc)
            return ref_time
        return None

    def is_vector(self, data_type: str) -> bool:
        test = f'{data_type}_x' if not data_type.endswith('_x') else data_type
        return test in self.engine

    def is_3d(self, data_type: str) -> bool:
        if 'numcells3d' in [x.lower() for x in self.engine.dimension_names(data_type)]:
            return True
        return False

    def is_static(self, data_type: str) -> bool:
        dims = self.engine.dimension_names(data_type)
        if 'time' not in [x.lower() for x in dims]:
            return True
        if self.engine.data_shape(data_type)[[x.lower() for x in dims].index('time')] == 1:
            return True
        return False

    def spherical(self) -> bool:
        if self.engine.ENGINE_NAME == 'NetCDF4':
            try:
                return self.engine.get_property('', 'spherical').lower() == 'true'
            except AttributeError:
                return False
        else:
            return self.engine.get_property('cell_X', 'units').lower() == 'decimal degrees'

    def maximum(self, data_type: str) -> float:
        return float(self.engine.data(data_type).max())

    def minimum(self, data_type: str) -> float:
        return float(self.engine.data(data_type).min())

    def data(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> np.ndarray:
        return self.engine.data(data_type, index)

    def wd_flag(self, data_type: str, index: PyDataExtractor.SliceType | PyDataExtractor.MultiSliceType) -> np.ndarray:
        return self.engine.data('stat', index).astype(bool)

    def dimension_names(self, variable_name: str) -> tuple[str, ...]:
        return self.engine.dimension_names(variable_name)
