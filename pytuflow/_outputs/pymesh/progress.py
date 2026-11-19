import typing

import numpy as np


class ProgressTracker:
    """Reports progress of a data extraction to a callback in the form ``callback(done, total)``.

    The unit of work is a single value read from the result file (time steps x vertices/cells x result types).
    Extraction is done in two stages. First a planning pass, which runs the same extraction calls with the data reads
    replaced by dummy data, adds up the number of values that will be read. Then each call is run for real
    and progress is reported as the data is read.
    """
    CHUNK_VALUES = 500_000  # target number of values per read when reads are split up over time steps

    def __init__(self, callback: typing.Callable[[int, int], None], driver):
        self.callback = callback
        self.driver = driver
        self.planning = False
        self.total = 0
        self.done = 0
        self._count = 0
        self._plan = []
        self._next = 0
        self._target = 0

    def plan(self, calls: list[typing.Callable[[], typing.Any]]):
        """Runs each call in planning mode to work out the total, then reports the initial progress."""
        self.planning = True
        self.driver._progress = self
        self.driver.cache.planning = True
        try:
            with np.errstate(all='ignore'):
                for call in calls:
                    self._count = 0
                    call()
                    self._plan.append(self._count)
        finally:
            self.planning = False
            self.driver._progress = None
            self.driver.cache.planning = False
        self.total = sum(self._plan)
        self.done = 0
        self.callback(self.done, self.total)

    def run(self, call: typing.Callable[[], typing.Any]) -> typing.Any:
        """Runs the next planned call. Progress is topped up afterwards for any reads that were skipped (e.g. the
        result was cached)."""
        planned = self._plan[self._next] if self._next < len(self._plan) else 0
        self._next += 1
        self._target = min(self._target + planned, self.total)
        self.driver._progress = self
        try:
            result = call()
        finally:
            self.driver._progress = None
        if self.done < self._target:
            self.done = self._target
            self.callback(self.done, self.total)
        return result

    def advance(self, n: int):
        if self.planning:
            self._count += int(n)
            return
        done = min(self.done + int(n), self.total)
        if done != self.done:
            self.done = done
            self.callback(self.done, self.total)

    def read(self, reader: typing.Callable, shape: tuple[int, ...] | None, data_type: str, index: typing.Any,
             dummy: typing.Callable[[tuple[int, ...]], np.ndarray]) -> np.ndarray:
        """Wraps an extractor read. ``shape`` is the full shape of the variable (``None`` if unknown)."""
        if shape is None:
            a = reader(data_type, index)
            self.advance(a.size)
            return a

        out_shape = np.broadcast_to(np.zeros((), dtype=np.int8), shape)[index].shape
        size = int(np.prod(out_shape))
        if self.planning:
            self.advance(size)
            return dummy(out_shape)

        first = index[0] if isinstance(index, tuple) else index
        if isinstance(first, slice) and (first.step or 1) > 0 and len(out_shape) > 1:
            ids = range(*first.indices(shape[0]))
            n = len(ids)
            per_step = size // n if n else 0
            step = max(1, self.CHUNK_VALUES // max(per_step, 1))
            if n > step:
                rest = tuple(index[1:]) if isinstance(index, tuple) else ()
                parts = []
                for i in range(0, n, step):
                    sub = ids[i:i + step]
                    a = reader(data_type, (slice(sub[0], sub[-1] + 1, first.step), *rest))
                    parts.append(a)
                    self.advance(a.size)
                return np.concatenate(parts, axis=0)

        a = reader(data_type, index)
        self.advance(a.size)
        return a
