import json
import re
from pathlib import Path


with (Path(__file__).parents[1] / 'data' / 'data_type_name_alternatives.json').open() as f:
    DATA_TYPE_NAME_ALTERNATIVES = json.load(f)


def get_standard_data_type_name(name: str) -> str:
    """Returns the standard data type name for a given name. The name can be a short name, long name, or
    any standard alternate name of the given data type.

    Parameters
    ----------
    name : str
        The name of the data type.

    Returns
    -------
    str
        The standard data type name.
    """
    for key, vals in DATA_TYPE_NAME_ALTERNATIVES['data_types'].items():
        if name.lower() == key.lower():
            return key
        for val in vals:
            if re.match(fr'^(?:t?max(?:imum)?(?:\s|_|-)?)?{val}(?:(?:\s|_|-)?t?max(?:imum)?)?$', name, re.IGNORECASE):
                if '\\d' in key:
                    n = re.findall(r'\d+', name)
                    return key.replace('\\d', n[0]) if n else key
                return key

    return name.lower()
