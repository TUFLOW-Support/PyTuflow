from .cf_load_factory import ControlFileLoadMixin
from .fvc_build_state import FVCControlFileBuildState, FVCBase
from .cf_run_state import ControlFileRunState
from ..context import Context
from ..parsers.fvcommand import Command, FVCommand
from .. import const


class FVC(ControlFileLoadMixin, FVCControlFileBuildState):
    """Initialises the FVC class in a build state. This is the main entry point for reading/writing a TUFLOW FV
    model.

    If the class is initialised with the :code:`fpath` parameter set to ``None``, an empty class will be initialised.

    Parameters
    ----------
    fpath : PathLike, optional
        The path to the control file (str or Path). If set to ``None``, the FVC will be initialised as an
        empty control file.

    **kwargs : optional parameters

        - config : FVCConfig, optional
            This object stores useful information such as variable mappings, the event database,
            water qualiaty model directory etc. If set to None, a new FVCConfig object will be created.
            For FVC, the settings object should be left as None.
        - parent : ControlFile, optional
            Will set the parent of the control file to another control file e.g. for a FVWQ, the parent
            should be set to the FVC. For FVCs, the parent should be set to None.
        - scope : ScopeList, optional
            A list of scope objects that will be inherited by the control file itself. Not currently used
            but reserved in case this is useful information in the future.
        - log_level : str, optional
            The logging level to use for the control file. Options are 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'.
            Default is 'WARNING'.
        - log_to_file : PathLike, optional
            If set, will log the control file to the given file path. Default is None.

    Examples
    --------

    point to FV example
    """
    TUFLOW_TYPE = const.CONTROLFILE.FVC
    
    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: ControlFileRunState | None = None) -> 'FVCRunState':
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return FVCRunState(self, ctx, parent)
    
    @staticmethod
    def _command_class() -> type[Command]:
        return FVCommand
    

class FVCRunState(ControlFileRunState, FVCBase):
    pass
