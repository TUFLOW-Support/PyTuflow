from typing import TYPE_CHECKING

from .cf import ControlFile
from ..scope import ScopeList, Scope
from ..context import Context

if TYPE_CHECKING:
    from .bld_state import BuildState


class RunState:
    """Abstract model class containing information when the model is in 'Run State'.

    i.e. context information on a given run has been provided (if any) and only inputs within the scope of
    the run are included also variable names have been resolved.

    This class should only be generated from an instance of a BuildState class using the 'context' method.
    """

    def __init__(self, build_state: 'BuildState', context: Context, parent: ControlFile):
        """
        Parameters
        ----------
        build_state : BuildState
            The BuildState object that the RunState object is based on.
        context : Context
            The context object that the RunState object is based on.
        parent : ControlFile
            The parent control file.
        """
        super().__init__()
        #: ControlFile: the parent control file
        self.parent = parent
        #: BuildState: the BuildState object that the RunState object is based on.
        self.bs = build_state
        #: Context: the context object that the RunState object is based on.
        self.ctx = context

        self._name = build_state.__class__.__name__

    def _resolve_scope_in_context(self):
        """Method called after all initialisation and resolves all inputs to remove variable names and unused inputs."""

    # noinspection PyPep8Naming
    @property
    def TUFLOW_TYPE(self) -> str:
        """Return the TUFLOW type of the input."""
        return self.bs.TUFLOW_TYPE

    @property
    def scope(self) -> ScopeList:
        """ScopeList: List of scopes associated with the object."""
        if hasattr(self, 'bs') and hasattr(self.bs, 'scope'):
            return self._cull_scope_list(self.bs.scope)
        return ScopeList()

    def context(self) -> ScopeList:
        """Returns the ScopeList that makes up the objects Context for the given RunState Object.

        Returns
        -------
        ScopeList
            The ScopeList for the given RunState Object.
        """
        scope_list = ScopeList()
        for scope in self.ctx.available_scopes:
            scopes = scope.explode()
            for scope2 in scopes:
                if scope2 == Scope('EVENT') and self.ctx.events_loaded:
                    if isinstance(scope2.name, list):
                        name = scope2.name[0]
                    else:
                        name = scope2.name
                    event = self.ctx.event_db.get(name)
                    if event is None:
                        scope_list.append(scope2)
                    else:
                        scope3 = Scope('EVENT', event.rhs, var=event.variable)
                        scope_list.append(scope3)
                if scope2 == Scope('EVENT DEFINE'):
                    pass
                else:
                    scope_list.append(scope2)

        return scope_list

    @staticmethod
    def _cull_scope_list(scope_list: ScopeList) -> ScopeList:
        """Cull the scope list to remove resolved scopes.
        E.g. Scenario/Event/Event Variable scope should all be resolved.
        """
        # assume all resolvable scopes are resolved!
        ret_scope_list = ScopeList([x for x in scope_list if not x.resolvable()])
        return ret_scope_list
