import re
import typing

from .cf_build_state import ControlFileBuildState
from .cf_run_state import ControlFileRunState
from .cf_load_factory import ControlFileLoadMixin
from ..context import Context
from .. import const

if typing.TYPE_CHECKING:
    from ..db.pit_inlet import PitInletDatabase, PitInletDatabaseRunState


class ECFRunState(ControlFileRunState):

    def pit_dbase(self) -> 'PitInletDatabaseRunState':
        """Returns the model's PitInletDatabaseRunState instance.

        Returns
        -------
        PitInletDatabaseRunState
            The PitInletDatabaseRunState instance.

        Raises
        ------
        KeyError
            If the pit inlet database is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> pit_dbase = pit_dbase.context().ecf().pit_dbase()
        """
        return self._find_control_file('pit inlet database|depth discharge database', None, regex=True, regex_flags=re.IGNORECASE)


class ECF(ControlFileLoadMixin, ControlFileBuildState):
    """Initialises the ECF class in a build state.

    If the class is initialised with the :code:`fpath` parameter set to ``None``, an empty class will be initialised.

    Parameters
    ----------
    fpath : PathLike, optional
        The path to the control file (str or Path). If set to ``None``, the ECF will be initialised as an
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
    TUFLOW_TYPE = const.CONTROLFILE.ECF

    def pit_dbase(self, context: Context = None) -> 'PitInletDatabase':
        """Returns the PitInletDatabase database instance.

        If more than one PitInletDatabase database instance exists, a Context object must be provided to resolve to the correct
        Pit Inlet Database.

        Parameters
        ----------
        context : Context, optional
            A context object to resolve the correct PitInletDatabase instance. Not required unless more than one
            PitInletDatabase file instance exists.

        Returns
        -------
        PitInletDatabase
            The PitInletDatabase instance.

        Raises
        ------
        KeyError
            If the PitInletDatabase database is not found in the control file.
        ValueError
            If more than one PitInletDatabase database is found and no context is provided to resolve the correct, or
            if the context does not resolve into a single PitInletDatabase database.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> bc_dbase = tcf.ecf().pit_dbase()
        """
        return self._find_control_file('pit inlet database|depth discharge database', context, regex=True, regex_flags=re.IGNORECASE)

    def context(self,
                run_context: str | dict[str, str] = '',
                context: Context | None = None,
                parent: ControlFileRunState | None = None) -> ECFRunState:
        # docstring inherited
        ctx = context if context else Context(run_context, config=self.config)
        return ECFRunState(self, ctx, parent)
