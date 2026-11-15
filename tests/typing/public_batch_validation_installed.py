"""Strict typing fixture for an installed PyTUFLOW wheel.

Run Pyright from outside the repository, using a non-editable installed wheel.
This file intentionally contains no runtime model creation or execution.
"""

# pyright: strict

from pathlib import Path
from typing import Literal, assert_type

from pytuflow import TCF
from pytuflow.batch_validation import BatchValidationResult, validate_batch_inputs
from pytuflow.validation import (
    ValidationFinding,
    ValidationKind,
    ValidationOptions,
    ValidationReport,
    ValidationStatus,
    validate_dependencies,
)


def inspect_public_api(
    model: TCF,
    filename: str,
    path: Path,
    flags: list[dict[str, str]],
) -> None:
    """Exercise filenames, a parsed TCF, structured flags and result members."""
    options = ValidationOptions(
        check_files=True,
        check_gpkg_layers=True,
        check_bc_csv_headers=True,
        check_raster_metadata=True,
        check_crs=True,
        io_workers=2,
        maximum_directory_entries=50_000,
    )
    assert_type(options, ValidationOptions)
    assert_type(options.check_raster_metadata, bool)
    assert_type(options.check_crs, bool)
    assert_type(options.io_workers, int)
    assert_type(options.maximum_directory_entries, int)

    assert_type(validate_batch_inputs(filename, flags, options=options), BatchValidationResult)
    assert_type(validate_batch_inputs(path, flags, options=options), BatchValidationResult)
    report = validate_batch_inputs(model, flags, options=options)
    assert_type(report, BatchValidationResult)
    assert_type(report.passed, bool)
    assert_type(report.issues, tuple[ValidationFinding, ...])
    assert_type(report.warnings, tuple[ValidationFinding, ...])
    assert_type(report.dependencies.passed, bool)
    assert_type(report.validation, ValidationReport)
    assert_type(report.parse_seconds, float)
    assert_type(report.collection_seconds, float)
    assert_type(report.inspection_seconds, float)
    assert_type(report.gis_sources_added, int)
    assert_type(report.gis_files_scanned, int)

    syntactic = model.collect_file_dependencies(flags)
    assert_type(syntactic.passed, bool)
    assert_type(syntactic.runs[0].index, int)
    assert_type(syntactic.runs[0].flags, str)
    assert_type(syntactic.runs[0].error, str | None)
    assert_type(syntactic.fragment_evaluations, int)
    assert_type(syntactic.fragment_reuses, int)
    assert_type(syntactic.elapsed_seconds, float)

    physical = report.validation
    assert_type(physical.passed, bool)
    assert_type(physical.warnings, tuple[ValidationFinding, ...])
    assert_type(physical.findings, tuple[ValidationFinding, ...])
    assert_type(physical.run_count, int)
    assert_type(physical.files_examined, int)
    assert_type(physical.geopackages_examined, int)
    assert_type(physical.csv_headers_examined, int)
    assert_type(physical.directories_scanned, int)
    assert_type(physical.raster_sources_examined, int)
    assert_type(physical.raster_subdatasets_opened, int)
    assert_type(physical.crs_sources_examined, int)

    assert_type(validate_dependencies(syntactic, model=model, options=options), ValidationReport)

    for run in report.dependencies.runs:
        assert_type(run.index, int)
        assert_type(run.error, str | None)
        assert_type(run.flags, str)

    for issue in report.issues:
        assert_type(issue, ValidationFinding)
        assert_type(issue.run_index, int)
        assert_type(issue.flags, str)
        assert_type(issue.status, ValidationStatus)
        assert_type(issue.kind, ValidationKind)
        assert_type(issue.path, Path | None)
        assert_type(issue.detail, str)
        assert_type(issue.layer, str | None)
        assert_type(issue.origin, str)
        assert_type(issue.input_uuid, str)
        assert_type(issue.command_index, int)
        assert_type(issue.owner_control_file, Path | None)
        assert_type(issue.database_kind, str | None)
        assert_type(issue.source_pattern, Path | None)
        assert_type(issue.csv_columns, tuple[str, ...] | None)
        assert_type(issue.severity, Literal["error", "warning"])
