"""Selected 1D BC dependencies and geometry-only rainfall triangulation.

Synthetic temporary files only; no TUFLOW solver or original example data.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point, Polygon

from pytuflow.batch_validation import validate_batch_inputs
from pytuflow.validation import ValidationOptions
from pytuflow.validation_gis import inspect_gis_attribute_sources


def _boundary_layer(
    root: Path,
    rows: list[tuple[str, str, str]],
    *,
    provider: str = "gpkg",
) -> tuple[Path, str]:
    layer = "1d_bc_external"
    if provider == "shp":
        path = root / f"{layer}.shp"
        frame = gpd.GeoDataFrame(
            rows,
            columns=["Type", "Flags", "Name"],
            geometry=[Point(index, 0) for index in range(len(rows))],
            crs="EPSG:28350",
        )
        frame.to_file(path)
        return path, path.name
    path = root / "boundaries.gpkg"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        db.execute("INSERT INTO gpkg_contents VALUES (?)", (layer,))
        db.execute(
            "CREATE TABLE gpkg_geometry_columns "
            "(table_name TEXT, column_name TEXT, geometry_type_name TEXT)"
        )
        db.execute(
            "INSERT INTO gpkg_geometry_columns VALUES (?, 'geom', 'POINT')", (layer,)
        )
        db.execute(
            f'CREATE TABLE "{layer}" (fid INTEGER PRIMARY KEY, Type TEXT, Flags TEXT, Name TEXT, geom BLOB)'
        )
        db.executemany(
            f'INSERT INTO "{layer}" (Type, Flags, Name) VALUES (?, ?, ?)', rows
        )
    return path, f"{path.name} >> {layer}"


def _model(root: Path, reference: str) -> Path:
    (root / "bc.csv").write_text(
        "Name,Source,Column 1,Column 2\n"
        "Flow,inflow.csv,Time,Flow\nStage,stage.csv,Time,Level\n"
        "Unused,unused-missing.csv,Time,Flow\n",
        encoding="utf-8",
    )
    (root / "inflow.csv").write_text("Time,Flow\n0,1\n", encoding="utf-8")
    (root / "stage.csv").write_text("Time,Level\n0,10\n", encoding="utf-8")
    (root / "model.ecf").write_text(f"Read GIS BC == {reference}\n", encoding="utf-8")
    top = root / "model.tcf"
    top.write_text(
        "BC Database == bc.csv\nESTRY Control File == model.ecf\n", encoding="utf-8"
    )
    return top


def _options() -> ValidationOptions:
    return ValidationOptions(
        check_raster_metadata=False, check_crs=False, check_bc_csv_headers=True
    )


@pytest.mark.parametrize("provider", ["shp", "gpkg"])
def test_selected_1d_boundary_sources_and_headers(
    tmp_path: Path, provider: str
) -> None:
    _, reference = _boundary_layer(
        tmp_path,
        [("QT", "", "Flow"), ("HT", "S", "Stage"), ("HQ", "", "slope=0.01")],
        provider=provider,
    )
    top = _model(tmp_path, reference)
    result = validate_batch_inputs(
        top, [{"s1": "Existing"}, {"s1": "Future"}], options=_options()
    )
    assert result.passed, result.issues
    assert result.validation.csv_headers_examined == 2
    checked = {finding.path for finding in result.validation.findings}
    assert {tmp_path / "inflow.csv", tmp_path / "stage.csv"} <= checked
    assert tmp_path / "unused-missing.csv" not in checked

    (tmp_path / "inflow.csv").unlink()
    missing = validate_batch_inputs(
        top, ["-s1 Existing", "-s1 Future"], options=_options()
    )
    assert not missing.passed
    selected = [
        issue for issue in missing.issues if issue.path == tmp_path / "inflow.csv"
    ]
    assert {issue.run_index for issue in selected} == {0, 1}
    assert all(issue.status == "missing" for issue in selected)
    assert all(
        issue.owner_control_file == top and issue.origin == "BC Database"
        for issue in selected
    )
    assert all(issue.input_uuid and issue.command_index >= 0 for issue in selected)
    assert not any(
        issue.path == tmp_path / "unused-missing.csv" for issue in missing.issues
    )


def test_selected_1d_source_csv_header_failure(tmp_path: Path) -> None:
    _, reference = _boundary_layer(tmp_path, [("QH", "", "Flow")])
    top = _model(tmp_path, reference)
    (tmp_path / "inflow.csv").write_text("Time,Wrong\n0,1\n", encoding="utf-8")
    result = validate_batch_inputs(top, ["-e1 A"], options=_options())
    assert not result.passed
    assert any(
        issue.kind == "csv_header" and "Flow" in issue.detail for issue in result.issues
    )


@pytest.mark.parametrize("name", ["slope=0.01", " SLOPE = 1e-3 "])
def test_automatic_1d_hq_needs_no_database(tmp_path: Path, name: str) -> None:
    _, reference = _boundary_layer(tmp_path, [("HQ", "", name), ("QT", "T", "")])
    top = tmp_path / "model.tcf"
    top.write_text(f"Read GIS BC == {reference}\n", encoding="utf-8")
    result = validate_batch_inputs(top, [""], options=_options())
    assert result.passed, result.issues
    assert result.validation.csv_headers_examined == 0


@pytest.mark.parametrize(
    "row",
    [
        ("QT", "", ""),
        ("QT", "", "<<missing>>"),
        ("XX", "", "Flow"),
        ("HQ", "", "slope=0"),
        ("HQ", "", "slope=-1"),
        ("HQ", "", "slope=nan"),
        ("HQ", "", "slope=inf"),
        ("HQ", "", "slope=oops"),
    ],
)
def test_invalid_1d_boundary_stays_unresolved(
    tmp_path: Path, row: tuple[str, str, str]
) -> None:
    path, _ = _boundary_layer(tmp_path, [row])
    request = (path, "1d_bc_external", True)
    result, _ = inspect_gis_attribute_sources({request})
    assert result[request].status == "unresolved"
    assert result[request].bc_identifiers == ()


def test_incomplete_1d_schema_stays_unresolved(tmp_path: Path) -> None:
    path, _ = _boundary_layer(tmp_path, [("QT", "", "Flow")])
    with sqlite3.connect(path) as db:
        db.execute('ALTER TABLE "1d_bc_external" DROP COLUMN Name')
    request = (path, "1d_bc_external", True)
    result, _ = inspect_gis_attribute_sources({request})
    assert result[request].status == "unresolved"
    assert "columns" in result[request].detail


@pytest.mark.parametrize("command", ["Read GIS RF Triangle", "Read MI RF Triangle"])
@pytest.mark.parametrize("provider", ["shp", "gpkg"])
def test_rainfall_triangle_blank_attributes_are_not_bc_names(
    tmp_path: Path,
    command: str,
    provider: str,
) -> None:
    points = tmp_path / "2d_rf_points.shp"
    triangles = tmp_path / f"2d_rf_triangles.{provider}"
    triangle_reference = (
        triangles.name if provider == "shp" else f"{triangles.name} >> 2d_rf_triangles"
    )
    gpd.GeoDataFrame(
        {"Name": ["Rain"]}, geometry=[Point(0, 0)], crs="EPSG:28350"
    ).to_file(points)
    gpd.GeoDataFrame(
        {"Name": [""], "f1": [0.0], "f2": [0.0]},
        geometry=[Polygon([(0, 0), (1, 0), (0, 1)])],
        crs="EPSG:28350",
    ).to_file(triangles, layer="2d_rf_triangles" if provider == "gpkg" else None)
    (tmp_path / "bc.csv").write_text(
        "Name,Source,Column 1,Column 2\nRain,rain.csv,Time,Rain\n",
        encoding="utf-8",
    )
    (tmp_path / "rain.csv").write_text("Time,Rain\n0,5\n", encoding="utf-8")
    (tmp_path / "rain.trfc").write_text(
        f"Read GIS RF Points == {points.name}\nRF Interpolation Method == TIN\n"
        f"{command} == {triangle_reference}\n",
        encoding="utf-8",
    )
    top = tmp_path / "model.tcf"
    top.write_text(
        "BC Database == bc.csv\nRainfall Control File == rain.trfc\n", encoding="utf-8"
    )
    result = validate_batch_inputs(top, ["-e1 A", "-e1 B"], options=_options())
    assert result.passed, result.issues
    assert result.validation.csv_headers_examined == 1
    assert any(
        finding.path == tmp_path / "rain.csv" for finding in result.validation.findings
    )

    if provider == "gpkg":
        # An absent selected layer must still fail physical validation.
        (tmp_path / "rain.trfc").write_text(
            f"{command} == {triangles.name} >> absent\n",
            encoding="utf-8",
        )
    else:
        triangles.with_suffix(".shx").unlink()
    missing = validate_batch_inputs(top, ["-e1 A"], options=_options())
    assert not missing.passed
    assert any(
        issue.path == triangles
        and issue.status == "missing"
        and (issue.layer == "absent" if provider == "gpkg" else ".shx" in issue.detail)
        for issue in missing.issues
    )
