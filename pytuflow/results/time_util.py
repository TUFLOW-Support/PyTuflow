from datetime import datetime
from typing import Union

import numpy as np


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
