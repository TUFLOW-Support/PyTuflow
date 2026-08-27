import typing
from pathlib import Path

from ..parsers.db_line import DBLine
from ..settings import TCFConfig
from ..scope import Scope, ScopeList
from ..tmf_types import PathLike

if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from ..abc.db import Database


class DBEntry:

    def __init__(self, index: typing.Hashable, values: list[str | int | float], config: TCFConfig, parent: 'Database'):
        self._index = index
        self._values = values
        self._string = f'{index},' + ','.join(f'"{v}"' if ',' in str(v) else str(v) for v in values)
        self._file_to_scope = {}
        self._files = []
        self._files_loaded = False
        self._is_list = False  # whether the value is a list of values e.g. "d1, n1, d2, n2"
        self._has_missing_files = False
        self._missing_files_checked = False

        self.config = config if config is not None else TCFConfig()
        self.parent = parent
        self.line = DBLine(self._string, config, parent.fpath)
        self.uses_source_file = False
        self.string = ','.join(str(x.value) for x in self.line.parts())

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} index={self._index} values={self._values}>'

    def __getitem__(self, item: int) -> DBLine:
        for i, part in enumerate(self.line.parts()):
            if i == item:
                return part
        raise IndexError(f'Index out of range: {item}')

    def __len__(self) -> int:
        return self.line.part_count

    @property
    def files(self) -> list[Path]:
        if not self._files_loaded:
            self._load_files()
        return self._files

    @property
    def has_missing_files(self) -> bool:
        if not self._files_loaded:
            self._load_files()
        if not self._missing_files_checked:  # resolving file paths is expensive so only do it once and only if needed
            self._missing_files_checked = True
            if not self._has_missing_files:
                for file in self._files:
                    if not file.exists():
                        self._has_missing_files = True
                        break
        return self._has_missing_files

    # noinspection PyMethodMayBeStatic
    def header_labels(self) -> list[str]:
        """Can be used if the header columns are dynamic (not like bc_dbase which has a fixed header)

        e.g. cross-section headers can be defined in the attribute table or be left blank and can be different
        per cross-section.
        """
        return []

    def file_scope(self, file: PathLike) -> ScopeList:
        """Public function that will return the scope of a given file.

        Parameters
        ----------
        file : PathLike
            The file to get the scope of.

        Returns
        -------
        ScopeList
            The scope of the file.
        """
        return self._file_to_scope.get(str(file), ScopeList([Scope('GLOBAL', '')]))

    def _load_files(self):
        pass
