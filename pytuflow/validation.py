"""Optional, read-only physical validation of parsed TUFLOW input references.

Dependency collection and control-file interpretation remain entirely separate.
This module accepts immutable per-run dependency projections and inspects only
the selected source paths, GeoPackage metadata, optional raster headers and BC CSV headers.
Inspection does not execute TUFLOW or require the QGIS runtime.
"""

from __future__ import annotations

import csv
import fnmatch
import os
import stat
from collections import defaultdict
from collections.abc import Collection, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from ._tmf.gpkg_safety import check_gpkg_safety, read_gpkg_layer_names
from ._tmf.options import CaseSensitivity, parse_case_sensitivity

if TYPE_CHECKING:
    from pyproj import CRS

    from ._tmf.cf.tcf import TCF
    from ._tmf.dependency_records import BatchDependencyRun
    from ._tmf.file_reference import FileReference

ValidationStatus = Literal["present", "missing", "unresolved", "unsupported"]
ValidationKind = Literal[
    "file", "wildcard", "layer", "csv_header", "raster_metadata",
    "crs", "attribute", "context",
]


class DependencyProjection(Protocol):
    """Immutable per-run dependency records accepted by the physical inspector."""

    @property
    def runs(self) -> tuple[BatchDependencyRun, ...]:
        """Return the immutable run dependencies to inspect."""
        ...


