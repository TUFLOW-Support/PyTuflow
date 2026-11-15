"""Focused read-only raster header validation contracts.

Synthetic model inputs and GDAL datasets are used; no solver is launched.
All file inventories are checked after the inspection, including failures.
"""

from __future__ import annotations

import os
import sqlite3
import warnings
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from pytuflow import TCF
from pytuflow._tmf.dependency_records import BatchDependencyRun, BatchInputReference
from pytuflow._tmf.file_reference import FileReference, make_file_reference
from pytuflow._tmf.parsers.command import Command
from pytuflow._tmf.settings import TCFConfig
from pytuflow.batch_validation import validate_batch_inputs
from pytuflow.validation import ValidationOptions, validate_dependencies


def _ref(
    path: Path,
    *,
    raster: bool = True,
    selector: str | None = None,
    unresolved: tuple[str, ...] = (),
) -> FileReference:
    return FileReference(
        base_directory=path.parent,
        expanded_value=path.name,
        path_pattern=path,
        layer_pattern=selector,
        origin="Read Grid Zpts",
        requires_directory_scan="*" in path.name,
        requires_layer_scan=False,
        requires_attribute_scan=False,
        requires_database_scan=False,
        unresolved_variables=unresolved,
        requires_raster_metadata_scan=raster,
    )


def _run(index: int, *refs: FileReference, error: str | None = None) -> BatchDependencyRun:
    links = tuple(
        BatchInputReference(
            input_uuid=f"raster-{position}",
            command_index=position,
            owner_control_file=ref.base_directory / "model.tcf",
            line_number=position + 1,
            reference=ref,
        )
        for position, ref in enumerate(refs)
    )
    return BatchDependencyRun(
        index=index,
        flags=f"-s1 S{index}",
        file_references=refs,
        database_sources=(),
        database_activations=(),
        error=error,
        input_references=links,
    )


def _projection(*runs: BatchDependencyRun) -> SimpleNamespace:
    return SimpleNamespace(runs=tuple(runs))


def _options(**changes: object) -> ValidationOptions:
    return ValidationOptions(case_sensitivity=0, check_raster_metadata=True, **changes)


def _tiff(path: Path) -> None:
    with rasterio.open(
        path, "w", driver="GTiff", width=2, height=2, count=1,
        dtype="float32", transform=from_origin(100, 200, 1, 1),
    ) as destination:
        destination.write(np.ones((2, 2), dtype="float32"), 1)


