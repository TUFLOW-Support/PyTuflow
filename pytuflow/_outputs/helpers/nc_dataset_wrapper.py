try:
    from netCDF4 import Dataset
    has_netcdf4 = True
except ImportError:
    Dataset = 'Dataset'
    has_netcdf4 = False


class DatasetWrapper:
    """Wrap ``Dataset``class so that it can be called with context manager regardless of whether file exists."""

    def __init__(self, filename, mode='r', clobber=True, nc_format='NETCDF4',
                 diskless=False, persist=False, keepweakref=False,
                 memory=None, encoding=None, parallel=False,
                 comm=None, info=None, auto_complex=False, **kwargs):
        self._filename = filename
        self._nc = None
        if filename is None:
            return
        if not has_netcdf4:
            raise ImportError("netCDF4 is not installed")

        self._nc = Dataset(filename, mode, clobber, nc_format, diskless, persist, keepweakref,
                           memory, encoding, parallel, comm, info, auto_complex, **kwargs)

    def __enter__(self):
        return self._nc

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self._nc is not None:
            self._nc.close()
