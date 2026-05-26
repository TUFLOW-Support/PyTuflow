import logging
import typing

from .gis import GisInputBase
from .. import const
from ..tfpathlib import TuflowPath

from ..parsers.command import Command

if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from ..cf.cf_build_state import ControlFileBuildState

logger = logging.getLogger('pytuflow')


class GridInput(GisInputBase):
    """Class for handling GRID inputs.

    This class can handle the following scenarios:

    * reading multiple files on a single line: the first file is assumed to be a grid file, the second is
      a vector file.
    """
    TUFLOW_TYPE = const.INPUT.GRID

    def __init__(self, parent: 'ControlFileBuildState', command: Command):
        self.multiplier = 1.
        self.clip_layer = None
        super().__init__(parent, command)

    def _load_files(self):
        for cmd in self._command.parts():
            if cmd.is_value_a_file():
                self._rhs.append(TuflowPath(cmd.value_expanded_path) if cmd.value_expanded_path else TuflowPath(cmd.value))
                at_least_once = False
                for file in cmd.iter_files():
                    at_least_once = True
                    file = TuflowPath(file)
                    self._files.append(file)
                    self._file_to_original[file] = cmd.value_expanded_path
                    if cmd.is_vector_file():
                        if self.clip_layer:
                            self.clip_layer = [self.clip_layer, file] if not isinstance(self.clip_layer, list) else self.clip_layer + [file]
                        else:
                            self.clip_layer = file
                if not at_least_once:
                    self._has_missing_files = True
                    file = TuflowPath(cmd.value_expanded_path) if cmd.config.control_file != TuflowPath() else TuflowPath(cmd.value)
                    self._files.append(file)
                    self._file_to_original[file] = file
            elif cmd.is_value_a_number_3():
                self._rhs.append(cmd.return_number())
                self.multiplier = cmd.return_number()

        self._rhs_files = self._files
        self._file_scopes()
        self._files_loaded = True
