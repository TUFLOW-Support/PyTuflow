import typing

from ..options import CaseSensitivity, FileResolution
from .cf_load_factory import ControlFileLoadMixin
from .. import const
from .tcf_build_state import TCFBuildState
from ..tmf_types import PathLike
from ..context import Context
from .cf_run_state import ControlFileRunState
from ..abc.tf_cf_base_mixin import TuflowControlFileMixin

if typing.TYPE_CHECKING:
    from .tcf_run_state import TCFRunState
    from .tgc import TGC
    from .tbc import TBC
    from .ecf import ECF
    from .tscf import TSCF
    from .tef import TEF
    from ..db.bc_dbase import BCDatabase
    from ..db.soil import SoilDatabase
    from ..db.rf import RainfallDatabase
    from ..db.mat import MatDatabase
    from ..fragment_dependencies import FragmentBatchResult


class TCF(ControlFileLoadMixin, TuflowControlFileMixin, TCFBuildState):
    """Initialises the TCF class in a build state. This is the main entry point for reading/writing a TUFLOW
    model.

    If the class is initialised with the :code:`fpath` parameter set to ``None``, an empty class will be initialised.

    Parameters
    ----------
    fpath : PathLike, optional
        The path to the control file (str or Path). If set to ``None``, the TCF will be initialised as an
        empty control file.

    **kwargs : optional parameters

        - config : TCFConfig, optional
            This object stores useful information such as variable mappings, the event database,
            current spatial database etc. If set to None, a new TCFConfig object will be created.
            For TCFs, the settings object should be left as None.
        - parent : ControlFile, optional
            Will set the parent of the control file to another control file e.g. for a TGC, the parent
            should be set to the TCF. For TCFs, the parent should be set to None.
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

    The following examples demonstrate some common operations and use cases for the TCF class:

    - :ref:`tcf_load_and_run`

    """
    TUFLOW_TYPE = const.CONTROLFILE.TCF

    def __init__(self, fpath: PathLike | None = None, *,
                 case_sensitivity: CaseSensitivity | None = None, **kwargs):
        """Load a model using a TUFLOW Linux filename-case policy.

        The optional ``CaseSensitivity`` enum identifies TUFLOW's -cs0
        (strict), -cs1 (extension only) and -cs2 (whole filename) modes.
        An omitted mode uses the configured value, defaulting to -cs0 on
        Linux. Windows retains ordinary filesystem filename matching.
        """
        if case_sensitivity is not None and kwargs.get('config') is not None:
            raise ValueError('Pass case_sensitivity or config, not both')
        if case_sensitivity is not None or kwargs.get('config') is not None:
            from pathlib import Path
            from ..settings import TCFConfig
            from ..tfpathlib import TuflowPath
            mode = (case_sensitivity if case_sensitivity is not None
                    else kwargs['config'].case_sensitivity)
            if fpath is not None:
                fpath = TuflowPath.init_case_policy_path(fpath, Path.cwd(), mode)
            if case_sensitivity is not None:
                existing = fpath if fpath is not None and Path(fpath).is_file() else None
                kwargs['config'] = TCFConfig(tcf=existing, case_sensitivity=mode)
        # ControlFileBuildState replaces a falsey configuration with the
        # default config when loading. Initialise a supplied empty config here
        # instead, preserving its selected -cs mode, variables and settings.
        # Do not mutate the caller's configuration object.
        if fpath is not None and kwargs.get('config') is not None:
            supplied = kwargs['config']
            from pathlib import Path
            if not supplied and Path(fpath).is_file():
                from ..settings import from_config
                from ..tfpathlib import TuflowPath
                config = from_config(supplied)
                config.tcf = TuflowPath(fpath)
                config.model_name = config.get_model_name(config.tcf)
                config.read_tcf()
                kwargs['config'] = config
        super(TCF, self).__init__(fpath, **kwargs)

    def tgc(self, context: Context = None) -> 'TGC':
        """Returns the TGC ControlFile instance.

        If more than one TGC control file instance exists, a Context object must be provided to resolve to the correct
        TGC.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct TGC control file instance. Not required unless more than one
            TGC control file instance exists.

        Returns
        -------
        TGC
            The TGC control file instance.

        Raises
        ------
        KeyError
            If the Geometry Control File is not found in the control file.
        ValueError
            If more than one Geometry Control File is found and no context is provided to resolve the correct, or
            if the context does not resolve into a single Geometry Control File.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tgc = tcf.tgc()
        """
        return super().tgc(context=context)

    def tbc(self, context: Context = None) -> 'TBC':
        """Returns the TBC ControlFile instance.

        If more than one TGC control file instance exists, a Context object must be provided to resolve to the correct
        TBC.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct TBC control file instance. Not required unless more than one
            TBC control file instance exists.

        Returns
        -------
        TBC
            The TGC control file instance.

        Raises
        ------
        KeyError
            If the BC Control File is not found in the control file.
        ValueError
            If more than one BC Control File is found and no context is provided to resolve the correct, or
            if the context does not resolve into a single BC Control File.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tbc = tcf.tbc()
        """
        return super().tbc(context=context)

    def ecf(self, context: Context = None) -> 'ECF':
        """Returns the ECF ControlFile instance.

        If more than one ECF control file instance exists, a Context object must be provided to resolve to the correct
        ECF.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct ECF control file instance. Not required unless more than one
            ECF control file instance exists.

        Returns
        -------
        ECF
            The ECF control file instance.

        Raises
        ------
        KeyError
            If the ESTRY Control File is not found in the control file.
        ValueError
            If more than one ESTRY Control File is found and no context is provided to resolve the correct, or
            if the context does not resolve into a single ESTRY Control File.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> ecf = tcf.ecf()
        """
        return super().ecf(context=context)

    def tscf(self, context: Context = None) -> 'TSCF':
        """Returns the TSCF ControlFile instance.

        If more than one TSCF control file instance exists, a Context object must be provided to resolve to the correct
        TSCF.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct TSCF control file instance. Not required unless more than one
            TSCF control file instance exists.

        Returns
        -------
        TSCF
            The TSCF control file instance.

        Raises
        ------
        KeyError
            If the SWMM Control File is not found in the control file.
        ValueError
            If more than one SWMM Control File is found and no context is provided to resolve the correct, or
            if the context does not resolve into a single SWMM Control File.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tscf = tcf.tscf()
        """
        return super().tscf(context=context)

    def tef(self, context: Context = None) -> 'TEF':
        """Returns the TEF ControlFile instance.

        If more than one TEF control file instance exists, a Context object must be provided to resolve to the correct
        TEF.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct TEF control file instance. Not required unless more than one
            TEF control file instance exists.

        Returns
        -------
        TEF
            The TEF control file instance.

        Raises
        ------
        KeyError
            If the TEF Control File is not found in the control file.
        ValueError
            If more than one Event File is found and no context is provided to resolve the correct, or
            if the context does not resolve into a single Event File.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tef = tcf.tef()
        """
        return super().tef(context=context)

    def bc_dbase(self, context: Context = None) -> 'BCDatabase':
        """Returns the BCDatabase database instance.

        If more than one BCDatabase database instance exists, a Context object must be provided to resolve to the correct
        BCDatabase.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct BCDatabase database instance. Not required unless more than one
            BCDatabase database instance exists.

        Returns
        -------
        BCDatabase
            The BCDatabase database instance.

        Raises
        ------
        KeyError
            If the BCDatabase database is not found in the control file.
        ValueError
            If more than one BCDatabase database is found and no context is provided to resolve the correct, or
            if the context does not resolve into a single BCDatabase database.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> bc_dbase = tcf.bc_dbase()
        """
        return super().bc_dbase(context=context)

    def mat_file(self, context: Context = None) -> 'MatDatabase':
        """Returns the MatDatabase database instance.

        If more than one MatDatabase database instance exists, a Context object must be provided to resolve to the correct
        MatDatabase.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct MatDatabase database instance. Not required unless more than one
            MatDatabase database instance exists.

        Returns
        -------
        MatDatabase
            The MatDatabase database instance.

        Raises
        ------
        KeyError
            If the MatDatbase database is not found in the control file.
        ValueError
            If more than one MatDatbase database is found and no context is provided to resolve the correct, or
            if the context does not resolve into a single MatDatbase database.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> mat_file = tcf.mat_file()
        """
        return super().mat_file(context=context)

    def soils_file(self, context: Context = None) -> 'SoilDatabase':
        """Returns the SoilDatabase database instance.

        If more than one SoilDatabase database instance exists, a Context object must be provided to resolve to the correct
        SoilDatabase.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct SoilDatabase database instance. Not required unless more than one
            SoilDatabase database instance exists.

        Returns
        -------
        SoilDatabase
            The SoilDatabase database instance.

        Raises
        ------
        KeyError
            If the SoilDatabase database is not found in the control file.
        ValueError
            If more than one SoilDatabase database is found and no context is provided to resolve the correct, or
            if the context does not resolve into a single SoilDatabase database.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> soils_file = tcf.soils_file()
        """
        return super().soils_file(context=context)

    def rainfall_dbase(self, context: Context = None) -> 'RainfallDatabase':
        """Returns the RainfallDatabase database instance.

        If more than one RainfallDatabase database instance exists, a Context object must be provided to resolve to the correct
        RainfallDatabase.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct RainfallDatabase database instance. Not required unless more than one
            RainfallDatabase database instance exists.

        Returns
        -------
        RainfallDatabase
            The RainfallDatabase database instance.

        Raises
        ------
        KeyError
            If the RainfallDatabase database is not found in the control file.
        ValueError
            If more than one RainfallDatabase database is found and no context is provided to resolve the correct, or
            if the context does not resolve into a single RainfallDatabase database.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> rainfall_dbase = tcf.rainfall_dbase()
        """
        return super().rainfall_dbase(context=context)

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: ControlFileRunState | None = None,
                *, file_resolution: FileResolution | None = None) -> 'TCFRunState':
        """Create a run context with explicit file-resolution behaviour.

        ``FileResolution.EAGER`` is the default and keeps PyTuflow's
        original file and GIS inspection behaviour. ``DEFERRED`` records
        file references for an explicit later inspection. It avoids
        repeated physical enumeration across many selected runs; parsing
        the original TCF may still read control files and databases.
        """
        from .tcf_run_state import TCFRunState
        ctx = context if context else Context(run_context, config=self.config)
        if file_resolution is not None:
            try:
                ctx.file_resolution = FileResolution(file_resolution)
            except ValueError as exc:
                raise ValueError("file_resolution must be eager or deferred") from exc
        return TCFRunState(self, ctx, parent)

    def collect_file_dependencies(
        self,
        run_flags: typing.Iterable[str | dict[str, str]],
    ) -> 'FragmentBatchResult':
        """Collect immutable, ordered file references for the specified runs.

        No physical file or GIS inspection occurs during dependency collection.
        """
        from ..fragment_dependencies import collect_file_dependencies
        return collect_file_dependencies(self, run_flags)


# Preserve the original context method for safe fragment eligibility checks.
_TCF_CONTEXT = TCF.context
