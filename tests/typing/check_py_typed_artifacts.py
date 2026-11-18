"""Check PEP 561 marker membership in independently built PyTUFLOW artifacts.

Run after creating a wheel, an sdist and a second wheel built from that sdist.
This verifies the actual archive members rather than the source checkout.
"""

from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path

_MARKER = "pytuflow/py.typed"


def check_wheel(path: Path) -> None:
    """Require the exact marker path inside an installable wheel."""
    with zipfile.ZipFile(path) as archive:
        members = set(archive.namelist())
    if _MARKER not in members:
        raise AssertionError(f"{path}: missing {_MARKER}")


def check_sdist(path: Path) -> None:
    """Require the marker inside the package directory of the source archive."""
    with tarfile.open(path, mode="r:gz") as archive:
        markers = [
            member.name
            for member in archive.getmembers()
            if member.isfile() and member.name.endswith("/" + _MARKER)
        ]
    if len(markers) != 1:
        raise AssertionError(f"{path}: expected one {_MARKER}, found {markers}")


def main(direct_wheel: Path, sdist: Path, rebuilt_wheel: Path) -> None:
    check_wheel(direct_wheel)
    check_sdist(sdist)
    check_wheel(rebuilt_wheel)
    print("PEP 561 marker present in direct wheel, sdist and rebuilt wheel")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: python check_py_typed_artifacts.py "
            "direct.whl package.tar.gz rebuilt.whl"
        )
    main(*(Path(arg) for arg in sys.argv[1:]))
