from pathlib import Path
import logging
import os

from .cf_load_factory import ControlFileLoadMixin
from .fvc_build_state import FVCControlFileBuildState, FVCBase
from .cf_run_state import ControlFileRunState
from ..context import Context
from ..parsers.fvcommand import Command, FVCommand
from ..tmf_types import PathLike
from ..tuflowfv_binaries import tuflowfv_binaries
from .model_run_mixin import ModelRunMixin
from .. import const


logger = logging.getLogger('pytuflow')


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
    

class FVCRunState(ControlFileRunState, ModelRunMixin, FVCBase):

    def run(self, tuflowfv_bin: PathLike, add_cli_args: list[str] = (), *args, **kwargs):
        """Run the control file in context using the specified TUFLOW binary.

        * TUFLOW binary can be a file path to the executable or a version name that has been registered using
            the :func:`register_tuflow_binary function()<pytuflow.register_tuflow_binary>`
            or the :func:`register_tuflow_binary_folder()<pytuflow.register_tuflow_binary_folder>`.

        Additional arguments can be passed in and will be passed to the subprocess.Popen() call. By default,
        a new console will be created for the subprocess.

        Parameters
        ----------
        tuflowfv_bin : PathLike
            Path to the TUFLOW binary or a registered version name.
        add_cli_args : list[str]
            A list of additional command line arguments specific to TUFLOW that will be passed directly to the
            subprocess.Popen() call. e.g. ``add_cli_args=['-t']`` to pass in the ``-t`` flag to run TUFLOW in test mode,
            or ``add_cli_args=['-cs1']`` to pass in the ``-cs1`` flag to run TUFLOW with case-insensitive file paths.
        *args, **kwargs:
            Will be passed to subprocess.Popen() call.

        Returns
        -------
        subprocess.Popen
            The subprocess.Popen object that is created when the control file is run.

        Examples
        --------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tcf.context().run('2025.1.2')
        <Popen: returncode: None args: ['C:\\TUFLOW\\releases\\2025.1.2\\TUFLOW_iSP_...>
        """
        fv_bin = self._find_tuflow_bin(tuflowfv_binaries, tuflowfv_bin, prec='SP')
        os.chdir(str(self.fpath.parent))
        return self._run(self.fpath, fv_bin, self.ctx.context_args, add_cli_args, *args, **kwargs)
