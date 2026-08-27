from pathlib import Path

from ..converters.unit_converter_manager import UnitConverterManager


def help_string() -> str:
    help_file = Path(__file__).parent / '../../data/HELP'
    with help_file.open() as f:
        txt = f.read()
    supported_units = [x.complete_unit_type_name().upper().replace('_', ' ').strip() for x in UnitConverterManager().converters if x.complete_unit_type_name()]
    if supported_units:
        txt = '{0}\nSUPPORTED TYPES:\n..{1}'.format(txt, '\n..'.join(supported_units))
    return txt
