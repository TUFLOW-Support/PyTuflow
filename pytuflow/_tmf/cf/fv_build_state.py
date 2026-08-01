import typing
from pathlib import Path
import logging

from .cf_build_state import ControlFileBuildState
from ..settings import FVCConfig
from ..parsers.fvcommand import FVCommand
from ..parsers.non_recursive_basic_parser import get_fv_commands
from ..inp.inp_build_state import InputBuildState
from ..inp.block import BlockControlInput
from ..inp.inputs import Inputs
from ..scope_writer import ScopeWriter
from ..abc.fvc_base import FVBaseMixin
from ..scope import ScopeList


logger = logging.getLogger('pytuflow')


class FVControlFileBuildState(ControlFileBuildState, FVBaseMixin):
    
    def __init__(self, *args, **kwargs):
        #: typing.Iterable[Command]: The parser iterable that is used to load the control file.
        self.parser = None
        super().__init__(*args, **kwargs)
        self.parser = None

    def _parser(self, path: Path, config: FVCConfig) -> typing.Iterator[FVCommand]:
        self.parser = get_fv_commands(path, config)
        return self.parser
    
    # def _load_trd(self, inp: InputBuildState):
    #     original_parser = self.parser
    #     super()._load_trd(inp)
    #     self.parser = original_parser

    @staticmethod
    def _trd_command_lhs() -> str:
        return ''
    
    @staticmethod
    def _generate_initial_config(path: Path) -> FVCConfig:
        return FVCConfig(path)

    @staticmethod
    def _write(fo: typing.TextIO, inputs: Inputs):
        scope_writer = ScopeWriter()
        for inp, scope_writer_ in scope_writer.inputs(fo, inputs):
            inp.write(fo, scope_writer_)
            if isinstance(inp, BlockControlInput):
                block = inp.block_control()
                block.write_block(fo, scope_writer_)
