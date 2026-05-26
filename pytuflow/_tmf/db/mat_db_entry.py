import typing
from pathlib import Path

from .db_entry import DBEntry
from ..settings import TCFConfig
from ..scope import Scope
from ..parsers.db_line import DBLine

if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from ..abc.db import Database


class MatDBEntry(DBEntry):
    SOURCE_INDEX = 1

    def __init__(self, index: typing.Hashable, values: list[str | int | float], config: TCFConfig, parent: 'Database'):
        super().__init__(index, values, config, parent)
        source_part = [x for x in self.line.parts()][self.SOURCE_INDEX]
        self.uses_source_file = source_part and not source_part.is_number(source_part.value, source_part.part_index, source_part.part_count)

    def is_list(self) -> bool:
        source_part = [x for x in self.line.parts()][self.SOURCE_INDEX]
        return '"' in str(source_part.value) and ',' in str(source_part.value)

    def _load_files(self):
        # find files
        if not self.uses_source_file:
            return
        source_part = [x for x in self.line.parts()][self.SOURCE_INDEX]
        self._files = [Path(x) for x in source_part.iter_files()]
        for file in self._files:
            self._file_to_scope[str(file)] = Scope.from_string(source_part.value_expanded_path, str(file))

        self._check_missing_files(source_part)
        self._files_loaded = True

    def _check_missing_files(self, source_part: DBLine) -> None:
        if source_part.value and not self._files:
            self._files = [source_part.value]
            self._file_to_scope[source_part.value] = Scope.from_string(source_part.value, source_part.value)
            self._has_missing_files = True
