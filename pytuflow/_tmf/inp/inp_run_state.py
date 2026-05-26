import logging
import typing
from pathlib import Path

from ..abc.run_state import RunState
from ..abc.input import Input
from ..tmf_types import PathLike
from ..parsers.command import Command
from ..scope import ScopeList
from ..context import Context



if typing.TYPE_CHECKING:
    from .inp_build_state import InputBuildState
    from ..cf.cf_run_state import ControlFileRunState

logger = logging.getLogger('pytuflow')


class InputRunState(RunState, Input):
    """Class for storing the run state of an input.

    This class should not be instantiated directly, but rather it should be created from an instance
    of a BuildState class using the `context` method of the BuildState class.

    Parameters
    ----------
    build_state : InputBuildState
        The BuildState object that the RunState object is based on.
    context : Context
        The context object that the RunState object is based on.
    parent : ControlFileRunState
        The parent control file run state.
    """

    def __init__(self, build_state: 'InputBuildState', context: Context, parent: 'ControlFileRunState'):
        super().__init__(build_state, context, parent)
        #: InputBuildState: the BuildState object that the RunState object is based on.
        self.bs = build_state
        #: ControlFileRunState: the parent control file
        self.parent = parent
        #: ControlFileRunState | DatabaseRunState: the loaded run state if the input is a control file or database.
        self.cf = []
        #: UUID4: A unique identifier for the input, set to the same as the BuildState UUID.
        self.uuid = self.bs.uuid
        #: Path | None: The .trd file that this input is from.
        self.trd = self.bs.trd
        #: TCFConfig: Configuration object for the input.
        self.config = self.bs.config
        #: int: The number of parts in the input command.
        self.part_count = 1

        self._rs: 'InputBuildState'

        self._resolve_scope_in_context()

    def __repr__(self):
        """Input name is BuildState type + Context."""
        if hasattr(self, 'lhs') and hasattr(self, 'rhs'):
            return '<{0}Context> {1} == {2}'.format(self._name, self.lhs, self.rhs)
        elif hasattr(self, 'lhs'):
            return '<{0}Context> {1}'.format(self._name, self.lhs)
        return '<{0}Context>'.format(self._name)

    @property
    def value(self) -> str | float | int | Path | tuple[str | float | int, ...]:
        return self._rs.value

    @property
    def files(self) -> list[Path]:
        return self._rs.files if self._rs else []

    @property
    def has_missing_files(self) -> bool:
        return self._rs.has_missing_files if self._rs else False

    @property
    def line_number(self) -> int:
        return self.bs.line_number

    def file_scope(self, file: PathLike) -> ScopeList:
        return self._rs.file_scope(file)

    def _resolve_scope_in_context(self):
        """Method called after all initialisation and resolves all inputs to remove variable names and unused inputs.
        Also resolve any numeric and file references in command value.

        e.g.
        File references can be using variable names (either user defined or scenario/event)
        or
        Some commands can contain numeric values that have been replaced by a variable name
        even GIS inputs can contain numeric values:
            - Read GIS Mat == 2d_mat.shp | 3  ! 3 is the column index to use
            - Read GIS Zpts Conveyance == <gis file> | <float> | <grid>  ! second value is the numeric value

        GIS inputs also may have file references in the attribute table - these are resolved lazily (when required).
        """
        from .get_input_class import get_input_class
        cmd_txt = f'{self.bs.lhs} == {self.ctx.translate(self.bs.rhs)}' if self.bs.rhs else self.bs.lhs
        self._command = Command(cmd_txt, self.config)
        self._command.config.variables = self.ctx.translate
        self._rs = get_input_class(self._command)(self.bs.parent, self._command)  # Input representing the RunState
        # check all variable names in file have been resolved
        if [x for x in self.files if not self.ctx.is_resolved(x)]:
            raise ValueError('Input has not been completely resolved - {0}'.format(self.rhs))
