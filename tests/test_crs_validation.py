"""CRS warnings are read-only, default-on and independent from pass/fail checks."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import rasterio
from pyproj import CRS
from rasterio.transform import from_origin

from pytuflow import TCF
from pytuflow._tmf.dependency_records import BatchDependencyRun, BatchInputReference
from pytuflow._tmf.file_reference import FileReference
from pytuflow.batch_validation import validate_batch_inputs
from pytuflow.validation import ValidationOptions, validate_dependencies


def _raster(path: Path, epsg: int | None) -> None:
    with rasterio.open(
        path, "w", driver="GTiff", width=2, height=2, count=1,
        dtype="float32", crs=f"EPSG:{epsg}" if epsg is not None else None,
        transform=from_origin(300, 500, 1, 1),
    ) as dataset:
        dataset.write(np.zeros((2, 2), dtype="float32"), 1)


def _reference(
    path: Path, *, raster: bool = False, vector: bool = False,
    layer: str | None = None,
) -> FileReference:
    return FileReference(
        base_directory=path.parent, expanded_value=path.name,
        path_pattern=path, layer_pattern=layer,
        origin="Read Grid Zpts" if raster else "Read GIS Code",
        requires_directory_scan=False, requires_layer_scan=layer is not None,
        requires_attribute_scan=False, requires_database_scan=False,
        requires_raster_metadata_scan=raster,
        requires_vector_crs_scan=vector,
    )


def _project(*references: FileReference) -> SimpleNamespace:
    links = tuple(
        BatchInputReference(
            input_uuid=f"source-{i}", command_index=i,
            owner_control_file=reference.base_directory / "model.tcf",
            line_number=i + 1, reference=reference,
        )
        for i, reference in enumerate(references)
    )
    run = BatchDependencyRun(
        index=0, flags="-s1 A", file_references=references,
        database_sources=(), database_activations=(), input_references=links,
    )
    return SimpleNamespace(runs=(run,))


def _options(**changes: object) -> ValidationOptions:
    return ValidationOptions(case_sensitivity=0, **changes)


def _model(tmp_path: Path, gis: str = "", tif: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        fpath=tmp_path / "model.tcf",
        config=SimpleNamespace(projection_wkt=gis, tif_projection=tif),
    )


def _snapshot(tmp_path: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(p.relative_to(tmp_path)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in tmp_path.rglob("*") if p.is_file()
    }


def _gpkg(path: Path, layers: dict[str, int]) -> None:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY)")
        db.execute(
            "CREATE TABLE gpkg_geometry_columns (table_name TEXT, srs_id INTEGER)"
        )
        db.execute(
            "CREATE TABLE gpkg_spatial_ref_sys (srs_id INTEGER, "
            "organization TEXT, organization_coordsys_id TEXT, definition TEXT)"
        )
        for epsg in sorted(set(layers.values())):
            db.execute(
                "INSERT INTO gpkg_spatial_ref_sys VALUES (?, 'EPSG', ?, 'undefined')",
                (epsg, str(epsg)),
            )
        for name, epsg in layers.items():
            db.execute("INSERT INTO gpkg_contents VALUES (?)", (name,))
            db.execute(
                "INSERT INTO gpkg_geometry_columns VALUES (?, ?)",
                (name, epsg),
            )


def test_defaults_are_enabled_and_controls_are_independent() -> None:
    options = ValidationOptions()
    assert options.check_raster_metadata
    assert options.check_crs
    assert not ValidationOptions(
        check_raster_metadata=False, check_crs=False,
    ).check_crs


def test_tcf_projection_is_reference_and_mismatch_only_warns(tmp_path: Path) -> None:
    matching, different = tmp_path / "same.tif", tmp_path / "different.tif"
    _raster(matching, 28350)
    _raster(different, 7850)
    before = _snapshot(tmp_path)
    result = validate_dependencies(
        _project(_reference(matching, raster=True),
                 _reference(different, raster=True)),
        options=_options(),
        model=_model(tmp_path, CRS.from_epsg(28350).to_wkt()),
    )
    assert result.passed
    assert result.raster_sources_examined == 2
    assert result.crs_sources_examined == 2
    assert len(result.warnings) == 1
    warning = result.warnings[0]
    assert warning.kind == "crs" and warning.severity == "warning"
    assert warning.status == "unresolved"
    assert warning.path == different
    assert "EPSG:7850" in warning.detail and "EPSG:28350" in warning.detail
    assert warning.owner_control_file == tmp_path / "model.tcf"
    assert _snapshot(tmp_path) == before


def test_without_tcf_projection_compare_selected_rasters_and_vectors(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "reference.tif"
    different = tmp_path / "different.gpkg"
    _raster(reference, 28350)
    _gpkg(different, {"2d_code": 7850})
    before = _snapshot(tmp_path)
    result = validate_dependencies(
        _project(
            _reference(reference, raster=True),
            _reference(different, vector=True, layer="2d_code"),
        ),
        options=_options(), model=_model(tmp_path),
    )
    assert result.passed
    assert result.crs_sources_examined == 2
    assert len(result.warnings) == 2
    mismatch = [item for item in result.warnings if item.path == different]
    assert len(mismatch) == 1
    assert mismatch[0].layer == "2d_code"
    missing_projection = [item for item in result.warnings if item.path == tmp_path / "model.tcf"]
    assert len(missing_projection) == 1
    assert "No GIS Projection or TIF Projection" in missing_projection[0].detail
    assert _snapshot(tmp_path) == before


def test_gpkg_layer_all_requires_separate_crs_comparison(tmp_path: Path) -> None:
    file = tmp_path / "layers.gpkg"
    _gpkg(file, {"2d_code_A": 28350, "2d_code_B": 7850})
    before = _snapshot(tmp_path)
    result = validate_dependencies(
        _project(_reference(file, vector=True, layer="all")),
        options=_options(), model=_model(tmp_path),
    )
    assert result.passed
    assert result.crs_sources_examined == 1
    source_warnings = [f for f in result.warnings if f.path == file]
    assert [(f.layer, f.kind) for f in source_warnings] == [
        ("2d_code_B", "crs"),
    ]
    assert any("No GIS Projection or TIF Projection" in f.detail for f in result.warnings)
    assert _snapshot(tmp_path) == before


def test_gpkg_null_and_invalid_srs_ids_warn_without_losing_valid_layers(
    tmp_path: Path,
) -> None:
    """Malformed SRS metadata must stay advisory and preserve good layer CRS."""
    from pytuflow._crs_validation import inspect_vector_crs

    path = tmp_path / "mixed_crs.gpkg"
    _gpkg(path, {"good": 28350, "null_srs": 7850, "invalid_srs": 4326})
    with sqlite3.connect(path) as db:
        db.execute(
            "UPDATE gpkg_geometry_columns SET srs_id = NULL "
            "WHERE table_name = 'null_srs'"
        )
        db.execute(
            "UPDATE gpkg_geometry_columns SET srs_id = 'not-an-integer' "
            "WHERE table_name = 'invalid_srs'"
        )
        # Even unrelated malformed reference definitions must not poison
        # the lookup of a valid SRS ID from another layer.
        db.execute(
            "INSERT INTO gpkg_spatial_ref_sys VALUES "
            "(NULL, 'EPSG', '0', 'undefined')"
        )
        db.execute(
            "INSERT INTO gpkg_spatial_ref_sys VALUES "
            "('not-an-integer', 'EPSG', '0', 'undefined')"
        )

    before = _snapshot(tmp_path)
    inspected = inspect_vector_crs(path, {("all", False)})[("all", False)]
    assert {name: (crs, error) for name, crs, error in inspected} == {
        "good": ("EPSG:28350", ""),
        "invalid_srs": (None, "GeoPackage layer lacks spatial CRS metadata"),
        "null_srs": (None, "GeoPackage layer lacks spatial CRS metadata"),
    }

    report = validate_dependencies(
        _project(_reference(path, vector=True, layer="all")),
        options=_options(),
        model=_model(tmp_path, CRS.from_epsg(28350).to_wkt()),
    )
    assert report.passed
    assert report.crs_sources_examined == 1
    assert {warning.layer for warning in report.warnings} == {
        "null_srs", "invalid_srs",
    }
    assert all(
        warning.kind == "crs"
        and warning.severity == "warning"
        and warning.status == "unresolved"
        and "lacks spatial CRS metadata" in warning.detail
        for warning in report.warnings
    )
    assert _snapshot(tmp_path) == before


def test_missing_invalid_crs_warn_and_do_not_crash(tmp_path: Path) -> None:
    path = tmp_path / "unprojected.tif"
    _raster(path, None)
    report = validate_dependencies(
        _project(_reference(path, raster=True)),
        options=_options(),
        model=_model(tmp_path, CRS.from_epsg(28350).to_wkt()),
    )
    assert report.passed
    assert len(report.warnings) == 1
    assert "no declared CRS" in report.warnings[0].detail

    # An invalid model CRS is itself a warning, never an uncaught PROJ error.
    invalid = validate_dependencies(
        _project(_reference(path, raster=True)),
        options=_options(), model=_model(tmp_path, "not a valid projection"),
    )
    assert invalid.passed
    assert len(invalid.warnings) >= 1
    assert any("Cannot interpret TCF projection" in f.detail
               for f in invalid.warnings)


def test_crs_can_be_switched_off_without_disabling_raster_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "grid.tif"
    _raster(path, 28350)
    original = rasterio.open

    class NoCRS:
        def __init__(self, handle: object) -> None:
            self.handle = handle

        def __enter__(self) -> "NoCRS":
            self.handle.__enter__()
            return self

        def __exit__(self, *args: object) -> None:
            self.handle.__exit__(*args)

        def __getattr__(self, name: str) -> object:
            if name in {"crs", "read", "statistics", "overviews"}:
                raise AssertionError(f"Forbidden metadata/pixel access: {name}")
            return getattr(self.handle, name)

    monkeypatch.setattr(
        rasterio, "open",
        lambda name, mode="r": NoCRS(original(name, mode=mode)),
    )
    report = validate_dependencies(
        _project(_reference(path, raster=True)),
        options=_options(check_crs=False),
    )
    assert report.passed
    assert report.raster_sources_examined == 1
    assert report.crs_sources_examined == 0
    assert not report.warnings


def test_crs_only_still_opens_raster_once(tmp_path: Path) -> None:
    path = tmp_path / "grid.tif"
    _raster(path, 7850)
    report = validate_dependencies(
        _project(_reference(path, raster=True)),
        model=_model(tmp_path, CRS.from_epsg(28350).to_wkt()),
        options=_options(check_raster_metadata=False),
    )
    assert report.passed
    assert report.raster_sources_examined == 1
    assert report.crs_sources_examined == 1
    assert any(f.kind == "crs" for f in report.warnings)
    assert not any(f.kind == "raster_metadata" for f in report.findings)


def test_readonly_vector_information_does_not_enumerate_features(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyogrio

    path = tmp_path / "clip.shp"
    for suffix in (".shp", ".dbf", ".shx"):
        path.with_suffix(suffix).write_bytes(b"synthetic")
    called: list[Path] = []

    def metadata_only(name: Path, **kwargs: object) -> dict[str, object]:
        called.append(Path(name))
        assert kwargs.get("layer") is None
        return {"crs": "EPSG:28350"}

    monkeypatch.setattr(pyogrio, "read_info", metadata_only)
    report = validate_dependencies(
        _project(_reference(path, vector=True)),
        model=_model(tmp_path, CRS.from_epsg(28350).to_wkt()),
        options=_options(),
    )
    assert report.passed and not report.warnings
    assert called == [path]
    assert report.crs_sources_examined == 1


def test_batch_tcf_projection_warns_and_preserves_errors(tmp_path: Path) -> None:
    raster = tmp_path / "different.tif"
    _raster(raster, 7850)
    (tmp_path / "reference.prj").write_text(
        CRS.from_epsg(28350).to_wkt(), encoding="utf-8",
    )
    control = tmp_path / "model.tcf"
    control.write_text(
        "GIS Projection == reference.prj\nRead Grid Zpts == different.tif\n",
        encoding="utf-8",
    )
    model = TCF(control, case_sensitivity=0)
    result = validate_batch_inputs(model, ["-s1 A", "-s1 B"])
    assert result.passed, result.issues
    assert len([x for x in result.warnings if x.path == raster]) == 2
    assert result.validation.raster_sources_examined == 1
    assert result.validation.crs_sources_examined >= 1
    assert not result.issues


def test_batch_without_projection_warns_on_different_grids(tmp_path: Path) -> None:
    _raster(tmp_path / "one.tif", 28350)
    _raster(tmp_path / "two.tif", 7850)
    control = tmp_path / "model.tcf"
    control.write_text(
        "Read Grid Zpts == one.tif\nRead Grid Zpts == two.tif\n",
        encoding="utf-8",
    )
    model = TCF(control, case_sensitivity=0)
    result = validate_batch_inputs(model, ["-s1 A"])
    assert result.passed, result.issues
    assert len(result.warnings) == 2
    assert any(
        w.path == tmp_path / "two.tif" and "selected input" in w.detail
        for w in result.warnings
    )
    assert any(
        w.path == control and "No GIS Projection or TIF Projection" in w.detail
        for w in result.warnings
    )


def test_only_one_header_open_for_crs_and_raster_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "grid.tif"
    _raster(path, 28350)
    original = rasterio.open
    calls: list[str] = []

    def counted(name: object, mode: str = "r") -> object:
        calls.append(str(name))
        assert mode == "r"
        return original(name, mode=mode)

    monkeypatch.setattr(rasterio, "open", counted)
    report = validate_dependencies(
        _project(_reference(path, raster=True), _reference(path, raster=True)),
        options=_options(),
    )
    assert report.passed
    assert calls == [str(path)]
    assert report.raster_sources_examined == 1
    assert report.crs_sources_examined == 1
    assert not report.warnings


def test_invalid_tcf_gis_tif_crs_disagreement_is_advisory(tmp_path: Path) -> None:
    path = tmp_path / "terrain.tif"
    _raster(path, 28350)
    report = validate_dependencies(
        _project(_reference(path, raster=True)),
        options=_options(),
        model=_model(
            tmp_path, CRS.from_epsg(28350).to_wkt(),
            CRS.from_epsg(7850).to_wkt(),
        ),
    )
    assert report.passed
    assert any("TIF projection" in w.detail for w in report.warnings)
    assert not any(w.path == path for w in report.warnings)


def test_crs_only_warns_when_existing_raster_header_is_unreadable(
    tmp_path: Path,
) -> None:
    """Disabling blocking headers must not silently certify unreadable CRS."""
    path = tmp_path / "invalid.tif"
    path.write_bytes(b"not a raster")
    report = validate_dependencies(
        _project(_reference(path, raster=True)),
        options=_options(check_raster_metadata=False, check_crs=True),
    )
    assert report.passed
    assert not any(f.kind == "raster_metadata" for f in report.findings)
    assert len(report.warnings) == 1
    assert report.warnings[0].kind == "crs"
    assert "Cannot inspect raster CRS" in report.warnings[0].detail


@pytest.mark.parametrize("flags", [["-s1 A"], ["-s1 B"], ["-s1 A", "-s1 B"]])
def test_projection_reference_uses_each_selected_scenario(tmp_path: Path, flags: list[str]) -> None:
    """Inactive/later projection declarations must not change another run's CRS."""
    for name, epsg in (("A", 28350), ("B", 7850)):
        _raster(tmp_path / f"{name}.tif", epsg)
        (tmp_path / f"{name}.prj").write_text(CRS.from_epsg(epsg).to_wkt(), encoding="utf-8")
    control = tmp_path / "model.tcf"
    control.write_text(
        "If Scenario == A\nGIS Projection == A.prj\nRead Grid Zpts == A.tif\n"
        "Else If Scenario == B\nGIS Projection == B.prj\nRead Grid Zpts == B.tif\nEnd If\n",
        encoding="utf-8",
    )
    model = TCF(control, case_sensitivity=0)
    before = _snapshot(tmp_path)
    result = validate_batch_inputs(model, flags)
    assert result.passed, result.issues
    assert not result.warnings
    assert _snapshot(tmp_path) == before
    # A real mismatch must still be attributed to that run, not the model's
    # last projection (B), whose CRS happens to match this altered input.
    _raster(tmp_path / "A.tif", 7850)
    result = validate_batch_inputs(model, flags)
    expected = [index for index, flag in enumerate(flags) if flag == "-s1 A"]
    assert [w.run_index for w in result.warnings] == expected
    assert all("EPSG:28350" in w.detail and w.path == tmp_path / "A.tif" for w in result.warnings)


