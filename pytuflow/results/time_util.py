import re
from datetime import datetime
from typing import Union

import numpy as np
try:
    from netCDF4 import Dataset
except ImportError:
    Dataset = None


default_reference_time = datetime(1990, 1, 1)


def nc_time_series_reference_time(nc):
    if Dataset is None:
        raise ModuleNotFoundError('netCDF4 is not installed')
    with Dataset(nc, 'r') as ds:
        units = ds.variables['time'].units
        if 'hour' in units:
            u = 'h'
        elif 'minute' in units:
            u = 'm'
        elif 'second' in units:
            u = 's'
        elif 'since' in units:
            u = units[:units.index('since')].strip()
        else:
            u = units
        time = re.findall(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', units)
        if time:
            return datetime.strptime(time[0], '%Y-%m-%d %H:%M'), u
    return default_reference_time, u



def closest_time_index(timesteps: list[Union[float, datetime]], time: Union[float, datetime], method: str = 'previous', tol: float = 0.001):
    if isinstance(time, datetime):
        a = np.array([abs((x - time).total_seconds()) for x in timesteps])
    else:
        a = np.array([abs(x - time) for x in timesteps])

    isclose = np.isclose(a, 0, rtol=0., atol=tol)
    if isclose.any():
        return np.argwhere(isclose).flatten()[0]

    if method == 'previous':
        prev = a < time
        if prev.any():
            return np.argwhere(prev).flatten()[-1]
        else:
            return 0
    elif method == 'next':
        next = a > time
        if next.any():
            return np.argwhere(next).flatten()[0]
        else:
            return len(timesteps) - 1
