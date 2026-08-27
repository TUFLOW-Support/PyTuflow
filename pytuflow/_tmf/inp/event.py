import typing

from .inp_build_state import InputBuildState
from ..parsers.command import EventCommand
from .. import const

if typing.TYPE_CHECKING:
    # noinspection PyUnusedImports
    from ..cf.cf_build_state import ControlFileBuildState


class EventInput(InputBuildState):
    TUFLOW_TYPE = const.INPUT.EVENT

    def __init__(self, parent: 'ControlFileBuildState | None', command: EventCommand):
        super().__init__(parent, command)
        self.event_name = command.event_name
        self.event_var, self.event_value = command.get_event_source() if command.is_event_source() else (None, None)