def _inventory(folder: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(path.relative_to(folder)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in folder.rglob("*") if path.is_file()
    }


def test_both_optional_checks_can_be_disabled_for_direct_and_batch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = tmp_path / "invalid.tif"
    bad.write_bytes(b"not a TIFF")
    model_path = tmp_path / "model.tcf"
    model_path.write_text("Read Grid Zpts == invalid.tif\n", encoding="utf-8")
    model = TCF(model_path, case_sensitivity=0)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Rasterio must not be imported/opened by disabled checks")

    monkeypatch.setattr(rasterio, "open", forbidden)
    no_headers = ValidationOptions(
        case_sensitivity=0, check_raster_metadata=False, check_crs=False,
    )
    direct = validate_dependencies(
        _projection(_run(0, _ref(bad))), options=no_headers,
    )
    batch = validate_batch_inputs(model, ["-s1 TEST"], options=no_headers)
    assert direct.passed and batch.passed
    assert direct.raster_sources_examined == batch.validation.raster_sources_examined == 0
    assert direct.crs_sources_examined == batch.validation.crs_sources_examined == 0
    assert all(f.kind != "raster_metadata" for f in (*direct.findings, *batch.validation.findings))


def test_real_geotiff_invalid_and_missing_are_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    good, bad, missing = (tmp_path / name for name in ("good.tif", "bad.tif", "absent.tif"))
    _tiff(good)
    bad.write_bytes(b"not a valid raster")
    bad.with_suffix(".tif.aux.xml").write_text("<PAMDataset/>", encoding="utf-8")
    before = _inventory(tmp_path)

    real_open = rasterio.open
    calls: list[str] = []
    handles: list[object] = []

    class Guard:
        def __init__(self, handle: object) -> None:
            self.handle = handle

        def __enter__(self) -> "Guard":
            self.handle.__enter__()
            return self

        def __exit__(self, *args: object) -> None:
            self.handle.__exit__(*args)

        def __getattr__(self, key: str) -> object:
            if key in {"read", "read_masks", "statistics", "get_statistics",
                       "overviews", "sample", "block_windows"}:
                raise AssertionError(f"Raster pixel/statistics method called: {key}")
            return getattr(self.handle, key)

    def guarded_open(path: object, mode: str = "r") -> Guard:
        assert mode == "r"
        calls.append(str(path))
        handle = real_open(path, mode=mode)
        handles.append(handle)
        return Guard(handle)

    monkeypatch.setattr(rasterio, "open", guarded_open)
    report = validate_dependencies(
        _projection(_run(0, _ref(good), _ref(bad), _ref(missing)),
                    _run(1, _ref(good), _ref(bad))),
        options=_options(),
    )
    assert not report.passed
    assert report.files_examined == 3
    assert report.raster_sources_examined == 2
    assert report.raster_subdatasets_opened == 0
    assert sorted(calls) == sorted([str(good), str(bad)])
    assert all(handle.closed for handle in handles)
    assert [(f.run_index, f.status) for f in report.findings if f.kind == "raster_metadata"] == [
        (0, "present"), (0, "unresolved"), (1, "present"), (1, "unresolved"),
    ]
    assert [(f.run_index, f.status) for f in report.findings
            if f.path == missing] == [(0, "missing")]
    assert _inventory(tmp_path) == before


def test_bad_dimensions_and_failed_context_never_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "empty.tif"
    path.touch()
    closed: list[bool] = []

    class Empty:
        width = 0
        height = 1
        count = 0

        def __enter__(self) -> "Empty":
            return self

        def __exit__(self, *args: object) -> None:
            closed.append(True)

        def read(self, *args: object) -> None:
            raise AssertionError("pixel reads are forbidden")

    monkeypatch.setattr(rasterio, "open", lambda *a, **k: Empty())
    report = validate_dependencies(
        _projection(_run(0, _ref(path)), _run(1, _ref(path), error="bad context")),
        options=_options(),
    )
    assert not report.passed
    assert report.raster_sources_examined == 1
    assert closed == [True]
    assert [(f.run_index, f.kind, f.status) for f in report.findings if f.status != "present"] == [
        (0, "raster_metadata", "unresolved"), (1, "context", "unresolved"),
    ]


def test_mixed_grid_vector_parts_preserve_raster_role(tmp_path: Path) -> None:
    config = TCFConfig(control_file=tmp_path / "model.tcf", init_from_tcf=False,
                       file_resolution="deferred")
    grid = Command("Read Grid Zpts == terrain.tif | clip.shp", config)
    references = [make_file_reference(part) for part in grid.parts()]
    assert [ref.requires_raster_metadata_scan for ref in references] == [True, False]

    conveyance = Command(
        "Read GIS Zpts Modify Conveyance == zpts.shp | 1 | conveyance.tif", config,
    )
    parts = list(conveyance.parts())
    assert [part.is_raster_file() for part in parts] == [False, False, True]


def test_batch_mixed_sources_and_wildcards_with_spaces(tmp_path: Path) -> None:
    _tiff(tmp_path / "rain A.tif")
    _tiff(tmp_path / "rain B.tif")
    for suffix in (".shp", ".dbf", ".shx"):
        (tmp_path / f"clip{suffix}").write_bytes(b"companion")
    top = tmp_path / "model.tcf"
    top.write_text("Read Grid Zpts == rain*.tif | clip.shp\n", encoding="utf-8")
    result = validate_batch_inputs(
        TCF(top, case_sensitivity=0), ["-s1 A", "-s1 B"], options=_options(),
    )
    assert result.passed, result.issues
    assert result.validation.raster_sources_examined == 2
    raster = [f for f in result.validation.findings if f.kind == "raster_metadata"]
    assert len(raster) == 4
    assert {f.run_index for f in raster} == {0, 1}
    assert all(f.path.suffix == ".tif" for f in raster)
    assert not any(f.kind == "raster_metadata" and f.path.name == "clip.shp"
                   for f in result.validation.findings)


def test_rainfall_csv_source_is_checked_not_csv_index(tmp_path: Path) -> None:
    (tmp_path / "rain_index.csv").write_text("0,rain_000.tif\n", encoding="utf-8")
    (tmp_path / "rain_000.tif").write_bytes(b"bad header")
    top = tmp_path / "model.tcf"
    top.write_text("Read Grid RF == rain_index.csv\n", encoding="utf-8")
    result = validate_batch_inputs(
        TCF(top, case_sensitivity=0), ["-s1 A"], options=_options(),
    )
    assert not result.passed
    assert result.validation.raster_sources_examined == 1
    assert any(f.kind == "raster_metadata" and f.status == "unresolved"
               and f.path.name == "rain_000.tif"
               and f.database_kind == "rainfall" for f in result.issues)
    assert not any(f.kind == "raster_metadata" and f.path.name == "rain_index.csv"
                   for f in result.validation.findings)


def test_gis_linked_raster_is_inspected_once_across_two_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _tiff(tmp_path / "shared.tif")
    gpkg = tmp_path / "links.gpkg"
    with sqlite3.connect(gpkg) as connection:
        connection.execute("CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO gpkg_contents VALUES ('1d_xs_link')")
        connection.execute(
            "CREATE TABLE gpkg_geometry_columns "
            "(table_name TEXT, column_name TEXT, geometry_type_name TEXT)"
        )
        connection.execute(
            "INSERT INTO gpkg_geometry_columns VALUES ('1d_xs_link', 'geom', 'LINESTRING')"
        )
        connection.execute(
            'CREATE TABLE "1d_xs_link" (fid INTEGER PRIMARY KEY, geom BLOB, Source TEXT)'
        )
        connection.execute('INSERT INTO "1d_xs_link" (Source) VALUES ("shared.tif")')
    top = tmp_path / "model.tcf"
    top.write_text(
        "Read Grid Zpts == shared.tif\n"
        "Read GIS Code == links.gpkg >> 1d_xs_link\n", encoding="utf-8",
    )
    model = TCF(top, case_sensitivity=0)
    from pytuflow import validation

    stat_calls: list[Path] = []
    original_stat = validation._stat_source

    def counted_stat(path: Path) -> tuple[str, str]:
        stat_calls.append(path)
        return original_stat(path)

    monkeypatch.setattr(validation, "_stat_source", counted_stat)
    # Initial model parsing retains existing provider I/O. Snapshot only the
    # new physical validation stage, which must never modify sidecars.
    before = _inventory(tmp_path)
    result = validate_batch_inputs(
        model, ["-s1 A", "-s1 B"], options=_options(),
    )
    assert result.passed, result.issues
    assert result.gis_sources_added == 2
    assert result.validation.raster_sources_examined == 1
    assert sorted(stat_calls) == sorted([tmp_path / "shared.tif", gpkg])
    assert len([f for f in result.validation.findings
                if f.kind == "raster_metadata" and f.path.name == "shared.tif"]) == 4
    assert _inventory(tmp_path) == before


@dataclass
class _FakeDataset:
    width: int = 0
    height: int = 0
    count: int = 0
    subdatasets: tuple[str, ...] = ()
    closed: bool = False

    def __enter__(self) -> "_FakeDataset":
        return self

    def __exit__(self, *args: object) -> None:
        self.closed = True

    def read(self, *args: object) -> None:
        raise AssertionError("Pixel reads are forbidden")

    def statistics(self, *args: object) -> None:
        raise AssertionError("Statistics are forbidden")

    def overviews(self, *args: object) -> None:
        raise AssertionError("Overview queries are forbidden")


def _netcdf_mock(
    monkeypatch: pytest.MonkeyPatch, root: Path,
    subdatasets: tuple[str, ...],
    children: dict[str, _FakeDataset | Exception],
    *, root_bands: int = 0,
) -> tuple[list[str], list[_FakeDataset]]:
    calls: list[str] = []
    opened: list[_FakeDataset] = []

    def fake_open(path: object, mode: str = "r") -> _FakeDataset:
        assert mode == "r"
        key = str(path)
        calls.append(key)
        if key == str(root):
            instance = _FakeDataset(
                width=2 if root_bands else 0,
                height=2 if root_bands else 0,
                count=root_bands,
                subdatasets=subdatasets,
            )
        else:
            candidate = children.get(key, OSError(f"Unexpected GDAL source: {key}"))
            if isinstance(candidate, Exception):
                raise candidate
            instance = candidate
        opened.append(instance)
        return instance

    monkeypatch.setattr(rasterio, "open", fake_open)
    return calls, opened


def test_netcdf_selected_variable_cannot_borrow_unrelated_valid_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "rain.nc"
    path.write_bytes(b"mock NC container")
    good, bad = ('NETCDF:"rain.nc":' + value for value in ("valid", "invalid"))
    calls, opened = _netcdf_mock(
        monkeypatch, path, (good, bad),
        {good: _FakeDataset(2, 2, 1), bad: _FakeDataset(0, 0, 0)},
    )
    report = validate_dependencies(
        _projection(_run(0, _ref(path, selector="valid")),
                    _run(1, _ref(path, selector="invalid")),
                    _run(2, _ref(path, selector=None)),
                    _run(3, _ref(path, selector="missing"))),
        options=_options(),
    )
    results = [f for f in report.findings if f.kind == "raster_metadata"]
    assert [(f.run_index, f.status) for f in results] == [
        (0, "present"), (1, "unresolved"), (2, "present"), (3, "unresolved"),
    ]
    assert "no particular variable" in results[2].detail
    assert [f.layer for f in results] == ["valid", "invalid", None, "missing"]
    assert report.raster_sources_examined == 1
    assert report.raster_subdatasets_opened == 2
    assert calls == [str(path), bad, good]
    assert len(opened) == 3 and all(ds.closed for ds in opened)


def test_netcdf_failed_subdataset_does_not_abort_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "rain.nc"
    path.touch()
    failed, good = "NETCDF:rain.nc:failed", "NETCDF:rain.nc:good"
    calls, opened = _netcdf_mock(
        monkeypatch, path, (failed, good),
        {failed: OSError("cannot open requested band"), good: _FakeDataset(3, 3, 1)},
    )
    report = validate_dependencies(
        _projection(_run(0, _ref(path, selector="failed")),
                    _run(1, _ref(path, selector="good")),
                    _run(2, _ref(path))),
        options=_options(),
    )
    statuses = [f.status for f in report.findings if f.kind == "raster_metadata"]
    assert statuses == ["unresolved", "present", "present"]
    assert report.raster_subdatasets_opened == 2
    assert len(opened) == 2 and all(ds.closed for ds in opened)


@pytest.mark.parametrize(
    ("subdatasets", "selectors", "maximum", "expected"),
    [
        ((), (None,), 2, "unresolved"),
        (("NETCDF:rain.nc:x", "NETCDF:rain.nc:y", "NETCDF:rain.nc:z"),
         (None, "x"), 2, "unsupported"),
        (("NETCDF:rain.nc:good",), ("not_found",), 2, "unresolved"),
        (("NETCDF:rain.nc:good",), ("bad*",), 2, "unsupported"),
    ],
)
def test_netcdf_empty_bounded_missing_and_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    subdatasets: tuple[str, ...], selectors: tuple[str | None, ...],
    maximum: int, expected: str,
) -> None:
    path = tmp_path / "rain.nc"
    path.touch()
    calls, opened = _netcdf_mock(monkeypatch, path, subdatasets, {})
    report = validate_dependencies(
        _projection(*(_run(i, _ref(path, selector=selector))
                      for i, selector in enumerate(selectors))),
        options=_options(maximum_raster_subdatasets=maximum),
    )
    assert not report.passed
    assert report.raster_sources_examined == 1
    assert report.raster_subdatasets_opened == 0
    assert all(f.status == expected for f in report.findings if f.kind == "raster_metadata")
    assert calls == [str(path)] and all(ds.closed for ds in opened)


