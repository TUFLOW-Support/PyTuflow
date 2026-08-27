import re


def add_geom_suffix(name_: str, suffix: str) -> str:
    """Add geometry suffix to name if it doesn't already exist."""
    from ..tfpathlib import TuflowPath
    name_ = str(name_)

    if not suffix or re.findall(rf'{re.escape(suffix)}$', TuflowPath(name_).with_suffix("").name, flags=re.IGNORECASE):
        return name_

    return f'{TuflowPath(name_).with_suffix("")}{suffix}{TuflowPath(name_).suffix}'


def remove_geom_suffix(name_: str | None) -> str | None:
    """Removes geometry suffix from name if it exists."""
    from ..tfpathlib import TuflowPath
    if name_ is None:
        return None

    new_name = re.sub(r'_[PLR]$', '', str(TuflowPath(name_).with_suffix("")), flags=re.IGNORECASE)

    return str(TuflowPath(new_name).with_suffix(TuflowPath(name_).suffix))


def get_geom_suffix(name_: str) -> str:
    """Returns geometry suffix from the name if it exists."""
    from ..tfpathlib import TuflowPath
    if re.findall(r'_[PLR]$', str(TuflowPath(name_).with_suffix("")), flags=re.IGNORECASE):
        return re.findall(r'_[PLR]$', str(TuflowPath(name_).with_suffix("")), flags=re.IGNORECASE)[0]

    return ''
