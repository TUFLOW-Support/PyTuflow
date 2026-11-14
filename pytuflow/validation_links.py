"""Conservative second-stage discovery of GIS feature-linked file inputs.

This module never changes original parsed commands or the immutable fragment
projection. A successful physical base-file/layer check is prerequisite to
reading attribute tables. Every supported attribute layer is scanned at most
once per distinct physical file/selector within this invocation.

Unsupported providers, schemas and unmatched curve/BC identifiers fail closed.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from ._tmf.cf.cf_run_state import prepare_run_context
from ._tmf.context import Context
from ._tmf.db.bc_dbase import bc_database_entry_name
from ._tmf.deferred_database import _cached_database_path_key, _expanded
from ._tmf.dependency_records import BatchDependencyRun, BatchInputReference
from ._tmf.file_reference import FileReference, _cached_path_matches
from ._tmf.gis import tuflow_type_requires_feature_iter
from .validation import (
    ValidationFinding,
    ValidationReport,
    _implicit_gpkg_layer,
)
from .validation_gis import (
    AttributeInspection,
    inspect_gis_attribute_sources,
)

if TYPE_CHECKING:
    from ._tmf.cf.tcf import TCF
    from ._tmf.fragment_dependencies import FragmentBatchResult


@dataclass(frozen=True, slots=True)
class ExtendedProjection:
    """Store linked inputs without mutating the original run projection."""

    runs: tuple[BatchDependencyRun, ...]


@dataclass(frozen=True, slots=True)
class GISExpansion:
    """Return discovered GIS sources, findings and scan counts."""

    projection: ExtendedProjection
    findings: tuple[ValidationFinding, ...]
    linked_sources: int
    gis_files_scanned: int


def _linked_reference(parent: BatchInputReference, path: Path) -> BatchInputReference:
    """Attribute a GIS-linked source to its original command."""
    expression = str(path)
    source = parent.reference
    # These paths come from recognised file-valued GIS attributes, without a
    # Command instance to classify their type. Only known raster suffixes can
    # receive a raster role here; unknown/extensionless linked grids remain
    # ordinary physical-file checks, not unverified Rasterio successes.
    linked_raster = path.suffix.casefold() in {
        ".tif", ".tiff", ".asc", ".flt", ".img", ".vrt", ".nc", ".nc4", ".cdf",
    }
    from ._crs_validation import is_vector_source

    file = FileReference(
        base_directory=path.parent,
        expanded_value=expression,
        path_pattern=path,
        layer_pattern=None,
        origin=f"GIS attribute of {source.origin}",
        requires_directory_scan=any(character in path.name for character in "*?["),
        requires_layer_scan=False,
        requires_attribute_scan=False,
        requires_database_scan=False,
        requires_raster_metadata_scan=linked_raster,
        requires_vector_crs_scan=(not linked_raster and is_vector_source(path)),
        unresolved_variables=tuple(re.findall(r"<<[^<>]+>>", expression)),
    )
    return BatchInputReference(
        input_uuid=parent.input_uuid,
        command_index=parent.command_index,
        owner_control_file=parent.owner_control_file,
        line_number=parent.line_number,
        reference=file,
    )


def _gis_read_role(command_name: str) -> str | None:
    """Classify supported TUFLOW GIS/MapInfo read-command spelling.

    The existing Command.is_read_gis() accepts READ GIS, READ MI, READ MID
    and READ ROWCOL. The immutable command record contains only its name,
    not its original Command object, so use its lexical READ form here.
    """
    words = command_name.casefold().split()
    if (
        len(words) < 2
        or words[0] != "read"
        or words[1] not in {"gis", "mi", "mid", "rowcol"}
    ):
        return None
    # RF triangulation uses geometry only: TUFLOW ignores every attribute.
    # Keep file/layer/companion checks, but never select BC Names from triangles.
    if words[2:] == ["rf", "triangle"]:
        return "geometry"
    return "bc" if len(words) > 2 and words[2] in {"bc", "sa", "rf"} else "gis"


def _pending_source_kinds(run: BatchDependencyRun) -> frozenset[str]:
    """Candidate database rows needing active GIS feature ID selection.

    An unused BC Source row or pit/curve key is not automatically an input
    file required by a run. Keep its original syntactic record unchanged; only
    the physical-check projection defers these candidate rows.
    """
    commands = tuple(
        command.command_name.casefold()
        for command in run.ordered_inputs
    )
    kinds: set[str] = set()
    if any(_gis_read_role(name) == "bc" for name in commands):
        kinds.add("bc")
    # Curve sources are selected by GIS Q/P and pit identifiers, rather than
    # required unconditionally by declaring a lookup database.
    if any(_gis_read_role(name) is not None for name in commands):
        kinds.update(("depth_discharge", "pit_inlet"))
    return frozenset(kinds)


def pending_physical_projection(projection: FragmentBatchResult) -> ExtendedProjection:
    """Exclude potentially unused BC/curve rows from initial physical checks.

    The linked-feature pass must subsequently certify each selected GIS layer
    and add back only the database Source rows referenced by its actual IDs.
    """
    return ExtendedProjection(
        tuple(
            replace(
                run,
                database_sources=tuple(
                    source for source in run.database_sources
                    if source.database_kind not in _pending_source_kinds(run)
                ),
            )
            for run in projection.runs
        )
    )


def _resolved_bc_inline_constant(
    model: TCF,
    run: BatchDependencyRun,
    activation_uuid: str,
    database_path: Path,
    database_key: str,
    *,
    original_flags: str | dict[str, str],
    run_contexts: dict[int, Context],
    cached_databases: dict[tuple[str, str], object],
) -> bool:
    """Classify a selected BC constant using its active run context.

    Resolve the cached BC database row through the same Context translation
    used for deferred database sources. This preserves Set Variable values
    without reopening the source CSV or constructing a new run-state tree.
    """
    identity = (activation_uuid, _cached_database_path_key(database_path))
    database = cached_databases.get(identity)
    if database is None:
        candidates = []
        for inp in model.find_input(lhs="bc database", recursive=True):
            if str(inp.uuid) != activation_uuid:
                continue
            candidates.extend(zip(inp.cf, getattr(inp, "_database_loaded_paths", ()), strict=True))
        matches = [db for db, original in candidates
                   if _cached_database_path_key(original) == identity[1]]
        if not matches:
            matches = [db for db, original in candidates
                       if _cached_path_matches(Path(original), database_path,
                                               model.config.case_sensitivity)]
        if len(matches) != 1:
            raise ValueError(
                f"Expected one cached active BC database, found {len(matches)}"
            )
        database = matches[0]
        cached_databases[identity] = database

    frame = database.df
    selected = [
        (key, record) for key, record in frame.iterrows()
        if str(key).strip().casefold() == database_key
    ]
    if len(selected) != 1:
        return False
    row_key, record = selected[0]
    context = run_contexts.get(run.index)
    if context is None:
        context = Context(original_flags, config=model.config)
        prepare_run_context(model, context)
        run_contexts[run.index] = context

    columns = list(frame.columns)
    source_column = next(
        (name for name in columns if str(name).strip().casefold() == "source"),
        None,
    )
    if source_column is None:
        raise ValueError("Active BC database lacks a Source column")
    source = _expanded(
        record[source_column], context, kind="bc", row=row_key
    )
    if source:
        value = source
    else:
        value_column = next(
            (name for name in columns if str(name).strip().casefold()
             in ("column 2", "value", "column 2 or value")),
            None,
        )
        if value_column is None:
            raise ValueError("Active BC database lacks Column 2 for constants")
        value = _expanded(
            record[value_column], context, kind="bc", row=row_key
        )
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def extend_gis_dependencies(
    projection: FragmentBatchResult,
    checked: ValidationReport,
    model: TCF,
    run_flags: tuple[str | dict[str, str], ...],
) -> GISExpansion:
    """Add validated primary GIS attribute link candidates to the projection.

    Existing model/fragment records are never mutated. This prepares a second
    physical check on the union of original and attribute-derived sources, not
    an implicit lookup during scenario/event evaluation.
    """
    sources: dict[tuple[int, str, int], list[BatchInputReference]] = defaultdict(list)
    selected_bc: dict[int, set[tuple[str, str]]] = defaultdict(set)
    selected_curves: dict[int, set[tuple[str, str]]] = defaultdict(set)
    scan_requests: set[tuple[Path, str, bool]] = set()
    needs: list[tuple[BatchDependencyRun, BatchInputReference, Path, str, bool, bool]] = []
    findings: list[ValidationFinding] = []

    # File existence/layer validation has already resolved wildcard filename
    # patterns, so GIS attribute scanning never probes a missing primary file.
    by_parent: dict[tuple[int, str, int, str, Path], list[Path]] = defaultdict(list)
    for item in checked.findings:
        if (
            item.kind == "file"
            and item.status == "present"
            and item.path is not None
        ):
            key = (
                item.run_index, item.input_uuid, item.command_index,
                item.origin, item.source_pattern or item.path,
            )
            by_parent[key].append(item.path)

    for run in projection.runs:
        commands = {
            command.command_index: command.command_name.casefold()
            for command in run.ordered_inputs
        }
        if run.error is not None:
            continue
        for link in run.input_references:
            original = link.reference
            layer_name = str(original.layer_pattern or original.path_pattern.stem)
            role = _gis_read_role(commands.get(link.command_index, ""))
            if role == "geometry":
                continue
            bc_command = role == "bc"
            known_bc_layer = bool(
                re.match(r"^(?:[12]d_bc|2d_(?:sa|rf))_", layer_name, flags=re.IGNORECASE)
            )
            flexible_bc_layer = (
                original.layer_pattern is not None
                and (layer_name.casefold() == "all"
                     or any(char in layer_name for char in "*?["))
            )
            if bc_command and not (known_bc_layer or flexible_bc_layer):
                findings.append(
                    ValidationFinding(
                        run_index=run.index,
                        flags=run.flags,
                        status="unresolved",
                        kind="attribute",
                        path=original.path_pattern,
                        detail="Unsupported GIS BC/SA/RF layer schema",
                        layer=layer_name,
                        origin=original.origin,
                        input_uuid=link.input_uuid,
                        command_index=link.command_index,
                        owner_control_file=link.owner_control_file,
                    )
                )
                continue
            is_bc = bc_command
            if not original.requires_attribute_scan and not is_bc:
                continue
            key = (
                run.index,
                link.input_uuid,
                link.command_index,
                original.origin,
                original.path_pattern,
            )
            for path in by_parent.get(key, []):
                implicit = _implicit_gpkg_layer(original)
                selector = (
                    path.stem if implicit or original.layer_pattern is None
                    else str(original.layer_pattern)
                )
                # A wildcard filename/layer is conservatively labelled as
                # an attribute candidate by FileReference, even when its
                # concrete result is a plain 2d_code/2d_mat layer. Do not
                # require GIS feature-table metadata for such input layers.
                # Explicit wildcard/'all' selectors may contain linked 1D
                # layers, so the inspector must check their concrete matches.
                known_file_fields = bool(
                    tuflow_type_requires_feature_iter(selector)
                )
                explicit_wildcard = (
                    not implicit
                    and original.layer_pattern is not None
                    and (any(char in selector for char in "*?[")
                         or selector.casefold() == "all")
                )
                if (
                    original.requires_table_link_scan
                    and not known_file_fields
                ):
                    findings.append(
                        ValidationFinding(
                            run_index=run.index,
                            flags=run.flags,
                            status="unresolved",
                            kind="attribute",
                            path=path,
                            detail="Unclassified GIS table-link schema cannot be certified",
                            layer=selector,
                            origin=original.origin,
                            input_uuid=link.input_uuid,
                            command_index=link.command_index,
                            owner_control_file=link.owner_control_file,
                        )
                    )
                    continue
                if not (
                    known_file_fields or is_bc
                    or original.requires_table_link_scan
                    or explicit_wildcard
                ):
                    continue
                request = (path, selector, implicit)
                scan_requests.add(request)
                needs.append((run, link, path, selector, implicit, is_bc))

    if not needs:
        return GISExpansion(
            pending_physical_projection(projection),
            tuple(findings), 0, 0,
        )

    inspected, count = inspect_gis_attribute_sources(scan_requests)
    run_contexts: dict[int, Context] = {}
    cached_databases: dict[tuple[str, str], object] = {}

    for run, link, path, selector, implicit, is_bc in needs:
        result: AttributeInspection = inspected[(path, selector, implicit)]

        def issue(
            detail: str,
            *,
            run: BatchDependencyRun = run,
            link: BatchInputReference = link,
            path: Path = path,
            selector: str = selector,
        ) -> None:
            """Record an unresolved attribute reference for the selected run."""
            findings.append(
                ValidationFinding(
                    run_index=run.index,
                    flags=run.flags,
                    status="unresolved",
                    kind="attribute",
                    path=path,
                    detail=detail,
                    layer=selector,
                    origin=link.reference.origin,
                    input_uuid=link.input_uuid,
                    command_index=link.command_index,
                    owner_control_file=link.owner_control_file,
                    database_kind=link.reference.database_kind,
                )
            )

        if result.status != "present":
            issue(result.detail or "Cannot certify GIS attribute dependencies")
            continue
        if is_bc and not result.bc_layer_selected:
            issue(
                "GIS BC/SA/RF selector contains no recognised BC layer; "
                "candidate source rows cannot be certified"
            )
            continue

        key = (run.index, link.input_uuid, link.command_index)
        sources[key].extend(_linked_reference(link, item) for item in result.sources)

        # Inlet and depth-discharge IDs are not file paths. They must resolve
        # through the selected cached parser database; never invent a path.
        for identifiers, kind in (
            (result.network_identifiers, "depth_discharge"),
            (result.pit_identifiers, "pit_inlet"),
        ):
            if not identifiers:
                continue
            for identifier in identifiers:
                matching = [
                    source for source in run.database_sources
                    if source.database_kind == kind
                    and source.entry_name.casefold() == identifier.casefold()
                ]
                if len(matching) != 1:
                    issue(
                        f"Expected one {kind} source for {identifier!r}, "
                        f"found {len(matching)}"
                    )
                else:
                    selected_curves[run.index].add(
                        (kind, identifier.casefold())
                    )

        if is_bc and result.bc_identifiers:
            declarations = [
                a for a in run.database_activations
                if a.database_kind == "bc"
            ]
            # The run projection already filters inactive scenario/event
            # declarations. A sole BC database is model-wide, including when
            # a nested BCF is read before its declaration. Multiple databases
            # still require an unambiguous preceding activation.
            activations = declarations if len(declarations) == 1 else [
                a for a in declarations if a.sequence < link.command_index
            ]
            if not activations:
                issue("GIS BC/SA/RF layer has no preceding active BC Database")
                continue
            active = max(activations, key=lambda a: a.sequence)
            for identifier in result.bc_identifiers:
                database_key = str(bc_database_entry_name(identifier)).casefold()
                matched = [
                    source for source in run.database_sources
                    if source.database_kind == "bc"
                    and source.input_uuid == active.input_uuid
                    and source.entry_name.casefold() == database_key
                ]
                if len(matched) == 1:
                    selected_bc[run.index].add(
                        (active.input_uuid, database_key)
                    )
                    continue
                if len(matched) > 1:
                    issue(f"Ambiguous active BC Source: {identifier!r}")
                    continue
                try:
                    if _resolved_bc_inline_constant(
                        model,
                        run,
                        active.input_uuid,
                        active.database_path,
                        database_key,
                        original_flags=run_flags[run.index],
                        run_contexts=run_contexts,
                        cached_databases=cached_databases,
                    ):
                        continue
                except (OSError, ValueError, TypeError, RuntimeError) as exc:
                    issue(f"Cannot classify active BC constant {identifier!r}: {exc}")
                    continue
                issue(
                    f"Active BC Database has no resolvable Source or inline "
                    f"constant for {identifier!r}"
                )

    extended: list[BatchDependencyRun] = []
    added = 0
    for run in projection.runs:
        seen: set[tuple[object, ...]] = set()
        links: list[BatchInputReference] = []
        for link in run.input_references:
            key = (run.index, link.input_uuid, link.command_index)
            for extra in sources.get(key, ()):
                fingerprint = (extra.input_uuid, extra.command_index,
                               extra.reference.path_pattern, extra.reference.layer_pattern)
                if fingerprint not in seen:
                    seen.add(fingerprint)
                    links.append(extra)
        added += len(links)
        extended.append(
            replace(
                run,
                input_references=run.input_references + tuple(links),
                file_references=run.file_references
                + tuple(link.reference for link in links),
                database_sources=tuple(
                    source for source in run.database_sources
                    if (
                        source.database_kind not in _pending_source_kinds(run)
                        or (
                            source.database_kind == "bc"
                            and (source.input_uuid, source.entry_name.casefold())
                            in selected_bc[run.index]
                        )
                        or (
                            source.database_kind in ("depth_discharge", "pit_inlet")
                            and (source.database_kind, source.entry_name.casefold())
                            in selected_curves[run.index]
                        )
                    )
                ),
            )
        )

    return GISExpansion(
        ExtendedProjection(tuple(extended)), tuple(findings), added, count
    )