def test_netcdf_usable_root_without_subdatasets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "grid.nc"
    path.touch()
    calls, opened = _netcdf_mock(monkeypatch, path, (), {}, root_bands=1)
    report = validate_dependencies(_projection(_run(0, _ref(path))), options=_options())
    assert report.passed
    assert report.raster_sources_examined == 1
    assert report.raster_subdatasets_opened == 0
    assert calls == [str(path)] and all(ds.closed for ds in opened)


def test_disabled_physical_checks_stay_unsupported(tmp_path: Path) -> None:
    path = tmp_path / "valid.tif"
    _tiff(path)
    report = validate_dependencies(
        _projection(_run(0, _ref(path))),
        options=ValidationOptions(check_files=False, check_raster_metadata=True),
    )
    assert not report.passed
    assert report.raster_sources_examined == 0
    assert [(f.kind, f.status) for f in report.findings] == [("file", "unsupported")]


def test_raster_limit_rejects_nonpositive_value() -> None:
    with pytest.raises(ValueError, match="Inspection limits"):
        ValidationOptions(maximum_raster_subdatasets=0)


def test_parser_preserves_explicit_netcdf_variable_role(tmp_path: Path) -> None:
    config = TCFConfig(control_file=tmp_path / "model.tcf", init_from_tcf=False,
                       file_resolution="deferred")
    command = Command("Read Grid RF == rain.nc >> rainfall", config)
    reference = make_file_reference(next(command.parts()))
    assert reference.path_pattern == tmp_path / "rain.nc"
    assert reference.layer_pattern == "rainfall"
    assert reference.requires_raster_metadata_scan


