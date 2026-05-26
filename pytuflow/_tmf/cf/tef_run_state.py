from .cf_run_state import ControlFileRunState
from ..abc.tef_base import TEFBase


class TEFRunState(ControlFileRunState, TEFBase):
    """Class for storing the run state of the TEF file.

    This class should not be instantiated directly, but rather it should be created from an instance
    of a BuildState class using the :meth:`context()<pytuflow.TCF.context>` method of the BuildState class.

    Parameters
    ----------
    build_state : TEF
        The TEF build state instance that the RunState object is based on.
    context : Context
        The context instance that will be used to resolve the build state.
    parent : ControlFileRunState
        The parent control file run state.
    """
    pass
