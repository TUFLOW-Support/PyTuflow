import re
from datetime import datetime
from typing import Union
from pytuflow.types import PathLike, TimeLike

import numpy as np
try:
    from netCDF4 import Dataset
except ImportError:
    Dataset = None


default_reference_time = datetime(1990, 1, 1)


def parse_time_units_string(string: str, regex: str, format: str) -> tuple[datetime, str]:
    """Parses a string containing the time units and reference time
    e.g. hours since 1990-01-01 00:00:00
    Returns the reference time as a datetime object, the time units as a single character.

    Parameters
    ----------
    string : str
       String containing the time units and reference time.
    regex : str
        Regular expression to match the format of the reference time.
    format : str
        Format of the reference time.

    Returns
    -------
    tuple[datetime, str]
        Reference time and time units.
    """
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


def gpkg_time_series_reference_time(gpkg: PathLike) -> tuple[datetime, str]:
    """Returns the reference time and units from a GeoPackage time series result.

    Parameters
    ----------
    gpkg : PathLike
        Path to the GeoPackage file.

    Returns
    -------
    tuple[datetime, str]
        Reference time and time units.
    """
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


def nc_time_series_reference_time(nc: PathLike) -> tuple[datetime, str]:
    """Returns the reference time and units from a netCDF time series result.

    Parameters
    ----------
    nc : PathLike
        Path to the netCDF file.

    Returns
    -------
    tuple[datetime, str]
        Reference time and time units.
    """
    if Dataset is None:
        raise ModuleNotFoundError('netCDF4 is not installed')
    with Dataset(nc, 'r') as ds:
        units = ds.variables['time'].units
        return parse_time_units_string(units, r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', '%Y-%m-%d %H:%M')



def closest_time_index(
        timesteps: list[TimeLike],
        time: TimeLike,
        method: str = 'previous',
        tol: float = 0.001
) -> int:
    """Returns the index of the closest time in the provided timesteps.
    It will try and find any matching time within the given tolerance, otherwise will return the index of the
    previous or next time depending on the method.

    Parameters
    ----------
    timesteps : list[TimeLike]
         List of time-steps as either float or datetime
    time : TimeLike
        Time to find the closest time-step to.
    method: str, optional
        Method to use if no matching time-step is found within the tolerance. Options are 'previous', or 'next'. The
        default is 'previous'.
    tol : float, optional
        Tolerance to use when comparing the time-steps. Default is 0.001.

    Returns
    -------
    int
        Index of the closest time-step.
    """
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