@pytest.mark.skipif(os.name != "nt", reason="UNC lexical paths require Windows")
def test_windows_unc_raster_path_is_passed_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pytuflow import validation

    unc = Path(r"\\server\share\grid.tif")
    monkeypatch.setattr(validation, "_stat_source", lambda path: ("present", ""))
    opened: list[Path] = []
    handle = _FakeDataset(2, 2, 1)

    def open_unc(path: Path, mode: str = "r") -> _FakeDataset:
        assert mode == "r"
        opened.append(path)
        return handle

    monkeypatch.setattr(rasterio, "open", open_unc)
    result = validate_dependencies(
        _projection(_run(0, _ref(unc))), options=_options(),
    )
    assert result.passed
    assert opened == [unc]
    assert handle.closed


def test_real_multivariable_netcdf_under_strict_raster_warnings(tmp_path: Path) -> None:
    """A bandless NetCDF root must not hide selected, usable subdatasets."""
    from netCDF4 import Dataset
    from rasterio.errors import NotGeoreferencedWarning

    source = tmp_path / "rain.nc"
    with Dataset(source, "w", format="NETCDF4") as dataset:
        dataset.createDimension("lat", 2)
        dataset.createDimension("lon", 2)
        lat = dataset.createVariable("lat", "f8", ("lat",))
        lon = dataset.createVariable("lon", "f8", ("lon",))
        lat.standard_name, lat.units = "latitude", "degrees_north"
        lon.standard_name, lon.units = "longitude", "degrees_east"
        lat[:] = (0.0, 1.0)
        lon[:] = (100.0, 101.0)
        for name in ("rainfall", "other"):
            # Header inspection needs the variable schema, not pixel writes.
            dataset.createVariable(name, "f4", ("lat", "lon"))
    before = _inventory(tmp_path)

    from pytuflow._raster_metadata import inspect_raster_headers

    with warnings.catch_warnings():
        warnings.simplefilter("error", NotGeoreferencedWarning)
        outcomes, child_opens, crs_values = inspect_raster_headers(
            source, {"rainfall", "other"},
            maximum_subdatasets=64, include_crs=True,
        )

    assert outcomes == {
        "rainfall": ("present", ""), "other": ("present", ""),
    }
    assert child_opens == 2
    assert set(crs_values) == {"rainfall", "other"}
    assert _inventory(tmp_path) == before