@dataclass(frozen=True, slots=True)
class ValidationOptions:
    """Configure supported physical checks and their resource limits.

    Args:
        check_files: Verify selected input paths exist and are readable.
        check_gpkg_layers: Verify selected GeoPackage layers.
        check_bc_csv_headers: Check referenced BC CSV column names.
        check_raster_metadata: Open required raster headers read-only (on by default).
        check_crs: Warn about absent, invalid or inconsistent raster/vector CRSs (on by default).
        maximum_raster_subdatasets: Bound NetCDF variable enumeration.
        io_workers: Maximum concurrent workers for independent input checks.
        maximum_directory_entries: Limit names visited per wildcard directory.
        maximum_header_lines: Limit lines inspected for a BC CSV header.
        maximum_header_bytes: Bound the bytes read while inspecting a CSV header.
        case_sensitivity: Linux TUFLOW filename policy (CaseSensitivity enum); None uses
            the parsed model's policy.

    """

    check_files: bool = True
    check_gpkg_layers: bool = True
    check_bc_csv_headers: bool = False
    io_workers: int = 1
    maximum_directory_entries: int = 50_000
    maximum_header_lines: int = 5
    maximum_header_bytes: int = 1_048_576
    # Linux TUFLOW -cs0/-cs1/-cs2. None means the projection has not
    # provided a policy: a possible spelling mismatch must fail closed.
    case_sensitivity: CaseSensitivity | None = None
    # Append fields to preserve positional construction of existing options.
    check_raster_metadata: bool = True
    maximum_raster_subdatasets: int = 64
    check_crs: bool = True

    def __post_init__(self) -> None:
        """Reject invalid resource limits and filename-case modes."""
        if self.case_sensitivity is not None:
            object.__setattr__(
                self, "case_sensitivity", parse_case_sensitivity(self.case_sensitivity)
            )
        if not 1 <= self.io_workers <= 32:
            raise ValueError("io_workers must be between 1 and 32")
        if min(
            self.maximum_directory_entries,
            self.maximum_header_lines,
            self.maximum_header_bytes,
            self.maximum_raster_subdatasets,
        ) < 1:
            raise ValueError("Inspection limits must be positive")


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    """Record the status of one input and its source-command provenance.

    The status is present, missing, unresolved or unsupported. For advisory
    CRS findings, severity="warning" means an unresolved CRS does not fail
    the preflight. Source ownership, input UUID and run index allow the
    same physical file to be attributed separately to each affected run.
    """

    run_index: int
    flags: str
    status: ValidationStatus
    kind: ValidationKind
    path: Path | None
    detail: str = ""
    layer: str | None = None
    origin: str = ""
    input_uuid: str = ""
    command_index: int = -1
    owner_control_file: Path | None = None
    database_kind: str | None = None
    source_pattern: Path | None = None
    csv_columns: tuple[str, ...] | None = None
    # CRS findings are advisory; their unresolved status is not a failed preflight.
    severity: Literal["error", "warning"] = "error"


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Report physical preflight findings for selected scenario/event runs.

    A report passes only if at least one run was inspected and all requirements
    are present. Physical inspection counts represent deduplicated I/O rather
    than a separate file read for every run.
    """

    findings: tuple[ValidationFinding, ...]
    run_count: int
    files_examined: int
    geopackages_examined: int
    csv_headers_examined: int
    directories_scanned: int
    # Count unique existing raster source paths, not GDAL root/subdataset handles.
    raster_sources_examined: int = 0
    # Count additional NetCDF subdataset open attempts, excluding root opens.
    raster_subdatasets_opened: int = 0
    crs_sources_examined: int = 0

    @property
    def warnings(self) -> tuple[ValidationFinding, ...]:
        """Return non-failing CRS diagnostics with original run provenance."""
        return tuple(item for item in self.findings if item.severity == "warning")

    @property
    def passed(self) -> bool:
        """Warnings do not override ordinary physical-validation success."""
        return bool(self.run_count) and all(
            item.status == "present" or item.severity == "warning"
            for item in self.findings
        )


@dataclass(frozen=True, slots=True)
class _Requirement:
    """Identify one requirement and its original run and command."""

    run_index: int
    flags: str
    path: Path
    layer: str | None
    origin: str
    input_uuid: str
    command_index: int
    owner_control_file: Path | None
    database_kind: str | None
    csv_columns: tuple[str, ...] | None
    unresolved: tuple[str, ...] = ()
    secondary_source: bool = False
    implicit_gpkg_layer: bool = False
    requires_raster_metadata_scan: bool = False
    requires_vector_crs_scan: bool = False


@dataclass(frozen=True, slots=True)
class _Inspection:
    """Record an inspected file and its associated validation status."""

    status: ValidationStatus
    detail: str = ""
    layers: tuple[str, ...] = ()
    layer_error: str = ""
    csv_records: tuple[tuple[str, ...], ...] = ()
    csv_error: str = ""
    gpkg_examined: bool = False
    csv_examined: bool = False
    raster_results: tuple[tuple[str | None, ValidationStatus, str], ...] = ()
    raster_examined: bool = False
    raster_subdatasets_opened: int = 0
    # Raster CRS is captured during the same Rasterio open as its header.
    raster_crs: tuple[tuple[str | None, str | None], ...] = ()
    # Each vector request may select one or several concrete GPKG layers.
    vector_crs: tuple[
        tuple[tuple[str | None, bool], tuple[tuple[str | None, str | None, str], ...]], ...
    ] = ()
    crs_examined: bool = False


@dataclass(slots=True)
class _InvocationCache:
    """Private, short-lived physical inspection state shared by both batch passes.

    A batch owns this cache only until it returns. Reuse physical results
    already inspected in the first pass, while inspecting newly discovered
    dependencies and newly requested metadata in the final pass. No model
    or path state survives into a later validation invocation.
    """

    inspected: dict[Path, _Inspection] = field(default_factory=dict)
    wildcard_matches: dict[Path, tuple[Path, ...]] = field(default_factory=dict)
    wildcard_failures: dict[Path, tuple[ValidationStatus, str]] = field(default_factory=dict)
    literal_paths: dict[Path, Path] = field(default_factory=dict)
    literal_failures: dict[Path, tuple[ValidationStatus, str]] = field(default_factory=dict)
    directories_scanned: int = 0


def _implicit_gpkg_layer(reference: FileReference) -> bool:
    """Return whether the parser inferred the layer from the filename stem.

    The original syntactic value distinguishes a GeoPackage without a
    `>> layer` selector from an explicit wildcard layer. A globbed filename
    must bind its *concrete* stem, never reuse the unexpanded stem pattern.
    """
    if (
        reference.layer_pattern is None
        or reference.path_pattern.suffix.casefold() != ".gpkg"
    ):
        return False
    from ._tmf.tfpathlib import TuflowPath

    _, explicit_layer = TuflowPath(reference.expanded_value)._split_db_and_lyr()
    return (
        explicit_layer is None
        and reference.layer_pattern.casefold()
        == reference.path_pattern.stem.casefold()
    )


def _requirements(projection: DependencyProjection) -> tuple[
    list[_Requirement], list[ValidationFinding]
]:
    """Collect per-run physical requirements with provenance."""
    requirements: list[_Requirement] = []
    errors: list[ValidationFinding] = []
    for run in projection.runs:
        if run.error is not None:
            errors.append(
                ValidationFinding(
                    run.index, run.flags, "unresolved", "context", None, run.error
                )
            )
            continue  # Never inspect any partial references from a failed run.

        links = run.input_references
        if links:
            for link in links:
                reference = link.reference
                requirements.append(
                    _Requirement(
                        run.index,
                        run.flags,
                        reference.path_pattern,
                        reference.layer_pattern,
                        reference.origin,
                        link.input_uuid,
                        link.command_index,
                        link.owner_control_file,
                        reference.database_kind,
                        getattr(reference, "csv_columns", None),
                        reference.unresolved_variables,
                        implicit_gpkg_layer=_implicit_gpkg_layer(reference),
                        requires_raster_metadata_scan=reference.requires_raster_metadata_scan,
                        requires_vector_crs_scan=reference.requires_vector_crs_scan,
                    )
                )
        else:
            # Callers can supply file references without optional command
            # provenance; still validate the files in that case.
            for reference in run.file_references:
                requirements.append(
                    _Requirement(
                        run.index,
                        run.flags,
                        reference.path_pattern,
                        reference.layer_pattern,
                        reference.origin,
                        "",
                        -1,
                        None,
                        reference.database_kind,
                        getattr(reference, "csv_columns", None),
                        reference.unresolved_variables,
                        implicit_gpkg_layer=_implicit_gpkg_layer(reference),
                        requires_raster_metadata_scan=reference.requires_raster_metadata_scan,
                        requires_vector_crs_scan=reference.requires_vector_crs_scan,
                    )
                )

        activations = {
            activation.input_uuid: activation
            for activation in run.database_activations
        }
        for source in run.database_sources:
            owner = activations.get(source.input_uuid)
            if source.input_uuid and owner is None:
                errors.append(
                    ValidationFinding(
                        run.index,
                        run.flags,
                        "unresolved",
                        "context",
                        source.path_pattern,
                        "Secondary source has no matching active database declaration",
                        origin=source.owning_command,
                        input_uuid=source.input_uuid,
                        owner_control_file=source.owner_control_file,
                        database_kind=source.database_kind,
                    )
                )
                continue
            if owner is not None and owner.database_kind != source.database_kind:
                errors.append(
                    ValidationFinding(
                        run.index,
                        run.flags,
                        "unresolved",
                        "context",
                        source.path_pattern,
                        "Secondary source kind does not match its active database",
                        origin=source.owning_command,
                        input_uuid=source.input_uuid,
                        owner_control_file=source.owner_control_file,
                        database_kind=source.database_kind,
                    )
                )
                continue
            requirements.append(
                _Requirement(
                    run.index,
                    run.flags,
                    source.path_pattern,
                    source.layer_pattern,
                    source.owning_command,
                    source.input_uuid,
                    owner.sequence if owner is not None else -1,
                    source.owner_control_file,
                    source.database_kind,
                    getattr(source, "csv_columns", None),
                    secondary_source=True,
                    requires_raster_metadata_scan=source.requires_raster_metadata_scan,
                    requires_vector_crs_scan=source.requires_vector_crs_scan,
                )
            )
    return requirements, errors


def _has_wildcards(path: str) -> bool:
    """Return whether a path contains glob metacharacters."""
    return any(char in path for char in "*?[")


def _filename_matches(
    candidate: str, pattern: str, case_sensitivity: CaseSensitivity | None, *,
    windows: bool,
) -> bool:
    """Match the final filename using TUFLOW -cs semantics, not folder case.

    -cs0 is strict; -cs1 relaxes extensions only; -cs2 relaxes both filename
    and extension. Windows always uses its filesystem's insensitive names.
    """
    if windows:
        return fnmatch.fnmatchcase(
            os.path.normcase(candidate), os.path.normcase(pattern)
        )
    if case_sensitivity in (CaseSensitivity.STRICT, None):
        return fnmatch.fnmatchcase(candidate, pattern)
    if case_sensitivity == CaseSensitivity.EXTENSION_INSENSITIVE:
        # Match the original TuflowPath.glob() implementation: the full
        # filename is case-insensitive, but the filename stem is exact.
        # Comparing suffixes separately wrongly rejects patterns such as
        # "rain_*" that also match "rain_A.CSV".
        return (
            fnmatch.fnmatchcase(candidate.casefold(), pattern.casefold())
            and fnmatch.fnmatchcase(Path(candidate).stem, Path(pattern).stem)
        )
    return fnmatch.fnmatchcase(candidate.casefold(), pattern.casefold())


def _scan_wildcard_patterns(
    patterns: Collection[Path], *, maximum_entries: int,
    case_sensitivity: CaseSensitivity | None,
) -> tuple[
    dict[Path, tuple[Path, ...]], dict[Path, tuple[ValidationStatus, str]], int
]:
    """Scan a directory once for all requested filename patterns in it."""
    found: dict[Path, tuple[Path, ...]] = {}
    failures: dict[Path, tuple[ValidationStatus, str]] = {}
    grouped: dict[Path, list[Path]] = defaultdict(list)
    for pattern in patterns:
        if _has_wildcards(str(pattern.parent)):
            failures[pattern] = (
                "unsupported",
                "Wildcard directories require an explicit traversal policy",
            )
        else:
            grouped[pattern.parent].append(pattern)

    scans = 0
    for parent, siblings in grouped.items():
        matches: dict[Path, list[Path]] = {pattern: [] for pattern in siblings}
        uncertain: set[Path] = set()
        scans += 1
        problem: tuple[ValidationStatus, str] | None = None
        try:
            with os.scandir(parent) as iterator:
                for index, entry in enumerate(iterator):
                    if index >= maximum_entries:
                        raise ValueError("Wildcard directory exceeds bounded scan limit")
                    for pattern in siblings:
                        if _filename_matches(
                            entry.name, pattern.name, case_sensitivity,
                            windows=os.name == "nt",
                        ):
                            matches[pattern].append(parent / entry.name)
                        elif (
                            os.name != "nt"
                            and case_sensitivity is None
                            and _filename_matches(
                                entry.name, pattern.name, CaseSensitivity.FILENAME_INSENSITIVE, windows=False
                            )
                        ):
                            uncertain.add(pattern)
        except FileNotFoundError:
            problem: tuple[ValidationStatus, str] = (
                "missing", "Wildcard parent directory does not exist"
            )
        except (OSError, ValueError) as exc:
            problem = ("unresolved", f"Cannot inspect wildcard directory: {exc}")
        for pattern in siblings:
            if problem is not None:
                failures[pattern] = problem
            elif pattern in uncertain:
                # A partial strict match cannot certify that -cs1/-cs2 would
                # not select other candidate files in the same directory.
                failures[pattern] = (
                    "unsupported",
                    "Linux filename case policy unknown: supply -cs0/-cs1/-cs2",
                )
            elif matches[pattern]:
                found[pattern] = tuple(sorted(matches[pattern]))
            else:
                failures[pattern] = (
                    "missing", "No input files match wildcard pattern"
                )
    return found, failures, scans


def _resolve_literal_case_paths(
    requested: Collection[Path], *, case_sensitivity: CaseSensitivity | None,
    maximum_entries: int,
) -> tuple[
    dict[Path, Path],
    dict[Path, tuple[ValidationStatus, str]],
    int,
]:
    """Apply -cs1/-cs2 to literal names with one bounded scan per directory.

    Exact spellings win without scans; missing literal spellings share an
    invocation-local directory inventory. This deliberately does not relax
    parent directory spelling or stat unrelated files.
    """
    if os.name == "nt" or case_sensitivity not in (CaseSensitivity.EXTENSION_INSENSITIVE, CaseSensitivity.FILENAME_INSENSITIVE):
        return {}, {}, 0

    resolved: dict[Path, Path] = {}
    failures: dict[Path, tuple[ValidationStatus, str]] = {}
    grouped: dict[Path, list[Path]] = defaultdict(list)
    for path in sorted(requested):
        try:
            path.stat()
        except FileNotFoundError:
            grouped[path.parent].append(path)
        except OSError as exc:
            failures[path] = (
                "unresolved", f"Cannot inspect literal input source: {exc}"
            )
        else:
            resolved[path] = path

    scanned = 0
    for parent, siblings in grouped.items():
        scanned += 1
        try:
            names: list[str] = []
            with os.scandir(parent) as entries:
                for index, entry in enumerate(entries):
                    if index >= maximum_entries:
                        raise ValueError(
                            "Literal filename case-resolution directory "
                            "exceeds bounded scan limit"
                        )
                    names.append(entry.name)
        except (FileNotFoundError, NotADirectoryError):
            # The requested path remains missing; do not invent a match.
            for path in siblings:
                resolved[path] = path
            continue
        except (OSError, ValueError) as exc:
            for path in siblings:
                failures[path] = (
                    "unresolved",
                    f"Cannot inspect literal case-resolution directory: {exc}",
                )
            continue

        for path in siblings:
            if case_sensitivity == CaseSensitivity.EXTENSION_INSENSITIVE:
                matching = [
                    name for name in names
                    if Path(name).stem == path.stem
                    and Path(name).suffix.casefold() == path.suffix.casefold()
                ]
            else:
                matching = [
                    name for name in names if name.casefold() == path.name.casefold()
                ]
            if path.name in matching:
                resolved[path] = path
            elif len(matching) == 1:
                resolved[path] = parent / matching[0]
            elif not matching:
                resolved[path] = path  # Ordinary _stat_source reports missing.
            else:
                failures[path] = (
                    "unresolved",
                    f"Ambiguous TUFLOW -cs{case_sensitivity} filename {path.name} in {parent}",
                )
    return resolved, failures, scanned


def _shapefile_companions(path: Path) -> tuple[Path, Path]:
    """Require matching-stem, matching-case-style DBF and SHX files.

    On Linux no case-insensitive lookup is attempted. The same names are
    used by the attribute reader, including uppercase SHP/DBF/SHX sets.
    """
    suffix_case = str.upper if path.suffix.isupper() else str.lower
    return (
        path.with_suffix(suffix_case(".dbf")),
        path.with_suffix(suffix_case(".shx")),
    )


def _stat_source(path: Path) -> tuple[ValidationStatus, str]:
    """Check whether the input is an ordinary readable file."""
    try:
        info = path.stat()
    except FileNotFoundError:
        return "missing", "Input source file does not exist"
    except OSError as exc:
        return "unresolved", f"Cannot inspect input source file: {exc}"
    if not stat.S_ISREG(info.st_mode):
        return "missing", "Expected a regular file, not a directory or other type"
    if path.suffix.casefold() == ".shp":
        for companion in _shapefile_companions(path):
            try:
                counterpart = companion.stat()
            except FileNotFoundError:
                return (
                    "missing",
                    (
                        f"Missing required Shapefile companion {companion.name}; "
                        "the SHP, DBF and SHX names must match"
                    ),
                )
            except OSError as exc:
                return "unresolved", f"Cannot inspect Shapefile companion {companion}: {exc}"
            if not stat.S_ISREG(counterpart.st_mode):
                return "missing", f"Shapefile companion is not a regular file: {companion}"
    if path.suffix.casefold() in {".mif", ".mid"}:
        # The existing MIDAttributes reader needs both files even for a
        # simple Read MI Code that does not reference secondary inputs.
        # Reuse its exact companion resolution, without opening GIS geometry.
        from ._tmf.gis_attr_driver import mapinfo_companion_path

        try:
            companion = mapinfo_companion_path(path)
            companion_info = companion.stat()
        except FileNotFoundError as exc:
            return "missing", f"Missing required MapInfo companion: {exc}"
        except OSError as exc:
            return "unresolved", f"Cannot inspect MapInfo companion for {path}: {exc}"
        if not stat.S_ISREG(companion_info.st_mode):
            return "missing", f"MapInfo companion is not a regular file: {companion}"
    if path.suffix.casefold() == ".gpkg":
        try:
            check_gpkg_safety(path, expected_stat=info)
        except (OSError, RuntimeError) as exc:
            return "unresolved", f"Cannot inspect GeoPackage journal state: {exc}"
    return "present", ""


def _gpkg_contents(path: Path) -> tuple[tuple[str, ...], str]:
    """Compatibility wrapper for the shared safe PyTUFLOW GeoPackage reader."""
    return read_gpkg_layer_names(path)


def _layer_status(
    requested: str, existing: tuple[str, ...], *, implicit: bool = False
) -> tuple[ValidationStatus, str]:
    """Check the selected GeoPackage layer against available names."""
    names = tuple(name.casefold() for name in existing)
    # A GeoPackage filename *stem* is a literal layer requirement, even if
    # spelled "all" or containing [bracket] syntax. TUFLOW's >> all and
    # wildcard rules apply only to explicit layer selectors.
    if implicit:
        return (
            ("present", "") if requested.casefold() in names
            else ("missing", f"GeoPackage layer does not exist: {requested}")
        )
    pattern = requested.casefold().strip()
    if pattern == "all":
        matched = bool(names)
    elif _has_wildcards(pattern):
        matched = any(fnmatch.fnmatchcase(name, pattern) for name in names)
    else:
        matched = pattern in names
    if matched:
        return "present", ""
    return "missing", f"GeoPackage layer does not exist: {requested}"


def _strip_csv_inline_comment(
    line: str, inside_quotes: bool,
) -> tuple[str, bool]:
    """Apply the source reader's ! comment rule without stripping quoted text.

    Preserve physical record boundaries for csv.reader, including headers
    with comments after quoted columns and multiline quoted fields.
    """
    index = 0
    while index < len(line):
        char = line[index]
        if char == '"':
            if inside_quotes and index + 1 < len(line) and line[index + 1] == '"':
                index += 2  # Escaped double quote inside a quoted field.
                continue
            inside_quotes = not inside_quotes
        elif char == "!" and not inside_quotes:
            return line[:index] + ("\n" if line.endswith("\n") else ""), inside_quotes
        index += 1
    return line, inside_quotes


def _csv_records(
    path: Path, requested: Collection[tuple[str, ...]], *,
    lines_limit: int, bytes_limit: int,
) -> tuple[tuple[tuple[str, ...], ...], str]:
    """Read one bounded CSV snapshot, keeping each run's selectors independent.

    Stop after the first candidate header for *each* selector pair. The same
    physical file is opened once, but no other run's requested columns can
    change which header a given run selects. Never parse numeric series values.
    """
    rows: list[tuple[str, ...]] = []
    requirements = frozenset(
        frozenset(name.strip().casefold() for name in pair if name.strip())
        for pair in requested
        if len(pair) == 2 and all(name.strip() for name in pair)
    )
    selected: set[frozenset[str]] = set()
    try:
        with path.open("rb") as source:
            remaining = bytes_limit
            record_started = False
            inside_quotes = False

            def lines() -> Iterator[str]:
                """Yield bounded CSV rows while respecting multiline quoted fields."""
                nonlocal remaining, record_started, inside_quotes
                for number in range(lines_limit):
                    line = source.readline(remaining + 1)
                    if len(line) > remaining:
                        raise ValueError("CSV header exceeds bounded byte limit")
                    if not line:
                        return
                    remaining -= len(line)
                    decoded = line.decode("utf-8-sig" if number == 0 else "utf-8")
                    decoded, inside_quotes = _strip_csv_inline_comment(
                        decoded, inside_quotes
                    )
                    if not record_started and (
                        not decoded.strip() or decoded.lstrip().startswith("!")
                    ):
                        continue
                    record_started = True
                    yield decoded

            for record in csv.reader(lines(), strict=True):
                columns = tuple(column.strip() for column in record)
                if not any(columns):
                    record_started = False
                    continue
                rows.append(columns)
                names = {column.casefold() for column in columns}
                for needed in requirements - selected:
                    if needed & names:
                        selected.add(needed)
                if selected == requirements:
                    break
                record_started = False
        return tuple(rows), ""
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        # Headers found before a subsequent malformed record still count:
        # one unrelated, invalid selection must not invalidate a valid run.
        return tuple(rows), f"Cannot inspect CSV header: {exc}"


def _select_csv_header(
    rows: tuple[tuple[str, ...], ...], required: tuple[str, ...], *,
    lines_limit: int, read_error: str,
) -> tuple[tuple[str, ...], str]:
    """Find each requirement's *own* first matching header record."""
    requested = {name.strip().casefold() for name in required if name.strip()}
    for row in rows:
        if requested.intersection(name.casefold() for name in row):
            return row, ""
    return (), read_error or (
        f"No CSV header containing a required name within first {lines_limit} "
        "physical lines"
    )


