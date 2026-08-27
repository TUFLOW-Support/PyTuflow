from pathlib import Path
import typing

from .cf import ControlFileInput, InputRunState
from ..context import Context
from .. import const

if typing.TYPE_CHECKING:
    from ..cf.block import BlockControl
    from ..cf.cf_run_state import ControlFileRunState


class BlockControlInputMixin:

    def block_control(self) -> 'BlockControl':
        try:
            return self.cf[0]
        except IndexError:
            raise IndexError(
                f'{self.__class__.__name__} does not have a loaded control block - this likely means that the control '
                'file was not properly loaded. Check the syntax in the control file.'
                )


class BlockControlInput(ControlFileInput, BlockControlInputMixin):
    """Class for block headers in TUFLOW FV."""
    TUFLOW_TYPE = const.INPUT.BLOCK

    def _load_files(self):
        self._files_loaded = True

    def _load_control_files(self):
        from ..cf.block import BlockControl
        cf = BlockControl(self.parent.fpath, self._command.config, self.parent, self.scope, self.parent.parser, self)
        self.cf.append(cf)

    @property
    def value(self):
        value = []
        for part in self._command.parts():
            if part.is_value_a_number_3():
                value.append(float(part.value))
            elif part.is_value_a_file():
                value.append(Path(part.value_expanded_path))
            else:
                value.append(part.value)
        return tuple(value) if len(value) > 1 else value[0]
        
    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> 'BlockControlInputRunState':
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return BlockControlInputRunState(self, ctx, parent)


class BCBlockControlInput(BlockControlInput):
    """Class for BC block headers in TUFLOW FV."""
    TUFLOW_TYPE = const.INPUT.BC_BLOCK

    def _load_control_files(self):
        from ..cf.block import BCBlockControl
        cf = BCBlockControl(self.parent.fpath, self._command.config, self.parent, self.scope, self.parent.parser, self)
        self.cf.append(cf)
    
    def _load_files(self):
        for cmd in self._command.parts():
            if cmd.is_value_a_file():
                for file in cmd.iter_files():
                    file = Path(file)
                    self._files.append(file)
                    self._file_to_original[file] = cmd.value_expanded_path
                if not self._files:
                    file = Path(cmd.value_expanded_path) if cmd.config.control_file != Path() else Path(cmd.value)
                    self._files = [file]
                    self._file_to_original[file] = file
                    self._has_missing_files = True
        self._rhs_files = self._files.copy()
        self._file_scopes()
        self._files_loaded = True


class GridDefinitionFileBlockInput(BCBlockControlInput):
    TUFLOW_TYPE = const.INPUT.GRID_DEFINITION_FILE_INPUT


class BlockControlInputRunState(InputRunState, BlockControlInputMixin):
    
    def _resolve_scope_in_context(self):
        super()._resolve_scope_in_context()
        for cf in self.bs.cf:
            run_cf = cf.context(context=self.ctx, parent=self.parent)
            run_cf.parent_input = self
            self.cf.append(run_cf)
