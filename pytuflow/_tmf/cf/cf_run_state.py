import logging
import re
import typing

from ..inp.inputs import Inputs
from ..inp.inp_run_state import InputRunState
from ..abc.cf import ControlFile
from ..abc.run_state import RunState
from ..context import Context



if typing.TYPE_CHECKING:
    from .cf_build_state import ControlFileBuildState

logger = logging.getLogger('pytuflow')


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
        # if context is empty, look for model events / scenario commands in file
        if self.ctx.is_empty():
            d = {}
            model_scenarios = self.bs.tcf.find_input(lhs='model scenario')
            for s in reversed(model_scenarios):
                d.update({'s{0}'.format(i+1): v for i, v in enumerate(re.split(r'[\t\s|,]+', s.rhs))})
                break
            model_events = self.bs.tcf.find_input(lhs='model event')
            for e in reversed(model_events):
                d.update({'e{0}'.format(i+1): v for i, v in enumerate(re.split(r'[\t\s|,]+', e.rhs))})
                break
            self.ctx.load_context_from_dict(d)

        # try and resolve variables
        if not self.ctx.var_loaded:
            var_inputs = self.bs.find_input(lhs='set variable', recursive=True)
            var_map = {}
            for var_input in var_inputs:
                if self.ctx.in_context_by_scope(var_input.scope):
                    var_name, var_val = var_input.command().parse_variable()
                    var_map[var_name] = var_val
            self.ctx.load_variables(var_map)

        for inp in self._inputs:
            if not self.ctx.in_context_by_scope(inp.scope):
                continue

            if inp.lhs.upper() == 'PAUSE':
                raise ValueError('Pause command encountered: {0}'.format(inp.rhs))

            input_run_state = inp.context(context=self.ctx, parent=self)
            self.inputs.append(input_run_state)