@pytest.mark.parametrize(
    ("headers", "crs"),
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_shared_files_and_wildcards_are_inspected_once_across_batch_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, headers: bool, crs: bool,
) -> None:
    """Final-pass metadata must not cause repeated primary file or glob I/O."""
    from pytuflow import validation

    grid = tmp_path / "grid A.tif"
    _tiff(grid)
    top = tmp_path / "model.tcf"
    top.write_text(
        "Read Grid Zpts == grid*.tif\nRead Grid Zpts == grid*.tif\n",
        encoding="utf-8",
    )
    model = TCF(top, case_sensitivity=0)

    checked: list[Path] = []
    globs: list[set[Path]] = []
    opened: list[str] = []
    original_stat = validation._stat_source
    original_globs = validation._scan_wildcard_patterns
    original_open = rasterio.open

    def counted_stat(path: Path) -> tuple[str, str]:
        checked.append(path)
        return original_stat(path)

    def counted_globs(patterns: set[Path], **kwargs: object) -> object:
        if patterns:
            globs.append(set(patterns))
        return original_globs(patterns, **kwargs)

    def counted_open(path: object, mode: str = "r") -> object:
        opened.append(str(path))
        return original_open(path, mode=mode)

    monkeypatch.setattr(validation, "_stat_source", counted_stat)
    monkeypatch.setattr(validation, "_scan_wildcard_patterns", counted_globs)
    monkeypatch.setattr(rasterio, "open", counted_open)
    report = validate_batch_inputs(
        model, ["-s1 A", "-s1 B"],
        options=ValidationOptions(
            case_sensitivity=0,
            check_raster_metadata=headers,
            check_crs=crs,
        ),
    )
    assert report.passed, report.issues
    assert checked == [grid]
    assert globs == [{tmp_path / "grid*.tif"}]
    assert report.validation.files_examined == 1
    assert report.validation.directories_scanned == 1
    assert opened == ([str(grid)] if headers or crs else [])
    assert report.validation.raster_sources_examined == int(headers or crs)
    assert report.validation.crs_sources_examined == int(crs)


