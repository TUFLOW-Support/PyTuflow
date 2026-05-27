import sys
import typing
from pathlib import Path

from ..helpers.singleton import Singleton
from ..helpers.available_dat_handlers import get_available_classes

if typing.TYPE_CHECKING:
    from ..parsers.units.handler import Handler
    from .converter import Converter


class UnitConverterManager(metaclass=Singleton):

    def __init__(self) -> None:
        self.converters = []
        self.base_class = 'Converter'
        self._converter_classes = []
        self.load_local_converters()

    def load_local_converters(self) -> None:
        if Path(sys.executable.lower()).name == 'fm_to_estry.exe':
            dir_ = Path(sys.executable).parent /'_internal' / 'converters'
        else:
            dir_ = Path(__file__).parent
        # import_loc = 'pytuflow._fm.converters'
        # import_loc = '_fm_tmp.fm_to_estry.parsers.units'
        import_loc = self.__module__.rsplit('.', 2)[0] + '.converters'
        for converter in get_available_classes(dir_, self.base_class, import_loc):
            self.add_converter(converter)

    def add_converter(self, converter: 'Converter.__class__') -> None:
        if converter not in self._converter_classes:
            self._converter_classes.append(converter)
            c = converter()
            self.converters.append(c)

    def find_converter(self, unit: 'Handler') -> 'Converter.__class__':
        from .converter import Converter
        for converter in self.converters:
            if converter.complete_unit_type_name().upper() == f'{unit.type.upper()}_{unit.sub_type.upper()}':
                return converter.__class__
        return Converter
