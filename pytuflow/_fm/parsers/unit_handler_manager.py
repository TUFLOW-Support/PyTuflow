import sys
import typing
from pathlib import Path

from ..helpers.available_dat_handlers import get_available_classes
from ..helpers.singleton import Singleton

if typing.TYPE_CHECKING:
    from .units.handler import Handler


class UnitHandlerManager(metaclass=Singleton):

    def __init__(self) -> None:
        from .units.handler import Handler
        self.handlers = []
        self._handler_classes = []
        self.add_handler(Handler)
        self.load_local_handlers()

    def load_local_handlers(self):
        if Path(sys.executable.lower()).name == 'fm_to_estry.exe':
            dir_ = Path(sys.executable).parent /'_internal' / 'parsers' / 'units'
        else:
            dir_ = Path(__file__).parent.parent / 'parsers' / 'units'
        import_loc = self.__module__.rsplit('.', 1)[0] + '.units'
        base_class = 'Handler'
        for handler in get_available_classes(dir_, base_class, import_loc):
            self.add_handler(handler)

    def add_handler(self, handler: 'Handler.__class__') -> None:
        if handler not in self._handler_classes:
            self._handler_classes.append(handler)
            h = handler()
            self.handlers.append(h)

    def is_recognised_handler(self, line: str) -> 'Handler':
        for handler in self.handlers:
            if handler.valid:
                if line.startswith(handler.unit_type_name()):
                    return handler.__class__()

    def handler_from_name(self, name: str) -> 'Handler':
        for handler in self.handlers:
            if handler.__class__.__name__.lower() == name.lower():
                return handler.__class__
