import numpy as np

try:
    from netCDF4 import Dataset
    has_nc = True
except ImportError:
    Dataset = 'Dataset'
    has_nc = False


class NCGridVar:

    def __init__(self, nc: Dataset, varname: str):
        if not has_nc:
            raise ImportError('netCDF4 is not installed.')
        self.name = varname
        xdims = self.grid_axis_dims(nc, 'x')
        ydims = self.grid_axis_dims(nc, 'y')
        self.var = nc.variables[varname]
        self.static = len(self.var.shape) == 2 or (len(self.var.shape) == 3 and self.var.shape[0] == 1)
        i, j = 0, 0
        if len(self.var.shape) == 3:
            i, j = 1, 2
        elif len(self.var.shape) == 2:
            i, j = 0, 1
        self.valid = len(self.var.shape) >= 2 and self.var.dimensions[i] in ydims and self.var.dimensions[j] in xdims
        if not self.valid:
            return
        x = nc.variables[xdims[0]][:]
        y = nc.variables[ydims[0]][:]
        self.dx = x[1] - x[0]
        self.dy = y[1] - y[0]
        self.ox = np.min(x) - self.dx / 2.
        self.oy = np.min(y) - self.dy / 2.
        self.ncol = self.var.shape[j]
        self.nrow = self.var.shape[i]
        self.is_max = varname.lower().startswith('maximum_')
        self.is_min = varname.lower().startswith('minimum_')
        self.type = 'scalar'
        if not self.static:
            self.times = nc.variables['time'][:]

    @staticmethod
    def grid_axis_dims(nc: Dataset, axis: str) -> list[str]:
        return [name for name, dim in nc.dimensions.items() if name in nc.variables and
                hasattr(nc.variables[name], 'axis') and nc.variables[name].axis.lower() == axis.lower()]
