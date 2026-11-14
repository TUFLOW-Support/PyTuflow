"""Options for run-time file resolution and TUFLOW Linux filename matching.

The filename modes correspond to the TUFLOW Classic/HPC 2026 -cs switch.
They affect Linux filename matching, not the case of parent directories.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum


class FileResolution(StrEnum):
    """Choose when TUFLOW input references are resolved during a run.

    EAGER preserves PyTuflow's existing context behaviour, including file and
    GIS enumeration on demand. DEFERRED records unresolved physical references
    for a later, explicit inspection phase; initial TCF parsing may still read
    control files and databases. Batch preflight uses deferred collection to
    avoid repeated physical reads across many scenario/event combinations.
    """

    EAGER = "eager"
    DEFERRED = "deferred"


class CaseSensitivity(IntEnum):
    """Select Linux TUFLOW filename case policy (-cs0, -cs1, -cs2).

    STRICT (-cs0): All path components, extensions included, match exactly.
    EXTENSION_INSENSITIVE (-cs1): Filename stem and directories stay exact;
        only the filename extension may differ in case.
    FILENAME_INSENSITIVE (-cs2): Filename stem and extension may differ in
        case, but directories still match exactly.

    Windows uses its filesystem's normal filename case behaviour. When
    multiple Linux candidates match, existing exact spellings take priority;
    ambiguous non-exact matches must not be chosen arbitrarily.

    Reference: https://docs.tuflow.com/classic-hpc/manual/2026.3/11-RunningSimulations.html
    """

    STRICT = 0
    EXTENSION_INSENSITIVE = 1
    FILENAME_INSENSITIVE = 2


def parse_case_sensitivity(value: CaseSensitivity | int) -> CaseSensitivity:
    """Convert a TUFLOW -cs numeric level to its named filename policy.

    Numeric levels are accepted because TUFLOW's CLI documents -cs0/-cs1/-cs2.
    This is input parsing, not an older PyTuflow public-API compatibility path.
    Booleans and other values are rejected rather than silently coerced.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("case_sensitivity must be CaseSensitivity or TUFLOW -cs0/-cs1/-cs2")
    try:
        return CaseSensitivity(value)
    except ValueError as exc:
        raise ValueError("case_sensitivity must be -cs0, -cs1 or -cs2") from exc
