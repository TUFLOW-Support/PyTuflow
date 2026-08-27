from .run_state import RunState
from .cf import ControlFile
from ..cf.cf_run_state import ControlFileRunState
from ..settings import TCFConfig
from ..context import Context
from ..scope import ScopeList, Scope


class BuildState:
    """Abstract model class containing information when the model is in 'Build State' or 'Configuration State'.

    i.e. inputs from all scenarios/events are included and variable names haven't been resolved yet.
    """

    #: str: A string identifying the PyTUFLOW object type.
    TUFLOW_TYPE: str = 'TuflowBuildState'

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._scope: ScopeList = ScopeList()
        self._dirty: bool = False
        #: BuildState | None: Parent object, if any.
        self.parent: BuildState | None = None
        #: TCFConfig: Configuration settings for the TUFLOW model.
        self.config = TCFConfig()

    @property
    def scope(self) -> ScopeList:
        """ScopeList: List of scopes associated with the object."""
        return self._scope

    @scope.setter
    def scope(self,
              value: ScopeList | list[Scope] | tuple[Scope, ...] | list[tuple[str, str]] | tuple[tuple[str, str], ...]):
        if isinstance(value, ScopeList):
            self._scope = value
            return
        # noinspection PyUnreachableCode
        if not isinstance(value, (list, tuple)):
            raise TypeError(f'Scope must be a ScopeList, list, or tuple, not {type(value)}')
        if value and isinstance(value[0], Scope):
            self._scope = ScopeList(value)
            return
        self._scope = ScopeList([Scope(*x) for x in value])

    @property
    def dirty(self) -> bool:
        """bool: Whether the object has been changed since it was last written to file."""
        return self._dirty

    @dirty.setter
    def dirty(self, value: bool):
        self._dirty = value
        if self.parent:
            if value:  # is True
                self.parent.dirty = value
            elif isinstance(self.parent, ControlFile):  # other inputs might be dirty, so need to check before setting it to clean
                if not self.parent.find_input(attrs='dirty'):
                    self.parent.dirty = value

    def figure_out_file_scopes(self, scope_list: ScopeList) -> None:
        """no-doc

        Resolve unknown scopes by passing in a list of known scopes.

        Unknown scopes are when <<~s~>>, <<~e~>>, <<variable>>, or ~event~ are encountered in file names and they
        cannot be resolved due to ambiguity, missing files, or missing information.

        This is not the same as using context to resolve scopes into a RunState. The method populates scope information
        where any is missing where variable names have been used in file names.

        Parameters
        ----------
        scope_list : ScopeList
            List of known scopes to resolve unknown scopes.
        """
        pass

    def add_variable(self, variable_name: str, variable_value: str):
        """no-doc

        Adds a variable to the TCFConfig settings object. This change is propagated to children.
        """
        self.config.variables[variable_name] = variable_value

    def remove_variable(self, variable_name: str):
        """no-doc

        Removes a variable from the TCFConfig settings object. This change is propagated to children.
        """
        if variable_name in self.config.variables:
            del self.config.variables[variable_name]

    def write(self, *args, **kwargs) -> str:
        """Write the object to file."""
        pass

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: ControlFileRunState | None = None) -> RunState:
        """Create a :class:`RunState` version of this object. The context will also be propagated to all
        child objects.

        The RunState instance will resolve all scenario and event scopes to a single event.
        For example, a command encompassed in "If Scenario" / "End if", will be either included
        or removed based on the context provided.

        Parameters
        ----------
        run_context : str | dict[str, str], optional
            A string in the format of the TUFLOW command line argument ``"-s1 EXG -e1 100yr"``, or a dictionary
            with the same information using keys ``{'e1': '100yr', 's1': 'EXG'}``.
        context : Context, optional
            A Context instance to use instead of creating a new one. If not provided, a new Context will be created
            using the `run_context` string or dictionary.
        parent : ControlFileRunState, optional
            The parent RunState instance. This will be passed to the created RunState instance.

        Returns
        -------
        RunState
            Object with the context passed in.

        Examples
        --------
        >>> cf = ... # Assume cf is an instance of a ControlFileBuildState or similar
        >>> run_state = cf.context('-s1 EXG -e1 100yr')
        """
        raise NotImplementedError
