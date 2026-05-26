import logging
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from .. import const
from ..tfstrings.patterns import contains_variable
from ..inp.inputs import Inputs
from ..scope import EventScope, ScenarioScope, EventDefineScope
from ..abc.bld_state import BuildState
from ..abc.input import Input
from ..parsers.command import Command
from ..scope_writer import ScopeWriter
from ..scope import Scope, ScopeList
from ..context import Context


if TYPE_CHECKING:
    from ..abc.bld_state import BuildState
    from .inp_run_state import InputRunState
    # noinspection PyUnresolvedReferences
    from ..cf.cf_run_state import ControlFileRunState
    # noinspection PyUnresolvedReferences
    from ..cf.cf_build_state import ControlFileBuildState

logger = logging.getLogger('pytuflow')


class InputBuildState(BuildState, Input):
    """Input class for the 'BuildState' of the model. The build state input contains extra information on the scope,
    of the input (e.g. it may be within a scenario block).

    It also collects all the associated files e.g. input paths can contain variables names so
    :code:`2d_zsh_<<~s1~>>_001.shp` could expand to

    * :code:`2d_zsh_D01_001.shp`
    * :code:`2d_zsh_D02_001.shp`

    if both files exist. It will collect information on the scope of files it finds.

    Parameters
    ----------
    parent : BuildState
        The parent build state object (most likely a ControlFile).
    command : Command
        Command object which unpins the input.
    """
    TUFLOW_TYPE = const.INPUT.INPUT

    def __init__(self, parent: 'ControlFileBuildState', command: Command) -> None:
        super().__init__()
        self.parent: 'ControlFileBuildState' = parent
        self.resolved = '<<' not in str(command.value)
        self.part_count = command.part_count
        self.config = command.config
        self._has_missing_files = False
        self._dirty = False
        self._files = []
        self._files_loaded = False
        self._command = command
        self._has_variable = contains_variable(str(command.command_orig))
        self._file_to_scope = {}
        self._file_to_original = {}
        self._scope = self._init_scope()
        self._load()

    @property
    def lhs(self) -> str:
        return Input.lhs.fget(self)

    @lhs.setter
    def lhs(self, value: str):
        from .get_input_class import get_input_class
        inputs = Inputs()
        inputs.append(self)
        self.record_change(inputs, 'update_command')
        cmd = deepcopy(self._command)
        cmd.value = str(value)
        new_value = '{0} == {1}'.format(value, cmd.value_orig)
        new_value = cmd.re_add_comments(new_value, True)
        cmd = Command(new_value, cmd.config)
        # test
        inp = get_input_class(cmd)(self.parent, cmd)
        # noinspection PyUnreachableCode
        if not isinstance(inp, type(self)):
            logger.error('Cannot change input type. Existing and provided inputs are not the same type')
            raise ValueError('Cannot change input type')
        self.__init__(self.parent, cmd)
        self.dirty = True

    @property
    def rhs(self) -> str:
        return Input.rhs.fget(self)

    @rhs.setter
    def rhs(self, value: str):
        inputs = Inputs()
        inputs.append(self)
        self.record_change(inputs, 'update_value')
        cmd = deepcopy(self._command)
        cmd.value = str(value)
        new_value = '{0} == {1}'.format(cmd.command_orig, cmd.value)
        new_value = cmd.re_add_comments(new_value, True)
        cmd = Command(new_value, cmd.config)
        self.__init__(self.parent, cmd)
        self.dirty = True

    @property
    def comment(self) -> str:
        return Input.comment.fget(self)

    @comment.setter
    def comment(self, value: str):
        inputs = Inputs()
        inputs.append(self)
        self.record_change(inputs, 'update_value')
        cmd = deepcopy(self._command)
        cmd.comment = value
        new_value = cmd.re_add_comments(cmd.original_text, True)
        cmd = Command(new_value, cmd.config)
        self._command = cmd
        self.dirty = True

    @property
    def scope(self) -> ScopeList:
        return BuildState.scope.fget(self)

    @scope.setter
    def scope(self, value: ScopeList | list[Scope] | tuple[Scope, ...] | list[tuple[str, str]] | tuple[tuple[str, str], ...]):
        inputs = Inputs()
        inputs.append(self)
        self.record_change(inputs, 'set_scope')
        if self._command.is_set_variable() and (Scope('Scenario') in value or Scope('Event') in value):
            if self.parent:
                variable_name, _ = self._command.parse_variable()
                self.parent.tcf.remove_variable(variable_name)
        BuildState.scope.fset(self, value)

    @property
    def files(self) -> list[Path]:
        if not self._files_loaded:
            self._load_files()
        return self._files

    @property
    def has_missing_files(self) -> bool:
        if not self._files_loaded:
            self._load_files()
        return self._has_missing_files

    @has_missing_files.setter
    def has_missing_files(self, value: bool):
        self._has_missing_files = value

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: 'ControlFileRunState | None' = None) -> 'InputRunState':
        # docstring inherited
        from .inp_run_state import InputRunState
        ctx = context if context else Context(run_context, config=self.config)
        return InputRunState(self, ctx, parent)

    def write(self, fo: TextIO, scope_writer: ScopeWriter) -> str:
        """Write the object to file. Users probably shouldn't be using this method directly in this class.

        Parameters
        ----------
        fo : TextIO
            Text buffer object to write to.
        scope_writer : ScopeWriter
            Scope writer object that helps convert the input scope to a string (i.e. adds indentation).

        Returns
        -------
        str
            Text written to the file.
        """
        text = self._command.original_text
        if text and text[-1] != '\n':
            text = f'{text}\n'
        text = scope_writer.write(text)
        fo.write(text)
        return text

    def record_change(self, inputs: Inputs, change_type: str) -> None:
        """Not private, but not for users to use directly either.

        Record a change to the input. The record change is passed to the parent control file to record the change to.

        Parameters
        ----------
        inputs : Inputs
            List of inputs that have been changed. Use Inputs class, and not just a list of inputs.
        change_type : str
            Type of change that has occurred. e.g. 'update_value', 'update_command', 'set_scope'
        """
        self.dirty = True
        if self.parent:
            self.parent.record_change(inputs, change_type)

    def figure_out_file_scopes(self, scope_list: ScopeList):
        """no-doc

        Given a list of known scopes (unordered) this function will try and resolve the names
        of the scopes for each file. Only affects scope names that have not been resolved yet and will
        only work if there are existing files to compare to as it will loop through every possible permutation of
        variable names and check if they exist once inserted into the file name.

        This is different from resolving scope through the 'run state' context which uses an ordered list of scopes
        which can simply be used to replace the variable names in the file name.

        Parameters
        ----------
        scope_list : ScopeList
            The list of known scopes.
        """
        for file in self.files:
            self._file_to_scope[str(file)] = Scope.resolve_scope(self.file_scope(file), str(self._file_to_original[file]), str(file), scope_list)

    def _load(self):
        pass

    def _load_files(self):
        pass

    def _init_scope(self) -> ScopeList:
        """Defines the scope of the input based on whether the command is sitting within a Define Block.

        A define block can be any block that starts with

        * :code:`IF  [Scenario | Event]`
        * :code:`ELSE IF  [Scenario | Event]`
        * :code:`ELSE`
        * :code:`DEFINE  [Map Output Zone | ...]`
        * :code:`Start 1D`

        If the input is not within a 'Scenario' or 'Event' block then the scope is also given a 'GLOBAL' scope.

        The list of scopes should be considered 'stacked' or 'nested' i.e. if 2 scenario scopes exist, then
        the input is within a nested if statement. Blocks that use '|' to indicate 'OR' will be within a single
        Scope object (i.e. it won't be a list of scope objects).

        Returns
        -------
        list[Scope]
            List of scope objects.
        """

        if self._command.define_blocks:
            scope = ScopeList()
            for block in self._command.define_blocks:
                s = Scope(block.type, block.name)
                if not scope.contains(s, explode=False):
                    scope.append(s)
                # check if scope already exists - if it does but it is not from an else statement,
                # then replace it with the new scope
                if s.is_else() and not [x for x in scope if x == s][0].is_else():
                    i = scope.index(s)
                    scope[i] = s

            if not [x for x in scope if isinstance(x, EventScope) or isinstance(x, ScenarioScope) or isinstance(x, EventDefineScope)]:
                scope.insert(0, Scope('GLOBAL', ''))
            return scope

        return ScopeList([Scope('GLOBAL', '')])

    def _file_scopes(self) -> None:
        """Called after files are collected in the initialisation of this class and finds the scope of each file. The
        scope of the file is independent of the scope of the input i.e. a file with a 'GLOBAL' scope does not
        reflect that the input itself may be within an 'IF Scenario' block, it indicates that the file does
        not contain any variable names that could potentially be expanded to a different files.

        It will try and resolve the scope of the input by comparing the name to any existing files
        it finds that match the input name pattern.

        e.g.

        Read File == input_file_<<~s~>>.trd

        Existing files:

           - input_file_exg.trd
           - input_file_dev.trd

        File scopes:

           - input_file_exg.trd -> Scope = SCENARIO, name = exg, var = <<~s~>>
           - input_file_dev.trd -> Scope = SCENARIO, name = dev, var = <<~s~>>

        If the scope name can't be resolved, then the scope name will be set to the variable name.

        If there are no variables in the file name, then a 'GLOBAL' scope will be assigned to the file.
        """
        for file in self._files:
            self._file_to_scope[str(file)] = Scope.from_string(str(self._file_to_original[file]), str(file))
