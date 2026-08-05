from __future__ import annotations

import os
import re
from pathlib import Path
import json


def _normalize_slashes(cmd: str) -> str:
    """Normalize all path separators in *cmd* to the OS-native separator."""
    return cmd.replace('\\', os.sep).replace('/', os.sep)


def _parse_filter(value: str) -> tuple[str, bool, int]:
    """Parse a filter string that may use ``/pattern/flags`` regex syntax.

    Returns ``(pattern, is_regex, flags)``.  Supported flag characters:
    ``i`` (IGNORECASE), ``m`` (MULTILINE), ``s`` (DOTALL).

    Plain strings are returned unchanged with ``is_regex=False, flags=0``.
    """
    if value.startswith('/'):
        last_slash = value.rfind('/', 1)
        if last_slash > 0:
            pattern = value[1:last_slash]
            flag_chars = value[last_slash + 1:]
            flags = 0
            for char, flag in (('i', re.IGNORECASE), ('m', re.MULTILINE), ('s', re.DOTALL)):
                if char in flag_chars:
                    flags |= flag
            return pattern, True, flags
    return value, False, 0


def _normalize_rendered(text: str) -> str:
    """Apply OS-native path separators to every line of a rendered template."""
    return '\n'.join(_normalize_slashes(line) for line in text.split('\n'))


def _variables_from_cf_path(cf_path: Path, **overrides) -> dict:
    """Try to infer model_name and iter from a control file filename."""
    stem = cf_path.stem  # e.g. mymodel_001
    variables = {}
    m = re.match(r'^(.+)_(\d+)$', stem)
    if m:
        variables['model_name'] = m.group(1)
        variables['iter'] = m.group(2)
    else:
        variables['model_name'] = stem
        variables['iter'] = '001'
    variables.update({k: v for k, v in overrides.items() if v is not None})
    return variables


def _create_projection_file(
    gis_dir: Path, gis_format: str, model_name: str, iter_: str, crs: str
) -> None:
    """Create a projection / spatial-database reference file in *gis_dir*.

    * SHP → ``projection.shp`` (empty Point layer carrying the CRS)
    * MIF → ``projection.mif`` (same)
    * GPKG → ``{model_name}_{iter}.gpkg`` with a ``projection`` layer
    """
    import warnings
    from ..._tmf import TuflowPath

    fmt = gis_format.upper()
    if fmt == 'SHP':
        uri = f'{gis_dir / "projection.shp"} >> projection'
    elif fmt == 'MIF':
        uri = f'{gis_dir / "projection.mif"} >> projection'
    elif fmt == 'GPKG':
        uri = f'{gis_dir / f"{model_name}_{iter_}.gpkg"} >> projection'
    else:
        return  # unknown format — skip silently

    with warnings.catch_warnings():
        warnings.filterwarnings(
            'ignore', message=".*Column names longer than 10 characters.*", category=UserWarning
        )
        p = TuflowPath(uri)
        with p.open_gis('w', 'Point', crs):
            pass  # no fields or features needed — CRS is embedded in the file


def _parse_feature(raw: str) -> str | dict:
    if raw.startswith('{'):
        return json.loads(raw)
    else:
        return raw


def _parse_features_list(raw: list[str]) -> list[str | dict]:
    """Parse each element of ``--features``.

    Plain strings are kept as-is.  Anything that parses as a JSON object
    (``{...}``) is returned as a dict — used for per-instance variable
    overrides on ``allow_multiple`` features.
    """
    result = []
    for item in raw:
        stripped = item.strip()
        result.append(_parse_feature(stripped))
    return result
