"""Synthetic contracts for explicit PyTUFLOW physical input validation.

All fixtures are local, temporary and read-only after construction. The
tests never run TUFLOW or depend on a real GIS/QGIS installation.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from pytuflow._tmf.dependency_records import BatchDependencyRun, BatchInputReference
from pytuflow._tmf.file_reference import (
    DeferredDatabaseActivation,
    DeferredDatabaseSource,
    FileReference,
)
from pytuflow.validation import ValidationOptions, validate_dependencies


def _ref(
    path: Path, *,
    layer: str | None = None,
    csv_columns: tuple[str, ...] | None = None,
    unresolved: tuple[str, ...] = (),
) -> FileReference:
    reference = FileReference(
        base_directory=path.parent,
        expanded_value=str(path.name),
        path_pattern=path,
        layer_pattern=layer,
        origin="Read GIS Code" if layer else "Read File",
        requires_directory_scan=("*" in path.name),
        requires_layer_scan=layer is not None,
        requires_attribute_scan=False,
        requires_database_scan=False,
        unresolved_variables=unresolved,
    )
    if csv_columns is None:
        return reference
    # Current master predates #39's csv_columns reference field. Preserve
    # the precise structural surface until the feature branch is refreshed.
    payload = vars(reference).copy()
    payload["csv_columns"] = csv_columns
    return cast(FileReference, SimpleNamespace(**payload))


def _run(
    index: int,
    refs: tuple[FileReference, ...] = (),
    *,
    sources: tuple[DeferredDatabaseSource, ...] = (),
    activations: tuple[DeferredDatabaseActivation, ...] = (),
    error: str | None = None,
) -> BatchDependencyRun:
    links = tuple(
        BatchInputReference(
            input_uuid=f"input-{ordinal}",
            command_index=ordinal,
            owner_control_file=ref.base_directory / "model.tcf",
            line_number=ordinal + 1,
            reference=ref,
        )
        for ordinal, ref in enumerate(refs)
    )
    return BatchDependencyRun(
        index=index,
        flags=f"-s1 S{index}",
        file_references=refs,
        database_sources=sources,
        database_activations=activations,
        error=error,
        input_references=links,
    )


def _project(*runs: BatchDependencyRun) -> SimpleNamespace:
    return SimpleNamespace(runs=tuple(runs))


def _bc_source(
    path: Path, *,
    columns: tuple[str, ...] | None,
    input_uuid: str = "bc-declaration",
) -> DeferredDatabaseSource:
    source = DeferredDatabaseSource(
        database_path=path.parent / "bc_dbase.csv",
        database_kind="bc",
        entry_name="inflow",
        path_pattern=path,
        owning_command="BC Database",
        owner_control_file=path.parent / "model.tbc",
        input_uuid=input_uuid,
    )
    if columns is None:
        return source
    payload = vars(source).copy()
    payload["csv_columns"] = columns
    return cast(DeferredDatabaseSource, SimpleNamespace(**payload))


def _bc_activation(path: Path, *, input_uuid: str = "bc-declaration") -> DeferredDatabaseActivation:
    return DeferredDatabaseActivation(
        sequence=5,
        input_uuid=input_uuid,
        database_kind="bc",
        database_path=path.parent / "bc_dbase.csv",
        owning_command="BC Database",
        owner_control_file=path.parent / "model.tbc",
        line_number=10,
    )


def test_file_and_directory_status_and_ordered_provenance(tmp_path: Path) -> None:
    present = tmp_path / "exists.shp"
    present.write_bytes(b"data")
    present.with_suffix(".dbf").write_bytes(b"data")
    present.with_suffix(".shx").write_bytes(b"data")
    directory = tmp_path / "not-a-file.shp"
    directory.mkdir()
    missing = tmp_path / "missing.tif"
    report = validate_dependencies(
        _project(
            _run(0, (_ref(present), _ref(directory), _ref(missing))),
            _run(1, (_ref(present),)),
        ),
        options=ValidationOptions(case_sensitivity=0),
    )
    assert not report.passed
    assert report.run_count == 2
    assert report.files_examined == 3
    assert report.geopackages_examined == report.csv_headers_examined == 0
    assert [(x.run_index, x.status) for x in report.findings] == [
        (0, "present"),
        (0, "missing"),
        (0, "missing"),
        (1, "present"),
    ]
    assert [(x.input_uuid, x.command_index) for x in report.findings[:3]] == [
        ("input-0", 0),
        ("input-1", 1),
        ("input-2", 2),
    ]


def test_projection_failure_does_not_jump_ahead_of_earlier_file(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.tif"
    existing.write_bytes(b"data")
    unresolved = tmp_path / "rain_<<UNKNOWN>>.tif"
    report = validate_dependencies(
        _project(
            _run(0, (_ref(existing),)),
            _run(1, (_ref(existing), _ref(unresolved, unresolved=("UNKNOWN",)))),
        ),
        options=ValidationOptions(case_sensitivity=0),
    )
    assert [(item.run_index, item.status) for item in report.findings] == [
        (0, "present"), (1, "present"), (1, "unresolved"),
    ]
    assert [item.path for item in report.findings] == [
        existing, existing, unresolved,
    ]


@pytest.mark.parametrize(
    ("candidate", "pattern", "case_sensitivity", "matched"),
    [
        ("Grid_A.TIF", "grid_*.tif", 0, False),
        ("Grid_A.TIF", "grid_*.tif", 1, False),
        ("grid_A.TIF", "grid_*.tif", 1, True),
        ("rain_A.CSV", "rain_*", 1, True),
        ("Rain_A.CSV", "rain_*", 1, False),
        ("rain_A.CSV", "rain_*", 0, True),
        ("Grid_A.TIF", "grid_*.tif", 2, True),
        ("Grid_A.TIF", "grid_*.tif", None, False),
    ],
)
def test_tuflow_linux_filename_glob_case_modes(
    candidate: str, pattern: str, case_sensitivity: int | None,
    matched: bool,
) -> None:
    from pytuflow.validation import _filename_matches

    assert _filename_matches(
        candidate, pattern, case_sensitivity, windows=False,
    ) is matched


def test_unique_wildcards_are_grouped_and_expanded_for_every_run(
    tmp_path: Path,
) -> None:
    for name in ("rain_A.shp", "rain_B.shp"):
        primary = tmp_path / name
        primary.write_bytes(b"test")
        primary.with_suffix(".dbf").write_bytes(b"test")
        primary.with_suffix(".shx").write_bytes(b"test")
    pattern = tmp_path / "rain_*.shp"
    report = validate_dependencies(
        _project(_run(0, (_ref(pattern),)), _run(1, (_ref(pattern),))),
    )
    assert report.passed
    assert report.directories_scanned == 1
    assert report.files_examined == 2
    assert [(f.run_index, f.path.name) for f in report.findings] == [
        (0, "rain_A.shp"),
        (0, "rain_B.shp"),
        (1, "rain_A.shp"),
        (1, "rain_B.shp"),
    ]
    assert all(f.source_pattern == pattern for f in report.findings)


@pytest.mark.parametrize(
    ("pattern", "expected_status"),
    [
        ("absent_*.shp", "missing"),
        ("no_parent/absent_*.shp", "missing"),
        ("*/rain.shp", "unsupported"),
    ],
)
def test_missing_and_unsupported_wildcard_requirements(
    tmp_path: Path, pattern: str, expected_status: str
) -> None:
    report = validate_dependencies(_project(_run(0, (_ref(tmp_path / pattern),))))
    assert len(report.findings) == 1
    assert report.findings[0].status == expected_status
    assert not report.passed


def test_bounded_wildcard_scan_fails_closed(tmp_path: Path) -> None:
    for index in range(3):
        primary = tmp_path / f"source_{index}.shp"
        primary.write_bytes(b"data")
        primary.with_suffix(".dbf").write_bytes(b"data")
        primary.with_suffix(".shx").write_bytes(b"data")
    report = validate_dependencies(
        _project(_run(0, (_ref(tmp_path / "source_*.shp"),))),
        options=ValidationOptions(maximum_directory_entries=1),
    )
    assert not report.passed
    assert report.findings[0].status == "unresolved"
    assert "bounded scan limit" in report.findings[0].detail
    assert report.files_examined == 0
    assert report.directories_scanned == 1


def test_parser_error_and_unresolved_variables_do_not_stat_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbid(*args: object, **kwargs: object) -> None:
        raise AssertionError("Parser error or unresolved name must not be inspected")

    unresolved = _ref(
        tmp_path / "path_<<~s1~>>.shp", unresolved=("<<~s1~>>",)
    )
    with monkeypatch.context() as guarded:
        guarded.setattr(Path, "stat", forbid)
        report = validate_dependencies(
            _project(
                _run(0, (unresolved,)),
                _run(1, (_ref(tmp_path / "partial.shp"),), error="Parser failure"),
            )
        )
    assert [(x.run_index, x.kind) for x in report.findings] == [
        (0, "file"), (1, "context"),
    ]
    assert all(x.status == "unresolved" for x in report.findings)
    assert report.files_examined == 0


def test_gpkg_exact_wildcard_and_all_layers_use_one_readonly_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pytuflow._tmf import gpkg_safety

    gpkg = tmp_path / "terrain.gpkg"
    with sqlite3.connect(gpkg) as connection:
        connection.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        connection.executemany(
            "INSERT INTO gpkg_contents VALUES (?)",
            [("2d_code_L",), ("2d_code_P",)],
        )

    connect = sqlite3.connect
    calls: list[str] = []

    def counted(database: str, *args: object, **kwargs: object) -> sqlite3.Connection:
        calls.append(database)
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(gpkg_safety.sqlite3, "connect", counted)
    report = validate_dependencies(
        _project(
            _run(0, (_ref(gpkg, layer="2d_code_L"), _ref(gpkg, layer="2d_code_*"))),
            _run(1, (_ref(gpkg, layer="all"), _ref(gpkg, layer="not_there"))),
        ),
    )
    assert report.files_examined == 1
    assert report.geopackages_examined == len(calls) == 1
    assert calls[0].endswith("?mode=ro&immutable=1")
    layers = [finding for finding in report.findings if finding.kind == "layer"]
    assert [item.status for item in layers] == [
        "present", "present", "present", "missing",
    ]
    assert not report.passed
    assert all(item.input_uuid.startswith("input-") for item in layers)


def test_gpkg_uncheckpointed_wal_changes_fail_without_writes(
    tmp_path: Path,
) -> None:
    """Fail on WAL-only changes; leave the editor's WAL and SHM untouched."""
    gpkg = tmp_path / "working.gpkg"
    editor = sqlite3.connect(gpkg)
    try:
        editor.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        editor.execute("INSERT INTO gpkg_contents VALUES ('checkpointed_layer')")
        editor.commit()
        assert editor.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        editor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        editor.execute("INSERT INTO gpkg_contents VALUES ('wal_only_edit')")
        editor.commit()

        wal = gpkg.with_name(gpkg.name + "-wal")
        shm = gpkg.with_name(gpkg.name + "-shm")
        assert wal.exists() and shm.exists()
        before = {item.name: item.read_bytes() for item in tmp_path.iterdir()}

        report = validate_dependencies(
            _project(
                _run(
                    0,
                    (
                        _ref(gpkg, layer="checkpointed_layer"),
                        _ref(gpkg, layer="wal_only_edit"),
                        _ref(gpkg),  # No layer selector: still an invalid GPKG
                    ),
                )
            )
        )
        after = {item.name: item.read_bytes() for item in tmp_path.iterdir()}

        assert after == before
        assert not report.passed
        assert report.files_examined == 1
        # WAL checks happen before connecting to SQLite, including when no
        # layer was requested. A rejected GPKG must never be counted as an
        # inspected valid GeoPackage.
        assert report.geopackages_examined == 0
        assert len(report.findings) == 3
        assert all(
            finding.status == "unresolved" and finding.kind == "file"
            for finding in report.findings
        )
        assert all(
            "non-empty SQLite -wal journal" in finding.detail
            and "Save/close" in finding.detail
            for finding in report.findings
        )
    finally:
        editor.close()


