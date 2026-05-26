import logging
import typing
from pathlib import Path

from .inp_build_state import InputBuildState
from .. import const



logger = logging.getLogger('pytuflow')


class FileInput(InputBuildState):
    """Class for handling inputs that reference files.

    This class will record all associated files and their scopes. This class assumes only one input
    file per line but the input can have variable names in it which expand to multiple files.

    | e.g.
    | ``Read File == input_file_<<~s~>>.trd``
    """
    TUFLOW_TYPE = const.INPUT.FILE

    @property
    def value(self) -> Path:
        # docstring inherited
        self._command.reload_value()
        return Path(self._command.value_expanded_path) if self._command.value_expanded_path else Path(str(self._command.value))

    @value.setter
    def value(self, value: typing.Any):
        raise AttributeError('The "value" attribute is read-only, use "rhs" to set the value of the input.')

    def _load_files(self):
        for file in self._command.iter_files():
            file = Path(file)
            self._files.append(file)
            self._file_to_original[file] = self._command.value_expanded_path
        if not self._files:
            file = Path(self._command.value_expanded_path) if self._command.config.control_file != Path() else Path(self._command.value)
            self._files = [file]
            self._file_to_original[file] = file
            self._has_missing_files = True
        self._rhs_files = self._files.copy()
        self._file_scopes()
