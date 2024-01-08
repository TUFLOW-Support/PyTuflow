import re
from datetime import datetime
from pathlib import Path
from typing import Union

import numpy as np
try:
    from netCDF4 import Dataset
except ImportError:
    Dataset = None


default_reference_time = datetime(1990, 1, 1)


def parse_time_units_string(string: str, regex: str, format: str) -> tuple[datetime, str]:
    if 'hour' in string:
        u = 'h'
    elif 'minute' in string:
        u = 'm'
    elif 'second' in string:
        u = 's'
    elif 'since' in string:
        u = string.split(' ')[0]
    else:
        u = string
    time = re.findall(regex, string)
    if time:
        return datetime.strptime(time[0], format), u
    return default_reference_time, u


def gpkg_time_series_reference_time(gpkg: Union[str, Path]) -> tuple[datetime, str]:
    import sqlite3
    try:
        conn = sqlite3.connect(gpkg)
        cur = conn.cursor()
        cur.execute('SELECT Reference_time FROM Timeseries_info LIMIT 1;')
        units = cur.fetchone()[0]
        rt, u = parse_time_units_string(units, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', '%Y-%m-%d %H:%M:%S')
    except Exception as e:
        rt, u = default_reference_time, ''
    finally:
        cur = None
        conn.close()
        return rt, u


def nc_time_series_reference_time(nc: Union[str, Path]) -> tuple[datetime, str]:
    if Dataset is None:
        raise ModuleNotFoundError('netCDF4 is not installed')
    with Dataset(nc, 'r') as ds:
        units = ds.variables['time'].units
        return parse_time_units_string(units, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', '%Y-%m-%d %H:%M:%S')



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
