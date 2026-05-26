import re
from pathlib import Path


def globify(infile: str | Path, wildcards: list[str]) -> str:
    """Converts TUFLOW wildcards (variable names, scenario/event names) to '*' for glob pattern."""
    infile = str(infile)
    if wildcards is None:
        return infile

    for wc in wildcards:
        infile = re.sub(wc, '*', infile, flags=re.IGNORECASE)
    if re.findall(r'\*\*(?![\\/])', infile):
        infile = re.sub(re.escape(r'**'), '*', infile)

    return infile
