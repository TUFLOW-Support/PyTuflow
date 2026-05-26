from typing import OrderedDict


class CaseInsDict(dict):
    """Case insensitive dictionary."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._key_lower = {str(k).lower(): k for k in self.keys()}

    def __getitem__(self, key):
        return super().__getitem__(self._key_lower[str(key).lower()])

    def __contains__(self, item):
        return str(item).lower() in self._key_lower

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._key_lower[str(key).lower()] = key

    def __deepcopy__(self, memo):
        from copy import deepcopy
        new_dict = self.__class__()
        for key, value in self.items():
            new_key = deepcopy(key, memo)
            new_value = deepcopy(value, memo)
            new_dict[new_key] = new_value
        return new_dict

    def get(self, key, default=None):
        return super().get(self._key_lower.get(str(key).lower()), default)

    def clear(self):
        super().clear()
        self._key_lower.clear()


class CaseInsDictOrdered(CaseInsDict, OrderedDict):
    """Ordered case-insensitive dictionary."""
    pass
