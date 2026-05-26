from .tef_build_state import TEFBuildState
from .tef_run_state import TEFRunState
from .cf_load_factory import ControlFileLoadMixin
from ..context import Context
from .cf_run_state import ControlFileRunState
from .. import const


class TEF(ControlFileLoadMixin, TEFBuildState):
    """Initialises the TEF class in a build state.

    If the class is initialised with the :code:`fpath` parameter set to ``None``, an empty class will be initialised.

    Parameters
    ----------
    fpath : PathLike, optional
        The path to the control file (str or Path). If set to ``None``, the TEF will be initialised as an
        empty control file.

    **kwargs : optional parameters

        - config : TCFConfig, optional
            This object stores useful information such as variable mappings, the event database,
            current spatial database etc. If set to None, a new TCFConfig object will be created.
        - parent : ControlFile, optional
            Will set the parent of the control file to another control file e.g. for a TGC, the parent
            should be set to the TCF.
        - scope : ScopeList, optional
            A list of scope objects that will be inherited by the control file itself. Not currently used
            but reserved in case this is useful information in the future.
        - log_level : str, optional
            The logging level to use for the control file. Options are 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'.
            Default is 'WARNING'.
        - log_to_file : PathLike, optional
            If set, will log the control file to the given file path. Default is None.
    """
    TUFLOW_TYPE = const.CONTROLFILE.TEF

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: ControlFileRunState | None = None) -> TEFRunState:
        # docstring inherited
        from .tef_run_state import TEFRunState
        ctx = context if context else Context(run_context, config=self.config)
        return TEFRunState(self, ctx, parent)