def test_gpkg_wal_journal_mode_without_sidecars_creates_no_files(
    tmp_path: Path,
) -> None:
    gpkg = tmp_path / "saved.gpkg"
    editor = sqlite3.connect(gpkg)
    try:
        editor.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        editor.execute("INSERT INTO gpkg_contents VALUES ('saved_layer')")
        editor.commit()
        assert editor.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    finally:
        editor.close()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["saved.gpkg"]
    before = gpkg.read_bytes()
    report = validate_dependencies(
        _project(_run(0, (_ref(gpkg, layer="saved_layer"),)))
    )
    assert report.passed
    assert report.geopackages_examined == 1
    assert gpkg.read_bytes() == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ["saved.gpkg"]


def test_symlinked_geopackage_rejects_wal_beside_real_target(
    tmp_path: Path,
) -> None:
    """Never accept uncheckpointed WAL edits hidden by a database symlink."""
    target = tmp_path / "real.gpkg"
    alias = tmp_path / "alias.gpkg"
    editor = sqlite3.connect(target)
    try:
        editor.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        editor.execute("INSERT INTO gpkg_contents VALUES ('saved_layer')")
        editor.commit()
        assert editor.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        editor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        editor.execute("INSERT INTO gpkg_contents VALUES ('wal_only_edit')")
        editor.commit()
        try:
            alias.symlink_to(target)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"Filesystem symlinks unavailable: {exc}")

        assert (tmp_path / "real.gpkg-wal").stat().st_size > 0
        before = {file.name: file.read_bytes() for file in tmp_path.iterdir()}
        report = validate_dependencies(
            _project(_run(0, (_ref(alias), _ref(alias, layer="saved_layer"))))
        )
        after = {file.name: file.read_bytes() for file in tmp_path.iterdir()}

        assert not report.passed
        assert report.geopackages_examined == 0
        assert report.files_examined == 1
        assert len(report.findings) == 2
        assert all(finding.path == alias for finding in report.findings)
        assert all(
            finding.status == "unresolved"
            and "non-empty SQLite -wal journal" in finding.detail
            for finding in report.findings
        )
        assert after == before
    finally:
        editor.close()


