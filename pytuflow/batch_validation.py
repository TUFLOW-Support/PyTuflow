"""Explicit batch dependency collection and physical input validation for TUFLOW.

This module is the orchestration boundary; ordinary TCF parsing, Context and
single-run semantics remain unchanged. A batch uses one parsed TCF and the
existing immutable fragment collector before checking distinct physical files,
GeoPackage layers and ordinary BC CSV headers. It never launches TUFLOW.

Pass actual scheduled flags rather than generating a Cartesian product from
scenario/event names. Syntactic collection alone never opens physical inputs;
the separate validation phase is explicitly requested here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from os import PathLike
from time import perf_counter
from typing import TYPE_CHECKING

from .validation import (
    ValidationFinding,
    ValidationOptions,
    ValidationReport,
    validate_dependencies,
)
from .validation_links import extend_gis_dependencies, pending_physical_projection

if TYPE_CHECKING:
    from ._tmf.cf.tcf import TCF
    from ._tmf.fragment_dependencies import FragmentBatchResult


@dataclass(frozen=True, slots=True)
class BatchValidationResult:
    """One immutable per-run dependency inventory and its physical findings."""

    dependencies: FragmentBatchResult
    validation: ValidationReport
    parse_seconds: float
    collection_seconds: float
    inspection_seconds: float
    gis_sources_added: int = 0
    gis_files_scanned: int = 0

    @property
    def passed(self) -> bool:
        """Only a complete successful projection and inspection can pass."""
        return self.dependencies.passed and self.validation.passed

    @property
    def issues(self) -> tuple[ValidationFinding, ...]:
        """Missing, unresolved or unsupported files, layers and run contexts."""
        return tuple(
            item for item in self.validation.findings
            if item.status != "present"
        )


def validate_batch_inputs(
    model: TCF | str | PathLike[str],
    run_flags: Iterable[str | dict[str, str]],
    *,
    options: ValidationOptions | None = None,
) -> BatchValidationResult:
    """Check all syntactic references and selected physical inputs for runs.

    A caller may supply an already parsed TCF to avoid reopening control files.
    Files, filename wildcards, selected GeoPackage layers and BC CSV selectors
    are inspected only during the explicit validation phase. Every finding is
    attributed to its original run and owning command.

    Defaults are strict: check files and GeoPackage layers, validate ordinary
    BC CSV headers, and use the same filename-case policy as the parsed model.
    GIS attribute-bearing layers receive a second read-only discovery stage;
    their linked source files are included in physical validation. Unknown GIS
    feature schemas fail closed rather than being marked as present. Raster
    pixel data and raster-content validity are outside this file-existence API.
    """
    from ._tmf.cf.tcf import TCF

    started = perf_counter()
    if isinstance(model, TCF):
        tcf = model
    else:
        # TUFLOW -cs policy must be applied while loading control files too.
        case = options.case_sensitivity if options is not None else None
        tcf = TCF(model, case_sensitivity=case)
    parse_seconds = perf_counter() - started

    # A TCF referring to a missing control file can remain unloaded rather
    # than raise immediately. Never certify its empty dependency inventory.
    if getattr(tcf, "fpath", None) is not None and not tcf.loaded:
        raise FileNotFoundError(f"TUFLOW control file was not loaded: {tcf.fpath}")
    if getattr(tcf, "fpath", None) is None and not tuple(tcf.inputs):
        raise ValueError("Cannot validate an empty, unnamed TUFLOW model")

    policy = getattr(tcf.config, "case_sensitivity", None)
    if options is None:
        options = ValidationOptions(
            check_files=True,
            check_gpkg_layers=True,
            check_bc_csv_headers=True,
            case_sensitivity=policy,
        )
    elif options.case_sensitivity is None:
        # Do not silently use Linux's unknown case policy if the model has an
        # explicit TUFLOW case policy. Preserve every other requested option.
        options = replace(options, case_sensitivity=policy)
    elif policy is not None and options.case_sensitivity != policy:
        raise ValueError(
            "Validation case_sensitivity must match the parsed TCF policy"
        )

    started = perf_counter()
    # Retain structured values for linked validation; display flags are lossy
    # when dictionary values contain whitespace. Consume generators only once.
    flags = tuple(dict(item) if isinstance(item, dict) else item for item in run_flags)
    dependencies = tcf.collect_file_dependencies(flags)
    collection_seconds = perf_counter() - started

    started = perf_counter()
    # First confirm primary physical sources and GeoPackage layers. GIS
    # attribute tables must not be opened for nonexistent or unresolved files.
    initial = pending_physical_projection(dependencies)
    primary_report = validate_dependencies(initial, options=options)
    discovered = extend_gis_dependencies(dependencies, primary_report, tcf, flags)
    # The private checked projection contains only GIS-selected BC/curve rows.
    # An unchanged syntactic run inventory is still exposed separately.
    report = (
        validate_dependencies(discovered.projection, options=options)
        if discovered.projection.runs != initial.runs else primary_report
    )
    if discovered.findings:
        by_run: dict[int, list[ValidationFinding]] = {}
        for finding in (*report.findings, *discovered.findings):
            by_run.setdefault(finding.run_index, []).append(finding)
        report = replace(
            report,
            findings=tuple(
                finding
                for run in dependencies.runs
                for finding in by_run.get(run.index, ())
            ),
        )
    inspection_seconds = perf_counter() - started

    return BatchValidationResult(
        dependencies, report,
        parse_seconds, collection_seconds, inspection_seconds,
        discovered.linked_sources, discovered.gis_files_scanned,
    )
