import logging
import typing
from pathlib import Path

from .db import DatabaseInput
from ..parsers.command import Command
from .. import const

if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from ..cf.cf_build_state import ControlFileBuildState

logger = logging.getLogger('pytuflow')


class MatDatabaseInput(DatabaseInput):
    TUFLOW_TYPE = const.INPUT.DB_MAT

    def __init__(self, parent: 'ControlFileBuildState', command: Command):
        self.multiplier = 1.0
        self._rhs = []
        super().__init__(parent, command)

    def _load(self):
        for cmd in self._command.parts():
            if cmd.is_value_a_file():
                self._rhs.append(Path(cmd.value_expanded_path))
                for file in cmd.iter_files():
                    file = Path(file)
                    self._files.append(file)
                    self._file_to_original[file] = cmd.value_expanded_path
                if not self._files:
                    self._has_missing_files = True
                    file = Path(cmd.value_expanded_path) if cmd.config.control_file != Path() else Path(cmd.value)
                    self._files.append(file)
                    self._file_to_original[file] = file
            elif cmd.is_value_a_number_3():
                self._rhs.append(cmd.return_number())
                self.multiplier = cmd.return_number()
            else:
                logger.error(f'Unexpected command part: {cmd} in {self._command}')
                raise ValueError(f'Unexpected command part: {cmd} in {self._command}')

        self._rhs_files = self._files.copy()
        self._load_database_files()
        self._file_scopes()
