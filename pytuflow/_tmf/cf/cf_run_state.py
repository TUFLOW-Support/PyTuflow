import logging
import re
import typing
from functools import cache

from ..inp.inputs import Inputs
from ..inp.inp_run_state import InputRunState
from ..abc.cf import ControlFile
from ..abc.run_state import RunState
from ..context import Context



if typing.TYPE_CHECKING:
    from .cf_build_state import ControlFileBuildState

logger = logging.getLogger('pytuflow')


@cache
def _batch_append_context_methods() -> dict[type, object]:
    """Identify original built-in input evaluators for conservative fragment reuse.

    Require known function identities so an extension cannot bypass its evaluator.
    """
    from ..inp import block, cf, comment, db, file, folder, gis, grid
    from ..inp import inp_build_state, mat, setting, time_inp, tin, trd

    plain_input_types = (
        inp_build_state.InputBuildState, setting.SettingInput,
        comment.CommentInput, file.FileInput, folder.FolderInput,
        grid.GridInput, time_inp.TimeInput, tin.TinInput, trd.TuflowReadFileInput,
    )
    return {
        **{input_type: inp_build_state._INPUT_BUILD_CONTEXT for input_type in plain_input_types},
        cf.ControlFileInput: cf._CONTROL_FILE_INPUT_CONTEXT,
        db.DatabaseInput: db._DATABASE_INPUT_CONTEXT,
        mat.MatDatabaseInput: db._DATABASE_INPUT_CONTEXT,
        gis.GisInput: gis._GIS_INPUT_CONTEXT,
        block.BlockControlInput: block._BLOCK_CONTROL_INPUT_CONTEXT,
        block.BCBlockControlInput: block._BLOCK_CONTROL_INPUT_CONTEXT,
        block.GridDefinitionFileBlockInput: block._BLOCK_CONTROL_INPUT_CONTEXT,
    }


def prepare_run_context(build_state: typing.Any, context: typing.Any) -> None:
    """Apply the existing model defaults and scoped variables once per context."""
    # if context is empty, look for model events / scenario commands in file
    if context.is_empty():
        d = {}
        model_scenarios = build_state.root_cf.find_input(lhs='model scenario')
        for s in reversed(model_scenarios):
            d.update({'s{0}'.format(i+1): v for i, v in enumerate(re.split(r'[\t\s|,]+', s.rhs))})
            break
        model_events = build_state.root_cf.find_input(lhs='model event')
        for e in reversed(model_events):
            d.update({'e{0}'.format(i+1): v for i, v in enumerate(re.split(r'[\t\s|,]+', e.rhs))})
            break
        context.load_context_from_dict(d)

    # try and resolve variables
    if not context.var_loaded:
        # Batch dependency collection precomputes the immutable list of
        # variable declarations once per parsed TCF. Each run still
        # independently evaluates scopes and the active variable values.
        compiled_assignments = getattr(context, '_batch_variable_assignments', None)
        var_map = {}
        if compiled_assignments is not None:
            for var_input, (var_name, var_val) in compiled_assignments:
                if context.in_context_by_scope(var_input.scope):
                    var_map[var_name] = var_val
        else:
            for var_input in build_state.find_input(lhs='set variable', recursive=True):
                if context.in_context_by_scope(var_input.scope):
                    var_name, var_val = var_input.command().parse_variable()
                    var_map[var_name] = var_val
        context.load_variables(var_map)



class ControlFileRunState(RunState, ControlFile):
    """Class for storing the run state of a control file.

    This class should not be instantiated directly, but rather it should be created from an instance
    of a BuildState class using the `context` method of the BuildState class.

    Parameters
    ----------
    build_state : ControlFileBuildState
        The BuildState object that the RunState object is based on.
    context : Context
        The context object that the RunState object is based on.
    parent : ControlFileRunState
        The parent control file run state.
    """
    def __init__(self, build_state: 'ControlFileBuildState', context: Context, parent: 'ControlFileRunState'):
        super().__init__(build_state, context, parent)
        #: ControlFileBuildState: the BuildState object that the RunState object is based on.
        self.bs = build_state
        #: ControlFileRunState: the parent control file
        self.parent = parent
        #: TuflowPath: the path to the control file
        self.fpath = self.bs.fpath
        #: TCFConfig: the configuration settings for the model.
        self.config = self.bs.config
        #: Inputs: list of inputs and comments in the control file
        self.inputs = Inputs[InputRunState]()
        #: bool: whether the control file has been loaded from disk or not.
        self.loaded = self.bs.loaded

        self._inputs = self.bs.inputs

        self._resolve_scope_in_context()

    def __str__(self):
        if self.fpath:
            if self.loaded:
                return self.fpath.name
            else:
                return f'{self.fpath.name} (not found)'
        return 'Empty Control File'

    def __repr__(self):
        return '<{0}Context> {1}'.format(self._name, str(self))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def _resolve_scope_in_context(self) -> None:
        prepare_run_context(self.bs, self.ctx)

        source_inputs = (
            self.bs._dependency_inputs()
            if getattr(self.ctx, "file_resolution", "eager") == "deferred"
            else self._inputs
        )
        for inp in source_inputs:
            if not self.ctx.in_context_by_scope(inp.scope):
                continue

            if inp.lhs.upper() == 'PAUSE':
                raise ValueError('Pause command encountered: {0}'.format(inp.rhs))

            input_run_state = inp.context(context=self.ctx, parent=self)
            self.inputs.append(input_run_state)
