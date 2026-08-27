import typing

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd


class DataFrameWrapper(pd.DataFrame):

    def __init__(self, on_change: typing.Callable[[], None] | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._on_change = on_change if on_change else lambda: None

    def to_df(self) -> pd.DataFrame:
        """Returns a copy of the underlying DataFrame as a DataFrame and not a wrapped class."""
        return super().copy(deep=True)

    def _mark_dirty(self):
        self._on_change()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._mark_dirty()

    @property
    def loc(self):
        class LocIndexer:
            def __init__(self, loc, on_change):
                self._loc = loc
                self._on_change = on_change

            def __getitem__(self, item):
                return self._loc[item]

            def __setitem__(self, item, value):
                self._loc[item] = value
                self._on_change()

            def __getattr__(self, item):
                return getattr(self._loc, item)

        return LocIndexer(pd.DataFrame.loc.fget(self), self._mark_dirty)

    @property
    def iloc(self):
        class IlocIndexer:
            def __init__(self, iloc, on_change):
                self._iloc = iloc
                self._on_change = on_change

            def __getitem__(self, item):
                return self._iloc[item]

            def __setitem__(self, item, value):
                self._iloc[item] = value
                self._on_change()

            def __getattr__(self, item):
                return getattr(self._iloc, item)

        return IlocIndexer(pd.DataFrame.iloc.fget(self), self._mark_dirty)

    @property
    def at(self):
        class AtIndexer:
            def __init__(self, at, on_change):
                self._at = at
                self._on_change = on_change

            def __getitem__(self, item):
                return self._at[item]

            def __setitem__(self, item, value):
                self._at[item] = value
                self._on_change()

            def __getattr__(self, item):
                return getattr(self._at, item)

        return AtIndexer(pd.DataFrame.at.fget(self), self._mark_dirty)

    @property
    def iat(self):
        class IatIndexer:
            def __init__(self, iat, on_change):
                self._iat = iat
                self._on_change = on_change

            def __getitem__(self, item):
                return self._iat[item]

            def __setitem__(self, item, value):
                self._iat[item] = value
                self._on_change()

            def __getattr__(self, item):
                return getattr(self._iat, item)

        return IatIndexer(pd.DataFrame.iat.fget(self), self._mark_dirty)

    def drop(self, *args, **kwargs):
        result = super().drop(*args, **kwargs)
        if result is None:
            self._mark_dirty()
        return result

    def pop(self, *args, **kwargs):
        result = super().pop(*args, **kwargs)
        self._mark_dirty()
        return result

    def set_index(self, *args, **kwargs):
        result = super().set_index(*args, **kwargs)
        if result is None:
            self._mark_dirty()
        return result

    def reset_index(self, *args, **kwargs):
        result = super().reset_index(*args, **kwargs)
        if result is None:
            self._mark_dirty()
        return result

    def update(self, *args, **kwargs):
        result = super().update(*args, **kwargs)
        self._mark_dirty()
        return result
