import abc
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np

from ..._pytuflow_types import TimeLike, PathLike


class LongProfileDataExtractor(abc.ABC):

    def __init__(self, fpath: PathLike, **kwargs):
        self.path = Path(fpath)
        self.name = ''
        self.labels = []
        self.units = 'h'
        self.reference_time = datetime(1990, 1, 1, tzinfo=timezone.utc)
        self.has_reference_time = False

    def __repr__(self):
        return f'{self.__class__.__name__}({self.path.name})'

    def is_valid(self) -> bool:
        return False

    def is_empty(self) -> bool:
        return not bool(self.labels)

    @abc.abstractmethod
    def number_of_points(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def get_chainages(self, label: str) -> list[float]:
        raise NotImplementedError

    @abc.abstractmethod
    def get_section(self, label: str, time: TimeLike) -> np.ndarray:
        raise NotImplementedError

    @abc.abstractmethod
    def get_time_series(self, label: str, point_ind: int, time_fmt: str) -> np.ndarray:
        raise NotImplementedError

    @abc.abstractmethod
    def get_time_series_data_raw(self, label: str) -> np.ndarray:
        raise NotImplementedError

    @abc.abstractmethod
    def _get_timesteps(self) -> np.ndarray:
        raise NotImplementedError

    def get_timesteps(self, fmt: str) -> np.ndarray:
        """Get the timesteps from the netCDF file.

        Parameters
        ----------
        fmt : str
            Format of the timesteps. Options are 'relative', 'absolute' (or 'datetime' can also be used as an alias).

        Returns
        -------
        np.ndarray
            Array of timesteps.
        """
        if fmt == 'relative':
            return self._get_relative_timesteps()
        else:  # absolute or datetime
            return self._get_absolute_timesteps()

    def _get_closest_timestep_index(self, time: TimeLike, tol: float = 0.01) -> int:
        if isinstance(time, datetime):
            time = (time - self.reference_time).total_seconds() / 3600
        timesteps = self._get_relative_timesteps()
        a = np.isclose(time, timesteps, atol=tol, rtol=0.)
        if a[a].any():
            # noinspection PyTypeChecker
            return np.where(a)[0][0]
        else:
            if time < timesteps.min():
                return 0
            elif time > timesteps.max():
                return timesteps.size - 1
            i = np.argmin(np.absolute(timesteps - time))
            if timesteps[i] < time:
                return i
            return max(i - 1, 0)

    def _get_relative_timesteps(self) -> np.ndarray:
        # return in hours
        if self.units == 'd':
            return self._get_timesteps() * 24
        elif self.units == 's':
            return self._get_timesteps() / 3600
        return self._get_timesteps()

    def _get_absolute_timesteps(self) -> np.ndarray:
        return np.array([self.reference_time + timedelta(hours=float(ts)) for ts in self._get_relative_timesteps()])
