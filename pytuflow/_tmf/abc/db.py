import typing
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    from ..stubs import pandas as pd

from .t_cf import ControlBase
from ..misc.case_insensitive_dict import CaseInsDictOrdered
from ..misc.dataframe_wrapper import DataFrameWrapper
from ..db.db_entry import DBEntry


class Database(ControlBase):
    """Abstract base class for database objects e.g. bc_dbase, materials, soil etc."""

    def __init__(self, *args, **kwargs):
        #: OrderedDict: Ordered dictionary containing the database entries.
        self.entries = CaseInsDictOrdered()
        #: BuildState | None: Parent object, if any.
        self.parent = None
        self._fpath = Path()
        self._df = pd.DataFrame()
        self._df_wrapped = DataFrameWrapper(data=self._df.copy())

    def __getitem__(self, item: str | int) -> DBEntry:
        if str(item) in self.entries:
            return self.entries[item]
        raise KeyError(f"'{item}' not found in database.")

    def __contains__(self, item: str | int):
        return item in self.entries

    @property
    def tcf(self):
        #: ControlFile: The parent TCF control file object
        if not self.parent:
            return self
        else:
            tcf = self.parent
            while tcf.parent:
                tcf = tcf.parent
            return tcf

    @property
    def df(self) -> pd.DataFrame:
        return self._df_wrapped

    @property
    def fpath(self) -> Path:
        return self._fpath

    @fpath.setter
    def fpath(self, value: Path):
        self._fpath = value

    def items(self) -> typing.Generator[tuple[str, DBEntry], None, None]:
        """Returns an iterator over the (key, value) pairs in the database."""
        yield from self.entries.items()

    def value(self, item: str | int) -> typing.Any:
        """Returns the value of the given item from the database.

        Parameters
        ----------
        item : str | int
            The item to get the value of.

        Returns
        -------
        Any
            The value of the item.
        """
        pass
