import re

from .cf_load_factory import ControlFileLoadMixin
from .cf_run_state import ControlFileRunState
from .fv_build_state import FVControlFileBuildState
from ..context import Context
from ..parsers.fvcommand import Command, FVSedCommand
from .. import const


class FVSedMixin:

    def sediment_fractions(self) -> list[str]:
        """Returns a unique list of sediment groups/fractions.
        
        Returns
        -------
        set[str] : 
            A set of unique sediment group names. If no sediment groups are found, an empty set is returned.
        """
        return list(self._group_names(lhs='fraction').keys())


class FVSed(ControlFileLoadMixin, FVControlFileBuildState, FVSedMixin):
    """Initialises the FV Sediment Transport Control File class in a build state.

    If the class is initialised with the :code:`fpath` parameter set to ``None``, an empty class will be initialised.

    Parameters
    ----------
    fpath : PathLike, optional
        The path to the control file (str or Path). If set to ``None``, the FVSed will be initialised as an
        empty control file.

    **kwargs : optional parameters

        - config : FVCConfig, optional
            This object stores useful information such as variable mappings, the event database,
            current spatial database etc. If set to None, a new FVCConfig object will be created.
        - parent : ControlFile, optional
            Will set the parent of the control file to another control file e.g. for a TGC, the parent
            should be set to the FVC.
        - scope : ScopeList, optional
            A list of scope objects that will be inherited by the control file itself. Not currently used
            but reserved in case this is useful information in the future.
        - log_level : str, optional
            The logging level to use for the control file. Options are 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'.
            Default is 'WARNING'.
        - log_to_file : PathLike, optional
            If set, will log the control file to the given file path. Default is None.
    """
    TUFLOW_TYPE = const.CONTROLFILE.FVSED
    pass

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: ControlFileRunState | None = None) -> 'FVSedRunState':
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return FVSedRunState(self, ctx, parent)
    
    def _command_class(self) -> type[Command]:
        return FVSedCommand



class FVSedRunState(ControlFileRunState, FVSedMixin):
    pass