def _header_status(
    header: tuple[str, ...], required: tuple[str, ...]
) -> tuple[ValidationStatus, str]:
    """Check that referenced BC CSV columns are unique and present."""
    if len(required) != 2 or any(
        not column.strip() or "<<" in column for column in required
    ):
        return "unsupported", "BC CSV requires two resolved named column selectors"
    counts: dict[str, int] = defaultdict(int)
    for column in header:
        counts[column.casefold()] += 1
    missing = list(dict.fromkeys(
        column for column in required
        if counts[column.strip().casefold()] == 0
    ))
    ambiguous = list(dict.fromkeys(
        column for column in required
        if counts[column.strip().casefold()] > 1
    ))
    if missing or ambiguous:
        problems: list[str] = []
        if missing:
            problems.append(f"Missing BC CSV columns: {', '.join(missing)}")
        if ambiguous:
            problems.append(f"Ambiguous BC CSV columns: {', '.join(ambiguous)}")
        return "unresolved", "; ".join(problems)
    return "present", ""


def validate_dependencies(
    projection: DependencyProjection,
    *,
    options: ValidationOptions | None = None,
    model: TCF | None = None,
    _invocation: _InvocationCache | None = None,
) -> ValidationReport:
    """Inspect explicitly requested TUFLOW inputs without changing the model.

    Source references come from an already-parsed run projection. No TCF
    parsing, variable substitution, simulator execution or model edits occur.
    File results are shared only within this invocation; finding ownership is
    restored independently for each run and source declaration. Supplying the
    parsed model enables TCF projection-based CRS comparison. Without a model,
    selected spatial references are compared with one another.
    """
    policy = options if options is not None else ValidationOptions()
    # Callers of the public direct API get a fresh cache. Only the batch
    # orchestrator shares a cache between its initial and final passes.
    cache = _invocation if _invocation is not None else _InvocationCache()
    if not projection.runs:
        raise ValueError("At least one run is required for input validation")
    requirements, failures = _requirements(projection)

    def finding(
        item: _Requirement,
        status: ValidationStatus,
        kind: ValidationKind,
        path: Path,
        detail: str = "",
    ) -> ValidationFinding:
        """Construct a finding with source-command attribution."""
        return ValidationFinding(
            item.run_index,
            item.flags,
            status,
            kind,
            path,
            detail,
            (path.stem if item.implicit_gpkg_layer else item.layer)
            if kind == "layer" else (item.layer if kind == "raster_metadata" else None),
            item.origin,
            item.input_uuid,
            item.command_index,
            item.owner_control_file,
            item.database_kind,
            item.path if path != item.path else None,
            item.csv_columns if kind == "csv_header" else None,
        )

    # Gather physical results by *declaration identity*, then emit in
    # original projection/requirement order. Up-front errors must not move a
    # later simulation ahead of a successful earlier simulation.
    by_requirement: dict[int, list[ValidationFinding]] = {
        id(item): [] for item in requirements
    }

    def add(item: _Requirement, result: ValidationFinding) -> None:
        """Associate a finding with its source requirement."""
        by_requirement[id(item)].append(result)

    def ordered_findings() -> tuple[ValidationFinding, ...]:
        """Preserve source and run ordering in the final report."""
        by_run: dict[int, list[ValidationFinding]] = defaultdict(list)
        for item in requirements:
            by_run[item.run_index].extend(by_requirement[id(item)])
        # Incomplete run/activation findings have no attached requirement.
        # Keep them in their original run, after its available source records.
        for error in failures:
            by_run[error.run_index].append(error)
        return tuple(
            item
            for run in projection.runs
            for item in by_run.get(run.index, ())
        )

    # Explicitly disabled inspection is never treated as validation success.
    # In particular, do not scandir wildcard directories when file checks
    # were disabled by the caller.
    if not policy.check_files:
        for item in requirements:
            add(
                item,
                finding(item, "unsupported", "file", item.path,
                        "Physical input-file inspection was disabled"),
            )
        return ValidationReport(
            ordered_findings(),
            len(projection.runs), 0, 0, 0, 0,
        )

    globs = {
        item.path for item in requirements
        if _has_wildcards(str(item.path))
        and not item.unresolved and "<<" not in str(item.path)
    }
    unseen_globs = globs - cache.wildcard_matches.keys() - cache.wildcard_failures.keys()
    expansions, glob_errors, glob_scans = _scan_wildcard_patterns(
        unseen_globs, maximum_entries=policy.maximum_directory_entries,
        case_sensitivity=policy.case_sensitivity,
    )
    cache.wildcard_matches.update(expansions)
    cache.wildcard_failures.update(glob_errors)
    literals = {
        item.path for item in requirements
        if not item.unresolved
        and "<<" not in str(item.path)
        and not _has_wildcards(str(item.path))
    }
    unseen_literals = literals - cache.literal_paths.keys() - cache.literal_failures.keys()
    case_resolved, case_errors, case_scans = _resolve_literal_case_paths(
        unseen_literals,
        case_sensitivity=policy.case_sensitivity,
        maximum_entries=policy.maximum_directory_entries,
    )
    cache.literal_paths.update(case_resolved)
    cache.literal_failures.update(case_errors)
    cache.directories_scanned += glob_scans + case_scans
    expansions, glob_errors = cache.wildcard_matches, cache.wildcard_failures
    case_resolved, case_errors = cache.literal_paths, cache.literal_failures
    scan_count = cache.directories_scanned
    concrete: list[tuple[_Requirement, Path]] = []
    for item in requirements:
        if item.unresolved or "<<" in str(item.path):
            add(item,
                finding(item, "unresolved", "file", item.path, "Unresolved TUFLOW variables")
            )
        elif item.path in glob_errors:
            status, detail = glob_errors[item.path]
            add(item, finding(item, status, "wildcard", item.path, detail))
        elif item.path in case_errors:
            status, detail = case_errors[item.path]
            add(item, finding(item, status, "file", item.path, detail))
        else:
            for path in expansions.get(item.path, (item.path,)):
                # Each distinct Linux literal was resolved through the one
                # bounded shared directory scan above. Never silently enumerate
                # an unbounded network directory inside an individual run.
                if path == item.path and not _has_wildcards(str(path)):
                    path = case_resolved.get(path, path)
                    if os.name != "nt" and policy.case_sensitivity is None:
                        try:
                            exists = path.exists()
                        except OSError as exc:
                            add(item, finding(
                                item, "unresolved", "file", path,
                                f"Cannot inspect input source file: {exc}",
                            ))
                            continue
                        if not exists:
                            add(item, finding(
                                item, "unsupported", "file", path,
                                "Linux filename case policy unknown: supply -cs0/-cs1/-cs2",
                            ))
                            continue
                concrete.append((item, path))

    gpkg_paths: set[Path] = set()
    csv_requests: dict[Path, set[tuple[str, ...]]] = defaultdict(set)
    raster_requests: dict[Path, set[str | None]] = defaultdict(set)
    vector_requests: dict[Path, set[tuple[str | None, bool]]] = defaultdict(set)
    for item, path in concrete:
        if (
            policy.check_gpkg_layers
            and item.layer is not None
            and path.suffix.casefold() == ".gpkg"
        ):
            gpkg_paths.add(path)
        if (
            policy.check_bc_csv_headers
            and item.csv_columns is not None
            and len(item.csv_columns) == 2
            and path.suffix.casefold() == ".csv"
        ):
            csv_requests[path].add(item.csv_columns)
        if (policy.check_raster_metadata or policy.check_crs) and item.requires_raster_metadata_scan:
            raster_requests[path].add(item.layer)
        if policy.check_crs and item.requires_vector_crs_scan:
            vector_requests[path].add((item.layer, item.implicit_gpkg_layer))
    files = {path for _, path in concrete}

    def inspect(path: Path) -> tuple[Path, _Inspection]:
        """Extend the same-invocation file snapshot with newly requested metadata."""
        previous = cache.inspected.get(path)
        if previous is None:
            status, detail = _stat_source(path)
            if status != "present":
                return path, _Inspection(status, detail)
        elif previous.status != "present":
            return path, previous
        else:
            status, detail = previous.status, previous.detail

        layers = previous.layers if previous is not None else ()
        layer_error = previous.layer_error if previous is not None else ""
        if path in gpkg_paths and not (previous and previous.gpkg_examined):
            layers, layer_error = _gpkg_contents(path)

        # The primary pass requests only file status and GPKG layers. All
        # CSV/raster/CRS selections are known together in the final pass, so
        # metadata needs neither a partial-result merge nor selector upgrades.
        csv_records: tuple[tuple[str, ...], ...] = ()
        csv_error = ""
        if path in csv_requests:
            csv_records, csv_error = _csv_records(
                path,
                csv_requests[path],
                lines_limit=policy.maximum_header_lines,
                bytes_limit=policy.maximum_header_bytes,
            )
        raster_results: tuple[tuple[str | None, ValidationStatus, str], ...] = ()
        raster_crs: tuple[tuple[str | None, str | None], ...] = ()
        subdataset_opens = 0
        if path in raster_requests:
            from ._raster_metadata import inspect_raster_headers

            if policy.check_crs:
                checks, subdataset_opens, crs_by_selector = inspect_raster_headers(
                    path,
                    raster_requests[path],
                    maximum_subdatasets=policy.maximum_raster_subdatasets,
                    include_crs=True,
                )
                raster_crs = tuple(crs_by_selector.items())
            else:
                checks, subdataset_opens = inspect_raster_headers(
                    path,
                    raster_requests[path],
                    maximum_subdatasets=policy.maximum_raster_subdatasets,
                )
            raster_results = tuple(
                (selector, *checks[selector])
                for selector in sorted(
                    checks, key=lambda name: (name is not None, name or "")
                )
            )
        vector_crs: tuple[tuple[tuple[str | None, bool], tuple[tuple[str | None, str | None, str], ...]], ...] = ()
        if path in vector_requests:
            from ._crs_validation import inspect_vector_crs

            vector_crs = tuple(inspect_vector_crs(path, vector_requests[path]).items())

        return path, _Inspection(
            status,
            detail,
            layers,
            layer_error,
            csv_records,
            csv_error,
            bool(path in gpkg_paths or (previous and previous.gpkg_examined)),
            path in csv_requests,
            raster_results=raster_results,
            raster_examined=path in raster_requests,
            raster_subdatasets_opened=subdataset_opens,
            raster_crs=raster_crs,
            vector_crs=vector_crs,
            crs_examined=bool(policy.check_crs and (path in raster_requests or path in vector_requests)),
        )

    ordered = sorted(files)
    if policy.io_workers == 1:
        examined = dict(inspect(path) for path in ordered)
    else:
        with ThreadPoolExecutor(max_workers=policy.io_workers) as executor:
            examined = dict(executor.map(inspect, ordered))
    cache.inspected.update(examined)

    for item, path in concrete:
        if not policy.check_files:
            continue
        info = examined[path]
        add(item, finding(item, info.status, "file", path, info.detail))
        if info.status != "present":
            continue
        if policy.check_raster_metadata and item.requires_raster_metadata_scan:
            metadata = {
                selector: (status, detail)
                for selector, status, detail in info.raster_results
            }
            status, detail = metadata[item.layer]
            add(item, finding(item, status, "raster_metadata", path, detail))
        if (
            policy.check_gpkg_layers and item.layer is not None
            and path.suffix.casefold() == ".gpkg"
        ):
            if info.layer_error:
                add(item,
                    finding(item, "unresolved", "layer", path, info.layer_error)
                )
            else:
                selected_layer = (
                    path.stem if item.implicit_gpkg_layer else item.layer
                )
                status, detail = _layer_status(
                    selected_layer, info.layers, implicit=item.implicit_gpkg_layer
                )
                add(item, finding(item, status, "layer", path, detail))
        if policy.check_bc_csv_headers and (
            item.csv_columns is not None
            or (
                item.secondary_source
                and item.database_kind == "bc"
                and path.suffix.casefold() == ".csv"
            )
        ):
            if item.csv_columns is None:
                if path.suffix.casefold() == ".csv":
                    add(item,
                        finding(
                            item, "unsupported", "csv_header", path,
                            "Parser did not provide BC CSV column requirements",
                        )
                    )
                continue
            if not item.csv_columns:
                continue  # FEWS/nonordinary CSV: no ordinary named selectors.
            if path.suffix.casefold() != ".csv":
                add(item,
                    finding(
                        item, "unsupported", "csv_header", path,
                        "BC column selectors require an ordinary Source CSV",
                    )
                )
            elif len(item.csv_columns) != 2 or any(
                not column.strip() or "<<" in column
                for column in item.csv_columns
            ):
                status, detail = _header_status((), item.csv_columns)
                add(item,
                    finding(item, status, "csv_header", path, detail)
                )
            else:
                header, header_error = _select_csv_header(
                    info.csv_records, item.csv_columns,
                    lines_limit=policy.maximum_header_lines,
                    read_error=info.csv_error,
                )
                if header_error:
                    status, detail = "unresolved", header_error
                else:
                    status, detail = _header_status(
                        header, item.csv_columns
                    )
                add(item,
                    finding(item, status, "csv_header", path, detail)
                )

    # Compare selected spatial inputs only after all physical headers/layers
    # have been checked. The reference is the TCF CRS (when known) or the
    # first selected source with a valid CRS in dependency/run order.
    if policy.check_crs:
        from ._crs_validation import crs_label, parse_crs, same_crs

        candidates: list[
            tuple[_Requirement, Path, str | None, str | None, str]
        ] = []
        for item, path in concrete:
            info = examined[path]
            if info.status != "present":
                continue
            if item.requires_raster_metadata_scan:
                raster_state = {
                    selector: status
                    for selector, status, _detail in info.raster_results
                }
                # A corrupt header already produces a normal failure when
                # enabled; it must not also produce a misleading CRS mismatch.
                if raster_state.get(item.layer) != "present":
                    # With headers explicitly disabled, an unreadable raster
                    # still cannot provide a trustworthy CRS. Warn rather than
                    # silently declaring its CRS consistent or making the
                    # header problem a blocking issue.
                    if not policy.check_raster_metadata:
                        detail = next((
                            message for selector, _status, message in info.raster_results
                            if selector == item.layer
                        ), "Raster metadata is unavailable")
                        candidates.append((
                            item, path, item.layer, None,
                            f"Cannot inspect raster CRS: {detail}",
                        ))
                    continue
                raster_crs = dict(info.raster_crs)
                candidates.append((
                    item, path, item.layer, raster_crs.get(item.layer),
                    "Raster has no declared CRS",
                ))
            elif item.requires_vector_crs_scan:
                layer_results = dict(info.vector_crs)
                for layer, raw_crs, detail in layer_results.get(
                    (item.layer, item.implicit_gpkg_layer), ()
                ):
                    if "was not found" in detail:
                        continue  # Existing layer validation reports this.
                    candidates.append((
                        item, path, layer, raw_crs,
                        detail or "Vector layer has no declared CRS",
                    ))

        def projection_role(name: str) -> str | None:
            """Classify selected projection declarations, excluding check commands."""
            name = name.upper()
            if "PROJECTION" not in name or "CHECK" in name:
                return None
            return "tif" if "TIF" in name else "gis"

        # Resolved dependency records already contain the active source paths,
        # selectors and source order for each run. Reuse their inspected CRS;
        # model.config alone is not scenario-specific (it scans all scopes).
        source_projections = {
            (item.run_index, item.command_index): value
            for item, _path, _layer, value, _error in candidates
            if projection_role(item.origin) is not None
        }
        references: dict[int, tuple[CRS | None, str]] = {}
        parsed_cache: dict[str, tuple[CRS | None, str | None]] = {}
        label_cache: dict[int, str] = {}
        compared_cache: dict[tuple[int, int], bool] = {}

        def label(value: CRS) -> str:
            """Avoid repeated PROJ authority lookups for shared run references."""
            if id(value) not in label_cache:
                label_cache[id(value)] = crs_label(value)
            return label_cache[id(value)]

        def equivalent(left: CRS, right: CRS) -> bool:
            """Reuse each semantic comparison across all selected simulations."""
            key = id(left), id(right)
            if key not in compared_cache:
                compared_cache[key] = same_crs(left, right)
            return compared_cache[key]

        def parsed_crs(value: str) -> tuple[CRS | None, str | None]:
            """Parse each source/reference definition once for this invocation."""
            if value not in parsed_cache:
                try:
                    parsed_cache[value] = (parse_crs(value), None)
                except (TypeError, ValueError) as exc:
                    parsed_cache[value] = (None, str(exc))
            return parsed_cache[value]

        for run in projection.runs:
            if run.error is not None:
                continue
            declared: dict[str, str | None] = {}
            for command in run.ordered_inputs:
                role = projection_role(command.command_name)
                if role is None:
                    continue
                if command.reference_count:
                    value = source_projections.get((run.index, command.command_index))
                else:
                    # Inline authority/WKT declarations have no physical source.
                    # Unexpanded or invalid values remain advisory parse failures.
                    value = command.command_text.partition("==")[2].split("!", 1)[0].strip()
                declared[role] = value
            if not run.ordered_inputs and model is not None:
                # Direct projections without command records can only supply a
                # model-level reference. Full batch inventories use active commands.
                declared = {
                    "gis": getattr(model.config, "projection_wkt", "") or None,
                    "tif": getattr(model.config, "tif_projection", "") or None,
                }
                declared = {role: value for role, value in declared.items() if value}

            def warn_reference(detail: str) -> None:
                failures.append(
                    ValidationFinding(
                        run.index,
                        run.flags,
                        "unresolved",
                        "crs",
                        getattr(model, "fpath", None),
                        detail,
                        origin="TCF Projection",
                        severity="warning",
                    )
                )

            gis_raw, tif_raw = declared.get("gis"), declared.get("tif")
            raw = gis_raw or tif_raw
            reference, description = None, ""
            if raw:
                reference, error = parsed_crs(raw)
                if error:
                    warn_reference(f"Cannot interpret TCF projection: {error}")
                elif reference is not None:
                    description = f"TCF projection {label(reference)}"
            elif declared:
                warn_reference(
                    "A TCF projection was declared but its CRS could not be resolved; "
                    "checking selected spatial inputs against one another instead"
                )
            elif model is not None or run.ordered_inputs:
                # The selected run has no active projection declaration. This
                # remains a warning even when all selected input CRSs agree:
                # agreement is not a substitute for a TCF-defined CRS.
                warn_reference(
                    "No GIS Projection or TIF Projection is defined in the TCF "
                    "for this run; comparing selected spatial input CRSs where possible"
                )
            if gis_raw and tif_raw:
                gis_crs, _gis_error = parsed_crs(gis_raw)
                tif_crs, tif_error = parsed_crs(tif_raw)
                if tif_error and raw != tif_raw:
                    warn_reference(f"Cannot interpret TCF TIF projection: {tif_error}")
                if gis_crs is not None and tif_crs is not None and not equivalent(gis_crs, tif_crs):
                    warn_reference(
                        f"TCF GIS projection {label(gis_crs)} and TIF projection {label(tif_crs)} differ"
                    )
            references[run.index] = reference, description

        parsed: list[tuple[_Requirement, Path, str | None, CRS | None, str]] = []
        # A shared source can occur in thousands of selected runs. Parse any
        # identical CRS definition once per validation invocation, without a
        # persistent cache that could become stale after a model edit.
        for item, path, layer, value, error in candidates:
            if projection_role(item.origin) is not None:
                continue
            crs = None
            if value:
                crs, parse_error = parsed_crs(value)
                if parse_error:
                    error = f"Cannot interpret input CRS: {parse_error}"
            parsed.append((item, path, layer, crs, error))

        # With no usable projection, choose a baseline within each simulation;
        # unrelated scenarios must not establish one another's expected CRS.
        for item, path, layer, crs, _error in parsed:
            if references[item.run_index][0] is None and crs is not None:
                references[item.run_index] = (
                    crs,
                    f"selected input {path}" + (f" >> {layer}" if layer else "") + f" ({label(crs)})",
                )

        for item, path, layer, crs, detail in parsed:
            reference, reference_description = references[item.run_index]
            if crs is None:
                detail = (
                    f"{detail}; cannot confirm consistency with "
                    f"{reference_description or 'other spatial inputs'}"
                )
            elif reference is not None:
                if equivalent(crs, reference):
                    continue
                detail = (
                    f"Input CRS {label(crs)} differs from "
                    f"{reference_description}"
                )
            else:
                continue
            add(item, replace(
                finding(item, "unresolved", "crs", path, detail),
                layer=layer, severity="warning",
            ))

    return ValidationReport(
        ordered_findings(),
        len(projection.runs),
        len(examined),
        sum(result.gpkg_examined for result in examined.values()),
        sum(result.csv_examined for result in examined.values()),
        scan_count,
        sum(result.raster_examined for result in examined.values()),
        sum(result.raster_subdatasets_opened for result in examined.values()),
        sum(result.crs_examined for result in examined.values()),
    )
