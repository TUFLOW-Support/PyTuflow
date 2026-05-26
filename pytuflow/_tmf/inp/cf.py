import logging
import typing

from .file import FileInput
from .inp_run_state import InputRunState
from ..context import Context
from ..abc.bld_state import BuildState
from .. import const



if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from ..cf.cf_run_state import ControlFileRunState

logger = logging.getLogger('pytuflow')


class ControlFileInputRunState(InputRunState):

    def _resolve_scope_in_context(self):
        super()._resolve_scope_in_context()
        for cf in self.bs.cf:
            if cf.fpath.resolve() == self.value.resolve():
                run_cf = cf.context(context=self.ctx, parent=self.parent)
                self.cf.append(run_cf)


class ControlFileInput(FileInput):
    """
    Class for control files.Includes TRD, TEF

    | e.g.
    | :code:`Geometry Control File == geometry_control_file.tgc`
    """
    TUFLOW_TYPE = const.INPUT.CF

    @property
    def dirty(self) -> bool:
        return self._dirty or any(cf.dirty for cf in self.cf)

    @dirty.setter
    def dirty(self, value: bool):
        BuildState.dirty.fset(self, value)

    def _load(self):
        super()._load()
        self._load_control_files()

    def _load_files(self):
        super()._load_files()
        self._files_loaded = True

    def _load_control_files(self):
        from ..cf.get_control_file_class import get_control_file_class
        for file in self.files:
            try:
                cf = get_control_file_class(file)(file, self._command.config, self.parent)
                self.cf.append(cf)
            except Exception as e:
                logger.error(f'Error loading control file {file}. Command: {self._command}. Error: {e}')

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> ControlFileInputRunState:
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return ControlFileInputRunState(self, ctx, parent)
