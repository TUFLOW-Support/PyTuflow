from .cf_load_factory import ControlFileLoadMixin
from .fv_build_state import FVControlFileBuildState
from ..parsers.fvcommand import Command, FVPTMCommand
from .. import const


class FVPTM(ControlFileLoadMixin, FVControlFileBuildState):
    """Initialises the FV Particle Tracking Control File class in a build state.

    If the class is initialised with the :code:`fpath` parameter set to ``None``, an empty class will be initialised.

    Parameters
    ----------
    fpath : PathLike, optional
        The path to the control file (str or Path). If set to ``None``, the FVPTM will be initialised as an
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
    TUFLOW_TYPE = const.CONTROLFILE.FVPTM
    
    def _command_class(self) -> type[Command]:
        return FVPTMCommand
