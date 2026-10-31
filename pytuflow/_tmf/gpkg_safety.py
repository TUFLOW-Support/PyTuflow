"""Read-only helpers for inspecting a stable main GeoPackage file.

Physical validation reads the checkpointed main SQLite database, checks
source identity and rejects unsafe journal or alias conditions. These
checks are used only for explicitly requested inspection and do not alter
the normal eager-parser behaviour.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

_UNSAVED_GPKG_WAL_ERROR = (
    "GeoPackage has a non-empty SQLite -wal journal; main .gpkg may "
    "not contain saved changes. Save/close the editing session, "
    "checkpoint the database externally, and rerun validation"
)
_UNSAVED_GPKG_ROLLBACK_ERROR = (
    "GeoPackage has a non-empty SQLite -journal rollback file; main .gpkg "
    "may include uncommitted changes. Save or roll back edits, close the "
    "editing session, and rerun validation"
)
_UNSAFE_GPKG_HARDLINK_ERROR = (
    "GeoPackage has multiple filesystem hard links (or unknown link count); "
    "other filenames may have active SQLite journals. A uniquely linked, "
    "fully saved main .gpkg is required for safe validation"
)
_GPKG_SOURCE_CHANGED_ERROR = (
    "GeoPackage source alias changed target or identity during inspection; "
    "rerun validation after editing and file links are stable"
)


class GeoPackageSafetyError(RuntimeError):
    """A main-file-only GeoPackage read cannot be certified as stable."""


def gpkg_source_identity(source: os.stat_result) -> tuple[int, int]:
    """Return the physical identity named by a lexical file alias."""
    return source.st_dev, source.st_ino


def gpkg_file_snapshot(source: os.stat_result) -> tuple[int, int, int, int, int]:
    """Compare changes across one bounded physical inspection."""
    return (
        source.st_dev, source.st_ino, source.st_size,
        source.st_mtime_ns, source.st_ctime_ns,
    )


def _gpkg_journal_error(path: Path, target: Path) -> str | None:
    """Check sidecar metadata for requested path and pinned target.

    Hard links are rejected because other filenames may own hidden journals.
    The main GeoPackage or its SQLite journals are never modified here.
    """
    if target.stat().st_nlink != 1:
        return _UNSAFE_GPKG_HARDLINK_ERROR
    for suffix, message in (
        ("-wal", _UNSAVED_GPKG_WAL_ERROR),
        ("-journal", _UNSAVED_GPKG_ROLLBACK_ERROR),
    ):
        for journal in {
            path.with_name(path.name + suffix),
            target.with_name(target.name + suffix),
        }:
            try:
                if journal.stat().st_size > 0:
                    return message
            except FileNotFoundError:
                continue
    return None


def _pin_gpkg(
    path: Path, expected_stat: os.stat_result | None = None
) -> tuple[Path, os.stat_result, os.stat_result]:
    """Pin the actual GeoPackage and reject unsafe journal states."""
    target = path.resolve(strict=True)
    alias = path.lstat()
    source = target.stat()
    requested = path.stat()
    if (
        gpkg_source_identity(requested) != gpkg_source_identity(source)
        or (expected_stat is not None
            and gpkg_source_identity(expected_stat) != gpkg_source_identity(source))
    ):
        raise GeoPackageSafetyError(_GPKG_SOURCE_CHANGED_ERROR)
    message = _gpkg_journal_error(path, target)
    if message is not None:
        raise GeoPackageSafetyError(message)
    if path.resolve(strict=True) != target:
        raise GeoPackageSafetyError(_GPKG_SOURCE_CHANGED_ERROR)
    return target, alias, source


def _confirm_gpkg(
    path: Path, target: Path,
    alias_before: os.stat_result, source_before: os.stat_result
) -> None:
    """Check that the pinned GeoPackage remains unchanged after inspection."""
    if path.resolve(strict=True) != target:
        raise GeoPackageSafetyError(_GPKG_SOURCE_CHANGED_ERROR)
    if (
        gpkg_file_snapshot(path.lstat()) != gpkg_file_snapshot(alias_before)
        or gpkg_source_identity(path.stat()) != gpkg_source_identity(source_before)
        or gpkg_file_snapshot(target.stat()) != gpkg_file_snapshot(source_before)
    ):
        raise GeoPackageSafetyError(_GPKG_SOURCE_CHANGED_ERROR)
    message = _gpkg_journal_error(path, target)
    if message is not None:
        raise GeoPackageSafetyError(message)


def check_gpkg_safety(
    path: Path, *, expected_stat: os.stat_result | None = None
) -> None:
    """Reject unsafe aliases or unsaved SQLite sidecars without opening SQLite."""
    target, alias, source = _pin_gpkg(Path(path), expected_stat)
    _confirm_gpkg(Path(path), target, alias, source)


def _readonly_sqlite_uri(path: Path) -> str:
    """Encode a pinned path with an empty authority for native SQLite."""
    uri = path.as_uri()
    # Windows resolves mapped drives to UNC paths. SQLite builds without
    # URI-authority support reject file://server/share; keep the server in
    # the path as file:////server/share instead. as_uri already escapes names.
    if uri.startswith("file://") and not uri.startswith("file:///"):
        uri = "file:////" + uri[len("file://"):]
    return f"{uri}?mode=ro&immutable=1"


@contextmanager
def readonly_gpkg(path: Path) -> Iterator[sqlite3.Connection]:
    """Open one stable, checkpointed main GeoPackage without SQLite writes.

    Even if an inspecting caller raises, verify the original main file and
    alias after the connection closes. An editor's concurrent changes are
    reported as an error rather than accepted as a stable metadata snapshot.
    """
    path = Path(path)
    target, alias, source = _pin_gpkg(path)
    uri = _readonly_sqlite_uri(target)
    try:
        with closing(sqlite3.connect(uri, uri=True)) as database:
            yield database
    finally:
        # Check even when the caller's query fails. No SQLite connection
        # remains open when the alias and journal state are rechecked.
        _confirm_gpkg(path, target, alias, source)


def read_gpkg_layer_names(path: Path) -> tuple[tuple[str, ...], str]:
    """Return GeoPackage layer names and a fail-closed source-owned error."""
    try:
        with readonly_gpkg(path) as database:
            names = tuple(
                str(row[0])
                for row in database.execute("SELECT table_name FROM gpkg_contents")
            )
        return names, ""
    except (OSError, sqlite3.DatabaseError, ValueError, RuntimeError) as exc:
        return (), f"Cannot inspect GeoPackage layers: {exc}"
