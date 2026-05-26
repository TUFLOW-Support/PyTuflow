import itertools
import typing

from .misc.case_insensitive_dict import CaseInsDict
from .misc.append_dict import AppendDict


class EventDatabase(CaseInsDict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inputs = []

    def __setitem__(self, key, value):
        if key in self:
            self[key].update(value)
        else:
            super().__setitem__(key, value)

    def __bool__(self):
        return bool(self.keys()) or bool(self.inputs)

    def update(self, m, /, **kwargs):
        """Update the event database with another mapping or keyword arguments."""
        for key, value in m.items():
            self[key] = value
        for key, value in kwargs.items():
            self[key] = value
        if hasattr(m, 'inputs'):
            self.inputs.extend(m.inputs)
        if hasattr(kwargs, 'inputs'):
            self.inputs.extend(kwargs.inputs)
        return self

    def copy(self):
        """Return a shallow copy of the EventDatabase."""
        new_db = EventDatabase()
        for key, value in self.items():
            new_db[key] = value.copy() if isinstance(value, dict) else value
        return new_db

    def event_variables(self) -> AppendDict:
        d = AppendDict()
        for key, val in self.items():
            for k, v in val.items():
                d[k] = v
        return d

    def event_combinations(self) -> typing.Generator[tuple[tuple[str, str]], None, None]:
        combs = []
        for event_var, event_vals in self.event_variables().items():
            if not isinstance(event_vals, list):
                event_vals = [event_vals]
            combs.append(list(itertools.product([event_var], event_vals)))
        combs = list(itertools.product(*combs))
        yield from combs