def test_unselected_projection_does_not_become_no_projection_reference(tmp_path: Path) -> None:
    """Each simulation without a projection chooses its own selected baseline."""
    _raster(tmp_path / "A.tif", 28350)
    _raster(tmp_path / "B.tif", 7850)
    (tmp_path / "reference.prj").write_text(CRS.from_epsg(7850).to_wkt(), encoding="utf-8")
    control = tmp_path / "model.tcf"
    control.write_text(
        "If Scenario == A\nRead Grid Zpts == A.tif\n"
        "Else If Scenario == B\nRead Grid Zpts == B.tif\n"
        "Else If Scenario == C\nGIS Projection == reference.prj\nEnd If\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(TCF(control, case_sensitivity=0), ["-s1 A", "-s1 B"])
    assert result.passed, result.issues
    assert [w.run_index for w in result.warnings] == [0, 1]
    assert all(
        "No GIS Projection or TIF Projection" in w.detail
        and w.path == control and w.severity == "warning"
        for w in result.warnings
    )


def test_selected_gis_projection_overrides_conflicting_tif_projection(tmp_path: Path) -> None:
    """Name both references once, and prefer the active GIS projection."""
    _raster(tmp_path / "projection.tif", 7850)
    _raster(tmp_path / "grid.tif", 28350)
    (tmp_path / "reference.prj").write_text(
        CRS.from_epsg(28350).to_wkt(), encoding="utf-8",
    )
    control = tmp_path / "model.tcf"
    control.write_text(
        "GIS Projection == reference.prj\nTIF Projection == projection.tif\nRead Grid Zpts == grid.tif\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(TCF(control, case_sensitivity=0), ["-s1 A"])
    assert result.passed
    assert len(result.warnings) == 1
    assert "TCF GIS projection EPSG:28350 and TIF projection EPSG:7850 differ" in result.warnings[0].detail


_MAPINFO_COORDSYS = (
    'CoordSys Earth Projection 8, 104, "m", 177, 0, '
    '0.9996, 500000, 10000000'
)


def test_inline_mapinfo_crs_uses_existing_converter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Native MapInfo CoordSys must be converted before parsing by PROJ."""
    from pytuflow._crs_validation import parse_crs, same_crs
    from pytuflow._tmf import gis

    called: list[str] = []

    def convert(value: str) -> str:
        called.append(value)
        return CRS.from_epsg(28350).to_wkt()

    monkeypatch.setattr(gis, "mi_projection", convert)
    assert same_crs(parse_crs(_MAPINFO_COORDSYS), CRS.from_epsg(28350))
    assert called == [_MAPINFO_COORDSYS]
    # Already supported EPSG strings must never invoke MapInfo conversion.
    assert same_crs(parse_crs("EPSG:28350"), CRS.from_epsg(28350))
    assert called == [_MAPINFO_COORDSYS]


def test_inline_mapinfo_projection_is_selected_tcf_crs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid MI Projection must override inter-source fallback for this run."""
    from pytuflow._tmf import gis

    converted: list[str] = []

    def convert(value: str) -> str:
        converted.append(value)
        return CRS.from_epsg(28350).to_wkt()

    monkeypatch.setattr(gis, "mi_projection", convert)
    raster = tmp_path / "grid.tif"
    _raster(raster, 28350)
    model_path = tmp_path / "model.tcf"
    model_path.write_text(
        f"MI Projection == {_MAPINFO_COORDSYS}\n"
        "Read Grid Zpts == grid.tif\n", encoding="utf-8",
    )
    model = TCF(model_path, case_sensitivity=0)

    good = validate_batch_inputs(model, ["-s1 A"])
    assert good.passed, good.issues
    assert not good.warnings
    assert converted and set(converted) == {_MAPINFO_COORDSYS}

    # Changing only the raster must warn against the declared MI reference.
    _raster(raster, 7850)
    wrong = validate_batch_inputs(model, ["-s1 A"])
    assert wrong.passed, wrong.issues
    assert len(wrong.warnings) == 1
    assert wrong.warnings[0].path == raster
    assert "EPSG:7850" in wrong.warnings[0].detail
    assert "EPSG:28350" in wrong.warnings[0].detail
    assert "selected input" not in wrong.warnings[0].detail


def test_inline_mapinfo_converter_failure_is_advisory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing native OSR bindings must warn, never crash validation."""
    from pytuflow._tmf import gis

    def unavailable(_value: str) -> str:
        raise NotImplementedError("GDAL/OSR Python bindings unavailable")

    monkeypatch.setattr(gis, "mi_projection", unavailable)
    grid = tmp_path / "grid.tif"
    _raster(grid, 28350)
    model_path = tmp_path / "model.tcf"
    model_path.write_text(
        f"MI Projection == {_MAPINFO_COORDSYS}\n"
        "Read Grid Zpts == grid.tif\n", encoding="utf-8",
    )
    result = validate_batch_inputs(
        TCF(model_path, case_sensitivity=0), ["-s1 A"],
    )
    assert result.passed, result.issues
    assert any(
        "Cannot interpret TCF projection" in warning.detail
        for warning in result.warnings
    )


def test_real_mapinfo_coordsys_conversion_in_native_gdal() -> None:
    """Exercise actual PyTUFLOW OSR conversion when native bindings exist."""
    pytest.importorskip("osgeo.osr")
    from pytuflow._crs_validation import parse_crs

    converted = parse_crs(_MAPINFO_COORDSYS)
    assert converted.is_projected
    assert converted.to_wkt()


@pytest.mark.parametrize(
    ("flags", "expected_missing"),
    [
        (["-s1 A"], [0]),
        (["-s1 B"], []),
        (["-s1 A", "-s1 B"], [0]),
        (["-s1 B", "-s1 A"], [1]),
    ],
)
def test_missing_tcf_projection_warns_only_for_selected_runs(
    tmp_path: Path,
    flags: list[str],
    expected_missing: list[int],
) -> None:
    """An inactive projection must not suppress another run's missing warning."""
    _raster(tmp_path / "A.tif", 28350)
    _raster(tmp_path / "B.tif", 7850)
    (tmp_path / "B.prj").write_text(
        CRS.from_epsg(7850).to_wkt(), encoding="utf-8",
    )
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "If Scenario == A\n"
        "Read Grid Zpts == A.tif\n"
        "Else If Scenario == B\n"
        "GIS Projection == B.prj\n"
        "Read Grid Zpts == B.tif\n"
        "End If\n",
        encoding="utf-8",
    )
    model = TCF(tcf, case_sensitivity=0)
    report = validate_batch_inputs(model, flags)
    assert report.passed, report.issues
    assert not report.issues
    assert [w.run_index for w in report.warnings] == expected_missing
    assert all(
        w.path == tcf
        and w.kind == "crs"
        and w.status == "unresolved"
        and w.severity == "warning"
        and w.origin == "TCF Projection"
        and "No GIS Projection or TIF Projection" in w.detail
        for w in report.warnings
    )
    assert report.validation.passed


def test_missing_tcf_projection_warns_even_when_all_input_crs_match(
    tmp_path: Path,
) -> None:
    """Input agreement does not establish an authoritative TCF projection."""
    for filename in ("first.tif", "second.tif"):
        _raster(tmp_path / filename, 28350)
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "Read Grid Zpts == first.tif\n"
        "Read Grid Zpts == second.tif\n",
        encoding="utf-8",
    )
    model = TCF(tcf, case_sensitivity=0)
    report = validate_batch_inputs(model, ["-s1 A", "-s1 B"])
    assert report.passed
    assert not report.issues
    assert [w.run_index for w in report.warnings] == [0, 1]
    assert all(w.path == tcf for w in report.warnings)
    assert all(
        "No GIS Projection or TIF Projection" in w.detail
        for w in report.warnings
    )


def test_missing_tcf_projection_warning_respects_crs_opt_out(
    tmp_path: Path,
) -> None:
    _raster(tmp_path / "grid.tif", 28350)
    tcf = tmp_path / "model.tcf"
    tcf.write_text("Read Grid Zpts == grid.tif\n", encoding="utf-8")
    model = TCF(tcf, case_sensitivity=0)
    report = validate_batch_inputs(
        model, ["-s1 A"],
        options=ValidationOptions(case_sensitivity=0, check_crs=False),
    )
    assert report.passed and not report.issues
    assert not report.warnings
