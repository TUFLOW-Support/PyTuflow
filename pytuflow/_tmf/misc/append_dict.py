class AppendDict(dict):
    """Dictionary that appends values to a key if it already exists. Items are stored as lists."""

    def __setitem__(self, key, value):
        if key in self:
            if isinstance(self[key], list):
                self[key].append(value)
            else:
                self[key] = [self[key], value]
        else:
            if not isinstance(value, list):
                value = [value]
            super().__setitem__(key, value)
