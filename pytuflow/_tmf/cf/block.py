from pathlib import Path
import typing

from ..abc.input import T_Input

from .. import const
from .cf_build_state import ControlFileBuildState
from .cf_run_state import ControlFileRunState
from ..context import Context
from ..abc.cf import ControlFile
from ..settings import TCFConfig
from ..tmf_types import PathLike
from ..scope import ScopeList, Scope
from ..scope_writer import ScopeWriter
from ..parsers.fvcommand import FVCommand
from ..inp.inputs import Inputs
from ..inp.inp_build_state import InputBuildState
from ..inp.block import BlockControlInput

if typing.TYPE_CHECKING:
    from ..scope import ScopeList


class _BlockScope(Scope):
    """Block scope object. This class is used for writing blocks with the ScopeWriter class and 
    should not be used outside of this context.
    """

    def __new__(cls, type_name: str, name: str = '', var: str = None, else_: bool = False):
        return object.__new__(cls)
    
    def __init__(self, type_name: str, name: str = '', var: str = None, else_: bool = False):
        super().__init__(type_name, name, var, else_)
        self.command = None

    def to_string_start(self) -> str:
        return ''  # start string is an input and is already written

    def to_string_end(self) -> str:
        if self.command is None:
            raise ValueError('Block scope does not have an FV block assigned to it.')
        return self.command.get_fv_block().end_command()

    def supports_else_if(self) -> bool:
        return False
    

class BlockControlRunState(ControlFileRunState):
    pass


class BlockControl(ControlFileBuildState):
    """Control file class for TUFLOW FV blocks.
    
    Unlike other control file classes, this class is not directly associated with a control file command. It also does not
    have a separate file path associated with the control file, as a block is just a collection of inputs within an FV control file.
    """
    TUFLOW_TYPE = const.CONTROLFILE.BLOCK
    
    def __init__(self,
                 path: PathLike = None,
                 config: TCFConfig = None,
                 parent: ControlFile = None,
                 scope: ScopeList = None,
                 parser: typing.Iterator[ControlFileBuildState] = None,
                 parent_input: T_Input = None,
                 **kwargs):
        super().__init__(None, config, parent, scope, **kwargs)
        self._fpath = Path(path) if path is not None else None
        self.parser = parser
        self.parent_input = parent_input
        if parser:
            self._load_block(parser)

    def __repr__(self):
        if self.parent_input is None:
            return f'<{self.__class__.__name__}>'
        return f'<{self.__class__.__name__}> {str(self)}'
    
    def __str__(self):
        if self.parent_input is None:
            return ''
        return str(self.parent_input)

    def _load_block(self, parser: typing.Iterator[ControlFileBuildState]):
        while True:
            try:
                cmd = next(parser)
                if cmd.is_end_fv_block():
                    return
                self._append_input(cmd, None, None)
            except StopIteration:
                # exception should be thrown by the parser before it gets here
                raise ValueError('Unexpected end of block control parser - did you forget to include an "END" command for the block?')
            
    def write_block(self, fo: typing.TextIO, scope_writer_: ScopeWriter, level: int = 0):
        block_scope = _BlockScope('Block')
        block_scope.command = self.parent_input.command()
        inputs, _ = self._get_trd_inputs(self)
        if inputs:
            for inp in inputs.inputs(include_hidden=True):
                inp.scope.insert(0, block_scope)
        else:  # add an empty command, otherwise the scope writer won't close the block
            cmd = FVCommand('', self.config, self.fpath)
            inp = InputBuildState(self, cmd)
            inp.scope.append(block_scope)
            inputs.append(inp)
        
        for inp, scope_writer_1 in scope_writer_.inputs(fo, inputs):
            inp.write(fo, scope_writer_1)
            if isinstance(inp, BlockControlInput):
                sub_level = level + 1
                scope_writer_new = ScopeWriter(start_indentation_level=sub_level)
                block = inp.block_control()
                block.write_block(fo, scope_writer_new, sub_level)
        
        for inp in inputs.inputs(include_hidden=True):
            inp.scope.pop(0)

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: ControlFileRunState | None = None) -> BlockControlRunState:
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return BlockControlRunState(self, ctx, parent)
    


class BCBlockControlRunState(BlockControlRunState):
    pass


class BCBlockControl(BlockControl):
    """Control file class for TUFLOW FV BC blocks."""
    TUFLOW_TYPE = const.CONTROLFILE.BC_BLOCK

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: ControlFileRunState | None = None) -> BCBlockControlRunState:
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return BCBlockControlRunState(self, ctx, parent)
        