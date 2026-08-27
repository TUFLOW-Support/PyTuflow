from __future__ import annotations

import os
import re
from pathlib import Path
from string import Template
import json


def _normalize_slashes(cmd: str) -> str:
    """Normalize all path separators in *cmd* to the OS-native separator, except inside <...> blocks or inside comments.

    Example 1: "a/b <path/to/file> c\\d" -> "a{sep}b <path/to/file> c{sep}d"
    
    Example 2: "! 1D/2D linking" is unaffected
    """
    protected = []

    def _protect(s: str) -> str:
        protected.append(s)
        return f"__PROTECTED_{len(protected)-1}__"

    # 1) Protect comments first (so any <...> inside comments is untouched)
    #    Comment marker recognized at start-of-line or after whitespace.
    temp = re.sub(
        r"(?m)(^|\s)([#!].*)$",
        lambda m: m.group(1) + _protect(m.group(2)),
        cmd,
    )

    # 2) Protect angle-bracket sections in non-comment text
    temp = re.sub(
        r"<[^<>]*>",
        lambda m: _protect(m.group(0)),
        temp,
    )

    # 3) Replace both slash types outside protected blocks
    temp = temp.replace("/", os.sep).replace("\\", os.sep)

    # 4) Restore protected blocks
    for i, original in enumerate(protected):
        temp = temp.replace(f"__PROTECTED_{i}__", original)

    return temp


def safe_substitute(text: str, variables: dict) -> str:
    """Perform Template.safe_substitute while preserving inline comment positions.

    Tabs in *text* are expanded to 4 spaces before substitution.  After
    substitution the comment (anything from the first ``!`` or ``#`` that is
    not part of a ``${...}`` placeholder) is re-attached at its original
    column.  If the substituted content is longer than that column, the
    comment is placed 2 spaces after the end of the content instead.

    Lines without a comment are passed straight through to
    ``Template.safe_substitute``.
    """
    lines = text.splitlines(keepends=True)
    result = []
    for line in lines:
        trailing_newline = ''
        if line.endswith('\n'):
            trailing_newline = '\n'
            line = line[:-1]

        # Expand tabs before processing
        line = line.expandtabs(4)

        # Find the first comment character ('!' or '#') that is not inside a
        # ${...} placeholder.  We walk character-by-character so we can skip
        # over placeholder tokens.
        comment_start = None
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '$' and i + 1 < len(line):
                if line[i + 1] == '{':
                    # Skip ${...}
                    end = line.find('}', i + 2)
                    if end != -1:
                        i = end + 1
                        continue
                elif line[i + 1].isalnum() or line[i + 1] == '_':
                    # Skip $identifier
                    j = i + 1
                    while j < len(line) and (line[j].isalnum() or line[j] == '_'):
                        j += 1
                    i = j
                    continue
            if ch in ('!', '#'):
                comment_start = i
                break
            i += 1

        if comment_start is None:
            # No comment — plain substitution
            result.append(Template(line).safe_substitute(variables) + trailing_newline)
            continue

        content_part = line[:comment_start]
        comment_part = line[comment_start:]

        substituted = Template(content_part).safe_substitute(variables)

        # Determine where the comment should go
        substituted_len = len(substituted.rstrip())
        if substituted_len >= comment_start:
            # Content grew past the original comment column — pad 2 spaces after content
            comment_line = substituted.rstrip() + '  ' + comment_part
        else:
            # Pad to original column
            comment_line = substituted.ljust(comment_start) + comment_part

        result.append(comment_line + trailing_newline)

    return ''.join(result)


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
