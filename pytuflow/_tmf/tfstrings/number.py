import re
import typing


def is_a_number_or_var(value: typing.Any) -> bool:
    """Check if a value is a number including if the value is a variable reference to a number.

    This logic assumes that variables in TUFLOW are typically used in file paths or for a number value.
    e.g.
    Set Variable CELL_SIZE = 5
    Read GIS Code == ../model/gis/2d_code_<<SCENARIO>>_001_R.shp

    It is very rare to use a variable for a string value in a setting, although could happen e.g.
    SGS == <<SGS_SWITCH>>  ! values ON or OFF
    In this case this routine would incorrectly flag this is a number value. It is up to the calling routine to check
    the context.
    """
    try:
        float(value)
        return True
    except ValueError:
        pass
    if re.findall(r'<<.+?>>', value) and re.findall(r'<<.+?>>', value)[0] == value.strip():
        return True
    return False