@pytest.mark.skipif(os.name == "nt", reason="Linux path-case policy")
def test_linux_explicit_case_policy_and_unknown_policy(tmp_path: Path) -> None:
    saved = tmp_path / "Grid_A.TIF"
    saved.write_bytes(b"grid")
    required = tmp_path / "grid_a.tif"
    projection = _project(_run(0, (_ref(required),)))

    unknown = validate_dependencies(projection)
    assert not unknown.passed
    assert unknown.findings[0].status == "unsupported"
    strict = validate_dependencies(
        projection, options=ValidationOptions(case_sensitivity=0)
    )
    assert not strict.passed
    assert strict.findings[0].status == "missing"
    relaxed = validate_dependencies(
        projection, options=ValidationOptions(case_sensitivity=2)
    )
    assert relaxed.passed
    assert relaxed.findings[0].path == saved

    wildcard = _project(_run(0, (_ref(tmp_path / "grid_*.tif"),)))
    matched = validate_dependencies(
        wildcard, options=ValidationOptions(case_sensitivity=2)
    )
    assert matched.passed
    assert matched.findings[0].path == saved


@pytest.mark.skipif(os.name == "nt", reason="Linux unknown-case existence probe")
@pytest.mark.parametrize(
    "error",
    [
        PermissionError("Cannot traverse input directory"),
        OSError("Input filesystem temporarily unavailable"),
    ],
)
def test_unknown_linux_case_probe_io_error_isolated_per_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: OSError,
) -> None:
    """An unreadable literal source must not abort inspection of another run."""
    denied = tmp_path / "private" / "input.tif"
    healthy = tmp_path / "available.tif"
    healthy.write_bytes(b"saved input")
    original_exists = Path.exists

    def restricted_exists(path: Path, *args: object, **kwargs: object) -> bool:
        if path == denied:
            raise error
        return original_exists(path, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", restricted_exists)
    report = validate_dependencies(
        _project(
            _run(0, (_ref(denied),)),
            _run(1, (_ref(healthy),)),
        ),
    )
    assert not report.passed
    assert report.run_count == 2
    assert report.files_examined == 1
    assert [(item.run_index, item.status, item.kind) for item in report.findings] == [
        (0, "unresolved", "file"),
        (1, "present", "file"),
    ]
    assert str(error) in report.findings[0].detail
    assert report.findings[0].path == denied
    assert report.findings[1].path == healthy


@pytest.mark.parametrize("use_symlink", [False, True])
def test_gpkg_active_rollback_journal_is_rejected_without_writes(
    tmp_path: Path, use_symlink: bool,
) -> None:
    """Immutable SQLite must never accept pages from an unfinished rollback."""
    target = tmp_path / "main.gpkg"
    editor = sqlite3.connect(target)
    try:
        editor.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        editor.executemany(
            "INSERT INTO gpkg_contents VALUES (?)",
            [(f"saved_{index}",) for index in range(3000)],
        )
        editor.commit()
        assert editor.execute("PRAGMA journal_mode=DELETE").fetchone() == (
            "delete",
        )
        editor.execute("PRAGMA cache_size=5")
        editor.execute("PRAGMA cache_spill=ON")
        editor.execute("BEGIN IMMEDIATE")
        editor.execute(
            "UPDATE gpkg_contents SET table_name = 'unsaved_' || table_name"
        )
        journal = tmp_path / "main.gpkg-journal"
        assert journal.stat().st_size > 0

        reference = target
        if use_symlink:
            reference = tmp_path / "linked.gpkg"
            try:
                reference.symlink_to(target)
            except (OSError, NotImplementedError) as exc:
                pytest.skip(f"Filesystem symlinks unavailable: {exc}")

        before = {file.name: file.read_bytes() for file in tmp_path.iterdir()}
        report = validate_dependencies(
            _project(
                _run(0, (_ref(reference, layer="saved_1"), _ref(reference))),
                _run(1, (_ref(reference, layer="unsaved_saved_1"),)),
            )
        )
        after = {file.name: file.read_bytes() for file in tmp_path.iterdir()}

        assert not report.passed
        assert report.files_examined == 1
        assert report.geopackages_examined == 0
        assert len(report.findings) == 3
        assert all(item.status == "unresolved" for item in report.findings)
        assert all(item.kind == "file" for item in report.findings)
        assert all(item.path == reference for item in report.findings)
        assert all(
            "non-empty SQLite -journal rollback file" in item.detail
            for item in report.findings
        )
        assert after == before
    finally:
        editor.rollback()
        editor.close()


@pytest.mark.parametrize("transaction", ["saved", "wal", "rollback"])
def test_hardlinked_geopackage_fails_closed_without_touching_sources(
    tmp_path: Path, transaction: str,
) -> None:
    """Hard links can hide a writer's WAL/rollback file under another name."""
    real = tmp_path / "real.gpkg"
    alias = tmp_path / "alias.gpkg"
    editor = sqlite3.connect(real)
    try:
        editor.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        editor.executemany(
            "INSERT INTO gpkg_contents VALUES (?)",
            [(f"saved_{i}",) for i in range(3000)],
        )
        editor.commit()
        try:
            os.link(real, alias)
        except (OSError, NotImplementedError) as exc:
            pytest.skip(f"Filesystem hard links unavailable: {exc}")
        assert real.stat().st_nlink > 1
        if transaction == "wal":
            assert editor.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
            editor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            editor.execute("INSERT INTO gpkg_contents VALUES ('wal_only')")
            editor.commit()
            assert (tmp_path / "real.gpkg-wal").stat().st_size > 0
        elif transaction == "rollback":
            assert editor.execute("PRAGMA journal_mode=DELETE").fetchone() == (
                "delete",
            )
            editor.execute("PRAGMA cache_size=5")
            editor.execute("PRAGMA cache_spill=ON")
            editor.execute("BEGIN IMMEDIATE")
            editor.execute(
                "UPDATE gpkg_contents SET table_name = 'uncommitted_' || table_name"
            )
            assert (tmp_path / "real.gpkg-journal").stat().st_size > 0
        before = {
            item.name: item.read_bytes() for item in tmp_path.iterdir()
        }

        report = validate_dependencies(
            _project(
                _run(0, (_ref(alias), _ref(alias, layer="saved_1"))),
                _run(1, (_ref(alias, layer="wal_only"),)),
            )
        )
        after = {item.name: item.read_bytes() for item in tmp_path.iterdir()}

        assert not report.passed
        assert report.files_examined == 1
        assert report.geopackages_examined == 0
        assert len(report.findings) == 3
        assert all(finding.kind == "file" for finding in report.findings)
        assert all(finding.status == "unresolved" for finding in report.findings)
        assert all(finding.path == alias for finding in report.findings)
        assert all(
            "multiple filesystem hard links" in finding.detail
            for finding in report.findings
        )
        assert before == after
    finally:
        editor.rollback()
        editor.close()


def test_symlink_retarget_during_gpkg_read_is_not_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A finding for an alias must still refer to the inspected source."""
    from pytuflow._tmf import gpkg_safety

    first = tmp_path / "first.gpkg"
    second = tmp_path / "second.gpkg"
    alias = tmp_path / "current.gpkg"
    for path, name in ((first, "first_only"), (second, "second_only")):
        with sqlite3.connect(path) as editor:
            editor.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
            editor.execute("INSERT INTO gpkg_contents VALUES (?)", (name,))
    try:
        alias.symlink_to(first)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Filesystem symlinks unavailable: {exc}")

    original_connect = sqlite3.connect
    swaps: list[bool] = []

    class RetargetingConnection:
        def __init__(self, source: sqlite3.Connection) -> None:
            self.source = source

        def execute(self, sql: str) -> sqlite3.Cursor:
            return self.source.execute(sql)

        def close(self) -> None:
            self.source.close()
            alias.unlink()
            alias.symlink_to(second)
            swaps.append(True)

    def intercept_connect(
        database: str, *, uri: bool,
    ) -> RetargetingConnection:
        return RetargetingConnection(original_connect(database, uri=uri))

    monkeypatch.setattr(gpkg_safety.sqlite3, "connect", intercept_connect)
    report = validate_dependencies(
        _project(_run(0, (_ref(alias, layer="first_only"),)))
    )

    assert swaps == [True]
    assert alias.resolve(strict=True) == second
    assert not report.passed
    assert [(finding.kind, finding.status) for finding in report.findings] == [
        ("file", "present"),
        ("layer", "unresolved"),
    ]
    assert report.findings[-1].path == alias
    assert "changed target or identity" in report.findings[-1].detail
    assert sorted(item.name for item in tmp_path.iterdir()) == [
        "current.gpkg", "first.gpkg", "second.gpkg",
    ]


@pytest.mark.parametrize("explicit_layer", [False, True])
def test_globbed_gpkg_implicit_default_layer_is_each_concrete_stem(
    tmp_path: Path, explicit_layer: bool,
) -> None:
    """Implicit terrain_*.gpkg checks concrete stems, not a layer wildcard."""
    from contextlib import closing

    from pytuflow._tmf.file_reference import make_file_reference
    from pytuflow._tmf.parsers.command import Command
    from pytuflow._tmf.settings import TCFConfig

    for name in ("terrain_A.gpkg", "terrain_B.gpkg"):
        with closing(sqlite3.connect(tmp_path / name)) as db:
            db.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
            # terrain_A.gpkg intentionally contains only terrain_B:
            # explicit ">> terrain_*" may match; implicit must not.
            db.execute("INSERT INTO gpkg_contents VALUES ('terrain_B')")
            db.commit()

    config = TCFConfig(
        control_file=tmp_path / "model.tcf",
        init_from_tcf=False,
    )
    value = "terrain_*.gpkg"
    if explicit_layer:
        value += " >> terrain_*"
    command = Command(
        f"Read GIS Code == {value}", config,
        parent=tmp_path / "model.tcf",
    )
    ref = make_file_reference(next(command.parts()))
    assert ref.path_pattern.name == "terrain_*.gpkg"
    assert ref.layer_pattern == "terrain_*"

    report = validate_dependencies(
        _project(_run(0, (ref,))),
        options=ValidationOptions(case_sensitivity=0),
    )
    assert report.files_examined == 2
    assert report.geopackages_examined == 2
    selected = [f for f in report.findings if f.kind == "layer"]
    assert [f.path.name for f in selected] == [
        "terrain_A.gpkg", "terrain_B.gpkg",
    ]
    assert [f.layer for f in selected] == (
        ["terrain_*", "terrain_*"] if explicit_layer
        else ["terrain_A", "terrain_B"]
    )
    assert [f.status for f in selected] == (
        ["present", "present"] if explicit_layer
        else ["missing", "present"]
    )
    assert report.passed is explicit_layer


@pytest.mark.parametrize(
    ("name", "existing", "expected"),
    [
        ("all", ("other_layer",), "missing"),
        ("all", ("all",), "present"),
        ("gis_[a]", ("gis_a",), "missing"),
        ("gis_[a]", ("gis_[a]",), "present"),
    ],
)
def test_implicit_gpkg_stems_are_literal_not_all_or_glob(
    name: str, existing: tuple[str, ...], expected: str,
) -> None:
    from pytuflow.validation import _layer_status

    assert _layer_status(name, existing, implicit=True)[0] == expected


def test_implicit_all_gpkg_requires_literal_all_layer(
    tmp_path: Path,
) -> None:
    from contextlib import closing

    from pytuflow._tmf.file_reference import make_file_reference
    from pytuflow._tmf.parsers.command import Command
    from pytuflow._tmf.settings import TCFConfig

    gpkg = tmp_path / "all.gpkg"
    with closing(sqlite3.connect(gpkg)) as db:
        db.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        db.execute("INSERT INTO gpkg_contents VALUES ('other_layer')")
        db.commit()

    config = TCFConfig(
        control_file=tmp_path / "model.tcf",
        init_from_tcf=False,
    )
    def ref(value: str) -> FileReference:
        return make_file_reference(next(
            Command(f"Read GIS Code == {value}", config,
                    parent=tmp_path / "model.tcf").parts()
        ))

    implicit = validate_dependencies(
        _project(_run(0, (ref("all.gpkg"),))),
        options=ValidationOptions(case_sensitivity=0),
    )
    explicit = validate_dependencies(
        _project(_run(0, (ref("all.gpkg >> all"),))),
        options=ValidationOptions(case_sensitivity=0),
    )
    assert not implicit.passed
    assert [(x.layer, x.status) for x in implicit.findings if x.kind == "layer"] == [
        ("all", "missing")
    ]
    assert explicit.passed
    assert [(x.layer, x.status) for x in explicit.findings if x.kind == "layer"] == [
        ("all", "present")
    ]


def test_single_implicit_gpkg_layer_uses_exact_filename_stem(
    tmp_path: Path,
) -> None:
    from contextlib import closing

    from pytuflow._tmf.file_reference import make_file_reference
    from pytuflow._tmf.parsers.command import Command
    from pytuflow._tmf.settings import TCFConfig

    gpkg = tmp_path / "single.gpkg"
    with closing(sqlite3.connect(gpkg)) as db:
        db.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        db.execute("INSERT INTO gpkg_contents VALUES ('other_layer')")
        db.commit()

    config = TCFConfig(
        control_file=tmp_path / "model.tcf",
        init_from_tcf=False,
    )
    ref = make_file_reference(next(
        Command("Read GIS Code == single.gpkg", config,
                parent=tmp_path / "model.tcf").parts()
    ))
    report = validate_dependencies(
        _project(_run(0, (ref,))),
        options=ValidationOptions(case_sensitivity=0),
    )
    assert not report.passed
    assert [(f.layer, f.status) for f in report.findings if f.kind == "layer"] == [
        ("single", "missing"),
    ]


@pytest.mark.skipif(os.name == "nt", reason="Linux final filename case policy")
@pytest.mark.parametrize(
    ("case_sensitivity", "requested"),
    [(1, "grid_A.tif"), (2, "grid_a.tif")],
)
def test_case_resolution_of_literal_filenames_is_bounded_and_shared(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_sensitivity: int,
    requested: str,
) -> None:
    """Repeat contexts may not rescan an unbounded network directory."""
    source = tmp_path / "Grid_A.TIF"
    if case_sensitivity == 1:
        source = tmp_path / "grid_A.TIF"
    source.write_bytes(b"grid")
    for index in range(4):
        (tmp_path / f"other_{index}.tif").write_bytes(b"unrelated")

    flag = tmp_path / requested
    projection = _project(*(
        _run(index, (_ref(flag),)) for index in range(4)
    ))
    original_scandir = os.scandir
    calls: list[Path] = []

    def counted(folder: os.PathLike[str] | str):
        calls.append(Path(folder))
        return original_scandir(folder)

    monkeypatch.setattr(os, "scandir", counted)
    report = validate_dependencies(
        projection,
        options=ValidationOptions(
            case_sensitivity=case_sensitivity,
            maximum_directory_entries=50,
        ),
    )
    assert report.passed
    assert report.directories_scanned == 1
    assert calls == [tmp_path]
    assert report.files_examined == 1
    assert len(report.findings) == 4
    assert all(item.path == source for item in report.findings)

    calls.clear()
    bounded = validate_dependencies(
        projection,
        options=ValidationOptions(
            case_sensitivity=case_sensitivity,
            maximum_directory_entries=1,
        ),
    )
    assert not bounded.passed
    assert bounded.directories_scanned == 1
    assert calls == [tmp_path]
    assert bounded.files_examined == 0
    assert len(bounded.findings) == 4
    assert all(item.status == "unresolved" for item in bounded.findings)
    assert all(
        "bounded scan limit" in item.detail for item in bounded.findings
    )


@pytest.mark.skipif(os.name == "nt", reason="Case-distinct filenames on Linux")
def test_case_relaxed_literal_ambiguous_filenames_fail_closed(tmp_path: Path) -> None:
    (tmp_path / "Grade_A.TIF").write_bytes(b"one")
    (tmp_path / "GRADE_A.TIF").write_bytes(b"two")
    wanted = tmp_path / "grade_a.tif"
    report = validate_dependencies(
        _project(_run(0, (_ref(wanted),))),
        options=ValidationOptions(case_sensitivity=2),
    )
    assert not report.passed
    assert report.directories_scanned == 1
    assert report.files_examined == 0
    assert report.findings[0].status == "unresolved"
    assert "Ambiguous TUFLOW -cs2 filename" in report.findings[0].detail


def test_invalid_geopackage_reports_unresolved_layer(tmp_path: Path) -> None:
    gpkg = tmp_path / "not_sqlite.gpkg"
    gpkg.write_bytes(b"invalid database")
    report = validate_dependencies(
        _project(_run(0, (_ref(gpkg, layer="2d_code_L"),))),
    )
    assert [(item.kind, item.status) for item in report.findings] == [
        ("file", "present"), ("layer", "unresolved")
    ]
    assert report.geopackages_examined == 1


def test_csv_header_is_checked_once_for_two_bc_activations(tmp_path: Path) -> None:
    source = tmp_path / "inflow.csv"
    source.write_text(
        "! TUFLOW event data\nEvent ID: E100\nTime,Flow,Stage\n0,2.5,0.1\n",
        encoding="utf-8",
    )
    a = _bc_source(source, columns=("Time", "Flow"))
    b = _bc_source(source, columns=("Time", "Stage"))
    report = validate_dependencies(
        _project(
            _run(0, sources=(a,), activations=(_bc_activation(source),)),
            _run(1, sources=(b,), activations=(_bc_activation(source),)),
        ),
        options=ValidationOptions(check_bc_csv_headers=True),
    )
    assert report.passed
    assert report.files_examined == report.csv_headers_examined == 1
    assert [(item.kind, item.command_index) for item in report.findings] == [
        ("file", 5), ("csv_header", 5), ("file", 5), ("csv_header", 5),
    ]
    assert all(item.input_uuid == "bc-declaration" for item in report.findings)


@pytest.mark.parametrize(
    ("columns", "status", "detail"),
    [
        (("Time", "Missing"), "unresolved", "Missing BC CSV columns"),
        (("Time", "Flow"), "unresolved", "Ambiguous BC CSV columns"),
        (("", "Flow"), "unsupported", "two resolved named column selectors"),
    ],
)
def test_csv_headers_detect_missing_duplicate_and_unresolved_selectors(
    tmp_path: Path, columns: tuple[str, str], status: str, detail: str
) -> None:
    source = tmp_path / "boundary.csv"
    source.write_text("Time,Flow,Flow\n0,1,2\n", encoding="utf-8")
    report = validate_dependencies(
        _project(
            _run(
                0,
                sources=(_bc_source(source, columns=columns),),
                activations=(_bc_activation(source),),
            )
        ),
        options=ValidationOptions(check_bc_csv_headers=True),
    )
    csv_findings = [
        item for item in report.findings if item.kind == "csv_header"
    ]
    assert len(csv_findings) == 1
    assert csv_findings[0].status == status
    assert detail in csv_findings[0].detail
    assert not report.passed


@pytest.mark.parametrize("invalid_first", [False, True])
def test_shared_bc_csv_header_selection_is_independent_per_run(
    tmp_path: Path, invalid_first: bool,
) -> None:
    """One run selecting a preamble must not invalidate a valid Source header."""
    source = tmp_path / "shared.csv"
    source.write_text(
        "Event ID: E100\nTime,Flow\n0,1\n", encoding="utf-8"
    )
    valid = _bc_source(source, columns=("Time", "Flow"))
    invalid = _bc_source(source, columns=("Event ID: E100", "Time"))
    first, second = (invalid, valid) if invalid_first else (valid, invalid)
    report = validate_dependencies(
        _project(
            _run(0, sources=(first,), activations=(_bc_activation(source),)),
            _run(1, sources=(second,), activations=(_bc_activation(source),)),
        ),
        options=ValidationOptions(check_bc_csv_headers=True),
    )
    assert not report.passed
    assert report.files_examined == 1
    assert report.csv_headers_examined == 1
    findings = [item for item in report.findings if item.kind == "csv_header"]
    assert len(findings) == 2
    by_index = {item.run_index: item for item in findings}
    valid_index = 1 if invalid_first else 0
    assert by_index[valid_index].status == "present"
    assert by_index[1 - valid_index].status == "unresolved"
    assert "Missing BC CSV columns" in by_index[1 - valid_index].detail


@pytest.mark.parametrize(
    ("header", "columns", "status", "detail"),
    [
        (
            "Time,!ignored,Flow\n", ("Time", "Flow"),
            "unresolved", "Missing BC CSV columns: Flow",
        ),
        (
            'Time,"Flow!value",!ignored\n', ("Time", "Flow!value"),
            "present", "",
        ),
        (
            "Time,Flow!trailing comment\n", ("Time", "Flow"),
            "present", "",
        ),
        (
            'Time,"Flow""!value"\n', ("Time", 'Flow"!value'),
            "present", "",
        ),
    ],
)
def test_bc_csv_inline_comments_ignore_only_unquoted_text(
    tmp_path: Path,
    header: str,
    columns: tuple[str, str],
    status: str,
    detail: str,
) -> None:
    source = tmp_path / "comments.csv"
    source.write_text(header + "0,1\n", encoding="utf-8")
    report = validate_dependencies(
        _project(_run(
            0,
            sources=(_bc_source(source, columns=columns),),
            activations=(_bc_activation(source),),
        )),
        options=ValidationOptions(check_bc_csv_headers=True),
    )
    result = [item for item in report.findings if item.kind == "csv_header"]
    assert len(result) == 1
    assert result[0].status == status
    assert detail in result[0].detail
    assert report.passed is (status == "present")


def test_csv_header_bounds_and_utf8_bom(tmp_path: Path) -> None:
    source = tmp_path / "long_header.csv"
    source.write_text(
        "\ufeff! first line\n! second line\n! third line\n"
        "! fourth line\n! fifth line\nTime,Flow\n0,1\n",
        encoding="utf-8",
    )
    projection = _project(
        _run(
            0,
            sources=(_bc_source(source, columns=("Time", "Flow")),),
            activations=(_bc_activation(source),),
        )
    )
    bounded = validate_dependencies(
        projection, options=ValidationOptions(check_bc_csv_headers=True)
    )
    assert not bounded.passed
    assert bounded.csv_headers_examined == 1
    assert "first 5 physical lines" in bounded.findings[-1].detail

    longer = validate_dependencies(
        projection,
        options=ValidationOptions(check_bc_csv_headers=True, maximum_header_lines=6),
    )
    assert longer.passed
    assert longer.csv_headers_examined == 1


def test_bounded_header_bytes_and_invalid_utf8_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "huge_header.csv"
    source.write_bytes(b"Time,Flow\n" + b"a" * 100)
    projection = _project(
        _run(
            0,
            sources=(_bc_source(source, columns=("Time", "Flow")),),
            activations=(_bc_activation(source),),
        )
    )
    tiny = validate_dependencies(
        projection,
        options=ValidationOptions(check_bc_csv_headers=True, maximum_header_bytes=4),
    )
    assert tiny.findings[-1].status == "unresolved"
    assert "bounded byte limit" in tiny.findings[-1].detail
    source.write_bytes(b"\xff,invalid\n")
    invalid = validate_dependencies(
        projection, options=ValidationOptions(check_bc_csv_headers=True)
    )
    assert invalid.findings[-1].status == "unresolved"


def test_fews_csv_skips_ordinary_header_check(tmp_path: Path) -> None:
    source = tmp_path / "fews.csv"
    source.write_bytes(b"not,an,ordinary,BC,header\n")
    report = validate_dependencies(
        _project(
            _run(
                0,
                sources=(_bc_source(source, columns=()),),
                activations=(_bc_activation(source),),
            )
        ),
        options=ValidationOptions(check_bc_csv_headers=True),
    )
    assert report.passed
    assert report.csv_headers_examined == 0
    assert len(report.findings) == 1
    assert report.findings[0].kind == "file"


def test_mismatched_bc_activation_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "value.csv"
    source.write_text("Time,Flow\n", encoding="utf-8")
    report = validate_dependencies(
        _project(
            _run(
                0,
                sources=(_bc_source(source, columns=("Time", "Flow"), input_uuid="other"),),
                activations=(_bc_activation(source),),
            )
        ),
        options=ValidationOptions(check_bc_csv_headers=True),
    )
    assert not report.passed
    assert report.findings[0].kind == "context"
    assert "no matching active" in report.findings[0].detail
    assert report.files_examined == 0


def test_no_file_check_with_only_optional_validation_disabled(tmp_path: Path) -> None:
    """Turning physical checks off must never implicitly touch source files."""
    invalid = tmp_path / "not_present.shp"
    report = validate_dependencies(
        _project(_run(0, (_ref(invalid),))),
        options=ValidationOptions(
            check_files=False,
            check_gpkg_layers=False,
            check_bc_csv_headers=False,
        ),
    )
    assert report.files_examined == 0
    assert report.directories_scanned == 0


def test_missing_bc_column_metadata_is_not_reported_as_valid(tmp_path: Path) -> None:
    source = tmp_path / "ordinary.csv"
    source.write_text("Time,Flow\n0,1\n", encoding="utf-8")
    report = validate_dependencies(
        _project(
            _run(
                0,
                sources=(_bc_source(source, columns=None),),
                activations=(_bc_activation(source),),
            )
        ),
        options=ValidationOptions(check_bc_csv_headers=True),
    )
    assert not report.passed
    assert report.csv_headers_examined == 0
    assert [(f.kind, f.status) for f in report.findings] == [
        ("file", "present"), ("csv_header", "unsupported"),
    ]


def test_disabled_validation_never_scans_wildcard_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("No filesystem inspection is allowed")

    monkeypatch.setattr(os, "scandir", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    report = validate_dependencies(
        _project(_run(0, (_ref(tmp_path / "source_*.shp"),))),
        options=ValidationOptions(
            check_files=False,
            check_gpkg_layers=False,
            check_bc_csv_headers=False,
        ),
    )
    assert not report.passed
    assert report.files_examined == report.directories_scanned == 0
    assert report.findings[0].status == "unsupported"


def test_primary_bc_database_is_not_misread_as_ordinary_source_csv(
    tmp_path: Path,
) -> None:
    """The BC Database itself is not a Source time-series CSV."""
    database = tmp_path / "bc_dbase.csv"
    database.write_text("Name,Source,Column 1,Column 2\n", encoding="utf-8")
    from dataclasses import replace

    primary = replace(_ref(database), database_kind="bc")
    report = validate_dependencies(
        _project(_run(0, (primary,))),
        options=ValidationOptions(check_bc_csv_headers=True),
    )
    assert report.passed
    assert report.files_examined == 1
    assert report.csv_headers_examined == 0
    assert len(report.findings) == 1
    assert report.findings[0].kind == "file"



def test_shapefile_companions_are_checked_on_plain_physical_files(
    tmp_path: Path,
) -> None:
    primary = tmp_path / "2d_code_area.shp"
    primary.write_bytes(b"shapefile header fixture")
    report = validate_dependencies(
        _project(_run(0, (_ref(primary),))),
        options=ValidationOptions(case_sensitivity=0),
    )
    assert not report.passed
    assert report.files_examined == 1
    assert report.findings[0].kind == "file"
    assert "2d_code_area.dbf" in report.findings[0].detail

    primary.with_suffix(".dbf").write_bytes(b"dbf")
    still_missing = validate_dependencies(
        _project(_run(0, (_ref(primary),))),
        options=ValidationOptions(case_sensitivity=0),
    )
    assert not still_missing.passed
    assert "2d_code_area.shx" in still_missing.findings[0].detail

    primary.with_suffix(".shx").write_bytes(b"shx")
    complete = validate_dependencies(
        _project(_run(0, (_ref(primary),))),
        options=ValidationOptions(case_sensitivity=0),
    )
    assert complete.passed
    assert complete.files_examined == 1


@pytest.mark.parametrize(
    ("primary_suffix", "companion_suffix"),
    [
        (".mif", ".mid"),
        (".mid", ".mif"),
        (".MIF", ".MID"),
        (".MID", ".MIF"),
        # Existing PyTUFLOW MapInfo readers also accept a different
        # *extension* case while keeping the filename stem unchanged.
        (".mif", ".MID"),
    ],
)
def test_mapinfo_pairs_are_required_independently_of_gis_attribute_inspection(
    tmp_path: Path, primary_suffix: str, companion_suffix: str,
) -> None:
    primary = tmp_path / f"2d_code_area{primary_suffix}"
    companion = primary.with_suffix(companion_suffix)
    primary.write_text("Primary MapInfo input", encoding="utf-8")
    projection = _project(_run(0, (_ref(primary),)))
    options = ValidationOptions(case_sensitivity=0)

    missing = validate_dependencies(projection, options=options)
    assert not missing.passed
    assert missing.files_examined == 1
    assert [(f.kind, f.status) for f in missing.findings] == [
        ("file", "missing"),
    ]
    assert companion_suffix.lstrip(".").upper() in missing.findings[0].detail

    companion.mkdir()
    directory = validate_dependencies(projection, options=options)
    assert not directory.passed
    assert "not a regular file" in directory.findings[0].detail
    companion.rmdir()

    companion.write_text("MapInfo companion", encoding="utf-8")
    complete = validate_dependencies(projection, options=options)
    assert complete.passed, complete.findings
    assert complete.files_examined == 1
