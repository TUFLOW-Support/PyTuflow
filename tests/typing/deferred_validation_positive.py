"""Static-only consumer checks for deferred batch validation APIs.

These type checks target an installed PyTUFLOW wheel; do not execute the file.
"""

# pyright: strict

from pathlib import Path
from typing import assert_type

from pytuflow import TCF
from pytuflow._tmf.fragment_dependencies import FragmentBatchResult
from pytuflow.batch_validation import BatchValidationResult, validate_batch_inputs
from pytuflow.validation import ValidationFinding, ValidationOptions, ValidationReport


def inspect_existing_model(model: TCF, flags: list[str]) -> None:
    options = ValidationOptions(
        check_files=True,
        check_gpkg_layers=True,
        check_bc_csv_headers=True,
        io_workers=2,
    )
    report = validate_batch_inputs(model, flags, options=options)
    assert_type(report, BatchValidationResult)
    assert_type(report.passed, bool)
    assert_type(report.issues, tuple[ValidationFinding, ...])
    assert_type(report.validation, ValidationReport)

    syntactic = model.collect_file_dependencies(flags)
    assert_type(syntactic, FragmentBatchResult)

    if not report.passed:
        for issue in report.issues:
            path: Path | None = issue.path
            status: str = issue.status
            _ = (path, status)


def inspect_model_path(path: Path, flags: list[str]) -> BatchValidationResult:
    return validate_batch_inputs(path, flags)
