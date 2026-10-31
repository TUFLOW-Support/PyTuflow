"""Immutable records of TUFLOW input dependencies for individual runs.

Capture active commands and file references in source order, preserving their
control-file ownership and positions. Physical validation of the referenced
inputs is performed separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .file_reference import (
        DeferredDatabaseActivation,
        DeferredDatabaseSource,
        FileReference,
    )


@dataclass(frozen=True, slots=True)
class BatchInputCommand:
    """An active command in original per-run order, even without file refs."""

    input_uuid: str
    command_index: int
    owner_control_file: Path | None
    line_number: int
    command_name: str
    command_text: str
    reference_count: int


@dataclass(frozen=True, slots=True)
class BatchInputReference:
    """An immutable input reference with ownership and command position."""

    input_uuid: str
    command_index: int
    owner_control_file: Path | None
    line_number: int
    reference: FileReference


@dataclass(frozen=True, slots=True)
class BatchDependencyRun:
    """One requested context; failed runs contain no partial dependencies."""

    index: int
    flags: str
    file_references: tuple[FileReference, ...]
    database_sources: tuple[DeferredDatabaseSource, ...]
    database_activations: tuple[DeferredDatabaseActivation, ...]
    error: str | None = None
    input_references: tuple[BatchInputReference, ...] = ()
    ordered_inputs: tuple[BatchInputCommand, ...] = ()
