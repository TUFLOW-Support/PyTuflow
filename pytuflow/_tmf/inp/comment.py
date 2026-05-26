from .inp_build_state import InputBuildState
from .. import const


class CommentInput(InputBuildState):
    """
    Input class for comment only lines.

    | e.g.
    | :code:`! Time Setting Inputs`
    """
    TUFLOW_TYPE = const.INPUT.COMMENT

    def __str__(self):
        return self._command.original_text

    def __bool__(self):
        return False