def test_cached_missing_files_have_one_failure_and_no_header_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not double-stat missing sources or turn them into header failures."""
    from pytuflow import validation

    missing = tmp_path / "missing.tif"
    top = tmp_path / "model.tcf"
    top.write_text("Read Grid Zpts == missing.tif\n", encoding="utf-8")
    model = TCF(top, case_sensitivity=0)
    checked: list[Path] = []
    original_stat = validation._stat_source

    def counted_stat(path: Path) -> tuple[str, str]:
        checked.append(path)
        return original_stat(path)

    monkeypatch.setattr(validation, "_stat_source", counted_stat)
    report = validate_batch_inputs(model, ["-s1 A", "-s1 B"])
    assert not report.passed
    assert checked == [missing]
    assert report.validation.raster_sources_examined == 0
    assert len([f for f in report.issues if f.kind == "file"]) == 2
    assert all(f.kind != "raster_metadata" for f in report.issues)


def test_no_file_inspection_cache_survives_separate_batch_invocations(
    tmp_path: Path,
) -> None:
    """Rerunning preflight after a model edit must inspect the changed bytes."""
    good = tmp_path / "grid.tif"
    _tiff(good)
    top = tmp_path / "model.tcf"
    top.write_text("Read Grid Zpts == grid.tif\n", encoding="utf-8")
    model = TCF(top, case_sensitivity=0)

    first = validate_batch_inputs(model, ["-s1 A"])
    assert first.passed, first.issues
    good.write_bytes(b"corrupt grid header")
    second = validate_batch_inputs(model, ["-s1 A"])
    assert not second.passed
    assert any(
        f.kind == "raster_metadata" and f.status == "unresolved"
        for f in second.issues
    )


def test_csv_headers_are_inspected_only_in_the_final_batch_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """New metadata checks must not duplicate an existing BC source header."""
    from pytuflow import validation

    database = tmp_path / "bc.csv"
    source = tmp_path / "inflow.csv"
    database.write_text(
        "Name,Source,Column 1,Column 2\nflow,inflow.csv,Time,Flow\n",
        encoding="utf-8",
    )
    source.write_text("Time,Flow\n0,10\n", encoding="utf-8")
    top = tmp_path / "model.tcf"
    top.write_text("BC Database == bc.csv\n", encoding="utf-8")
    model = TCF(top, case_sensitivity=0)

    csv_reads: list[Path] = []
    file_stats: list[Path] = []
    read_csv = validation._csv_records
    stat_source = validation._stat_source

    def counted_csv(path: Path, *args: object, **kwargs: object) -> object:
        csv_reads.append(path)
        return read_csv(path, *args, **kwargs)

    def counted_stat(path: Path) -> tuple[str, str]:
        file_stats.append(path)
        return stat_source(path)

    monkeypatch.setattr(validation, "_csv_records", counted_csv)
    monkeypatch.setattr(validation, "_stat_source", counted_stat)
    result = validate_batch_inputs(model, ["-s1 A", "-s1 B"])

    assert result.passed, result.issues
    assert csv_reads == [source]
    assert sorted(file_stats) == sorted([database, source])
    assert result.validation.csv_headers_examined == 1
    assert result.validation.files_examined == 2


def test_netcdf_strict_warning_filter_is_safe_with_parallel_workers(
    tmp_path: Path,
) -> None:
    """NetCDF-only warning filters must not interfere across IO worker threads."""
    from netCDF4 import Dataset
    from rasterio.errors import NotGeoreferencedWarning

    sources: list[Path] = []
    for index in range(2):
        source = tmp_path / f"rain_{index}.nc"
        with Dataset(source, "w", format="NETCDF4") as dataset:
            dataset.createDimension("lat", 2)
            dataset.createDimension("lon", 2)
            lat = dataset.createVariable("lat", "f8", ("lat",))
            lon = dataset.createVariable("lon", "f8", ("lon",))
            lat.standard_name, lat.units = "latitude", "degrees_north"
            lon.standard_name, lon.units = "longitude", "degrees_east"
            lat[:] = (0.0, 1.0)
            lon[:] = (100.0, 101.0)
            for name in ("rainfall", "other"):
                dataset.createVariable(name, "f4", ("lat", "lon"))
        sources.append(source)

    before = _inventory(tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("error", NotGeoreferencedWarning)
        result = validate_dependencies(
            _projection(_run(0, *(_ref(path, selector="rainfall") for path in sources))),
            options=_options(io_workers=4),
        )
    assert result.passed
    assert result.raster_sources_examined == 2
    assert result.raster_subdatasets_opened == 2
    assert _inventory(tmp_path) == before


@pytest.mark.parametrize("selector,expected", [("rainfall", "present"), ("absent", "unresolved")])
def test_single_variable_netcdf_explicit_selector_is_exact(
    tmp_path: Path,
    selector: str,
    expected: str,
) -> None:
    """GDAL root bands must satisfy their own variable, never an unrelated name."""
    from netCDF4 import Dataset

    from pytuflow._raster_metadata import inspect_raster_headers

    path = tmp_path / "single.nc"
    with Dataset(path, "w") as database:
        database.createDimension("lat", 2)
        database.createDimension("lon", 2)
        for name, values in (("lat", (0.0, 1.0)), ("lon", (100.0, 101.0))):
            coordinate = database.createVariable(name, "f8", (name,))
            coordinate.standard_name = "latitude" if name == "lat" else "longitude"
            coordinate.units = "degrees_north" if name == "lat" else "degrees_east"
            coordinate[:] = values
        database.createVariable("rainfall", "f4", ("lat", "lon"))
    with rasterio.open(path) as root:
        assert root.count == 1 and not root.subdatasets
    before = _inventory(tmp_path)
    results, opens = inspect_raster_headers(path, {selector}, maximum_subdatasets=64)
    assert results[selector][0] == expected
    assert opens == 1
    assert _inventory(tmp_path) == before


def test_netcdf_warning_filter_cannot_hide_another_raster_workers_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On global-filter Python builds, a TIFF must not inherit a NetCDF filter."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from rasterio.errors import NotGeoreferencedWarning

    from pytuflow._raster_metadata import inspect_raster_headers

    netcdf_started, release_netcdf, tiff_started = Event(), Event(), Event()
    expected_message = "Dataset has no geotransform, gcps, or rpcs. The identity matrix will be returned."

    def fake_open(path: Path, mode: str = "r") -> _FakeDataset:
        assert mode == "r"
        if path.suffix == ".nc":
            netcdf_started.set()
            assert release_netcdf.wait(5)
        warnings.warn(expected_message, NotGeoreferencedWarning, stacklevel=1)
        return _FakeDataset(2, 2, 1)

    def inspect_tiff() -> object:
        tiff_started.set()
        return inspect_raster_headers(tmp_path / "unprojected.tif", {None}, maximum_subdatasets=64)

    monkeypatch.setattr(rasterio, "open", fake_open)
    with warnings.catch_warnings():
        warnings.simplefilter("error", NotGeoreferencedWarning)
        with ThreadPoolExecutor(max_workers=2) as executor:
            netcdf = executor.submit(inspect_raster_headers, tmp_path / "container.nc", {None}, maximum_subdatasets=64)
            try:
                assert netcdf_started.wait(5)
                tiff = executor.submit(inspect_tiff)
                assert tiff_started.wait(5)
            finally:
                release_netcdf.set()
            assert netcdf.result()[0][None][0] == "present"
            with pytest.raises(NotGeoreferencedWarning):
                tiff.result()


def test_netcdf_warning_filter_does_not_suppress_unrelated_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrelated warning in the NetCDF driver still reaches the caller."""
    from rasterio.errors import NotGeoreferencedWarning

    from pytuflow._raster_metadata import inspect_raster_headers

    def fake_open(*args: object, **kwargs: object) -> None:
        warnings.warn("Unrelated georeferencing diagnostic", NotGeoreferencedWarning, stacklevel=1)

    monkeypatch.setattr(rasterio, "open", fake_open)
    with pytest.raises(NotGeoreferencedWarning, match="Unrelated"):
        inspect_raster_headers(tmp_path / "container.nc", {None}, maximum_subdatasets=64)
