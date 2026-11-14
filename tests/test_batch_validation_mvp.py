"""End-to-end checks of the separate deferred batch parser and file validator.

Fixtures are synthetic and use only temporary local files; TUFLOW, GDAL and
QGIS solvers/providers are never launched. Physical checks are explicit.
"""

from __future__ import annotations

import os
import sqlite3
from collections import OrderedDict
from pathlib import Path
from unittest.mock import patch

import pytest

from pytuflow import TCF
from pytuflow.batch_validation import validate_batch_inputs
from pytuflow.validation import ValidationOptions


def _gpkg(path: Path, *layers: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY)")
        connection.executemany(
            "INSERT INTO gpkg_contents (table_name) VALUES (?)",
            ((name,) for name in layers),
        )


def test_existing_files_and_named_layers_across_conditional_runs(tmp_path: Path) -> None:
    _gpkg(tmp_path / "dev.gpkg", "2d_code")
    _gpkg(tmp_path / "exg.gpkg", "2d_code")
    (tmp_path / "model.tcf").write_text(
        "If Scenario == DEV\n"
        " Read GIS Code == dev.gpkg >> 2d_code\n"
        "Else\n"
        " Read GIS Code == exg.gpkg >> 2d_code\n"
        "End If\n",
        encoding="utf-8",
    )
    model = TCF(tmp_path / "model.tcf")
    flags = ["-s1 DEV -e1 E1", "-s1 EXG -e1 E1"]
    result = validate_batch_inputs(model, flags)
    assert result.passed, result.issues
    assert result.validation.run_count == 2
    assert result.validation.geopackages_examined == 2
    assert result.validation.files_examined == 2
    assert sum(x.kind == "layer" for x in result.validation.findings) == 2
    assert result.dependencies.runs == model.collect_file_dependencies(flags).runs


def test_bc_source_key_preserves_provenance_delimiter(tmp_path: Path) -> None:
    _bc_gpkg(tmp_path / 'bc.gpkg', name='Inlet row 1')
    (tmp_path / 'bc.csv').write_text(
        'Name,Source,Column 1,Column 2\nInlet row 1,inflow.csv,Time,Flow\n', encoding='utf-8',
    )
    (tmp_path / 'inflow.csv').write_text('Time,Flow\n0,10\n', encoding='utf-8')
    top = tmp_path / 'model.tcf'
    top.write_text('BC Database == bc.csv\nRead GIS BC == bc.gpkg >> 2d_bc_lines\n', encoding='utf-8')
    result = validate_batch_inputs(top, ['-s1 Existing'])
    assert result.passed, result.issues
    assert result.dependencies.runs[0].database_sources[0].entry_name == 'Inlet row 1'
    assert result.validation.csv_headers_examined == 1


def test_nonexistent_layer_is_reported_for_exact_run(tmp_path: Path) -> None:
    _gpkg(tmp_path / "model.gpkg", "other_layer")
    (tmp_path / "model.tcf").write_text(
        "Read GIS Code == model.gpkg >> 2d_code\n", encoding="utf-8"
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 DEV"])
    assert not result.passed
    assert any(
        issue.kind == "layer"
        and issue.status == "missing"
        and issue.layer == "2d_code"
        and issue.run_index == 0
        for issue in result.issues
    ), result.issues


def test_missing_files_do_not_pass_even_with_complete_syntax(tmp_path: Path) -> None:
    (tmp_path / "model.tcf").write_text(
        "Read Grid Zpts == missing_<<~s1~>>.tif\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 DEV", "-s1 EXG"])
    assert result.dependencies.passed
    assert not result.passed
    assert {x.run_index for x in result.issues} == {0, 1}
    assert all(x.status == "missing" for x in result.issues)


def test_shared_csv_header_checked_once_and_wrong_columns_fail(tmp_path: Path) -> None:
    (tmp_path / "bc.csv").write_text(
        "Name,Source,Column 1,Column 2\n"
        "flow,inflow.csv,Time,Flow\n",
        encoding="utf-8",
    )
    (tmp_path / "inflow.csv").write_text("Time,Flow\n0,10\n", encoding="utf-8")
    (tmp_path / "model.tcf").write_text(
        "BC Database == bc.csv\n",
        encoding="utf-8",
    )
    flags = ["-s1 EXG -e1 A", "-s1 DEV -e1 B"]
    result = validate_batch_inputs(tmp_path / "model.tcf", flags)
    assert result.passed, result.issues
    assert result.validation.csv_headers_examined == 1

    (tmp_path / "inflow.csv").write_text("Time,WrongColumn\n0,10\n", encoding="utf-8")
    invalid = validate_batch_inputs(tmp_path / "model.tcf", flags)
    assert not invalid.passed
    assert {
        item.run_index
        for item in invalid.issues
        if item.kind == "csv_header"
    } == {0, 1}


def test_wildcard_layers_and_physical_files_are_all_checked(tmp_path: Path) -> None:
    _gpkg(tmp_path / "terrain_A.gpkg", "terrain_A")
    _gpkg(tmp_path / "terrain_B.gpkg", "terrain_B")
    (tmp_path / "model.tcf").write_text(
        "Read GIS Code == terrain_*.gpkg\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 DEV"])
    assert result.passed, result.issues
    assert result.validation.geopackages_examined == 2
    assert {
        f.layer for f in result.validation.findings if f.kind == "layer"
    } == {"terrain_A", "terrain_B"}


def test_fail_closed_context_does_not_inspect_partial_references(tmp_path: Path) -> None:
    (tmp_path / "model.tcf").write_text(
        "Read Grid Zpts == some_grid.tif\n"
        "If Scenario == BAD\n PAUSE\nEnd If\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 BAD", "-s1 GOOD"])
    assert not result.passed
    assert any(x.kind == "context" and x.run_index == 0 for x in result.issues)
    assert all(
        x.run_index != 0 or x.kind == "context"
        for x in result.validation.findings
    )


def test_validation_options_cannot_conflict_with_parsed_case_policy(tmp_path: Path) -> None:
    (tmp_path / "model.tcf").write_text("Read Grid Zpts == terrain.tif\n", encoding="utf-8")
    parsed = TCF(tmp_path / "model.tcf", case_sensitivity=0)
    with pytest.raises(ValueError, match="case_sensitivity"):
        validate_batch_inputs(
            parsed, ["-s1 EXG"],
            options=ValidationOptions(case_sensitivity=2),
        )


def test_dependency_collection_does_not_provoke_physical_checks(tmp_path: Path) -> None:
    (tmp_path / "model.tcf").write_text("Read Grid Zpts == grid.tif\n", encoding="utf-8")
    parsed = TCF(tmp_path / "model.tcf")
    with (
        patch.object(Path, "open", side_effect=AssertionError("open")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
    ):
        projected = parsed.collect_file_dependencies(["-s1 EXG", "-s1 DEV"])
    assert projected.passed


def _linked_gpkg(path: Path, *, layer: str, file_name: str) -> None:
    """One real GPKG attribute table with the first TUFLOW file field."""
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY)")
        connection.execute(
            "INSERT INTO gpkg_contents (table_name) VALUES (?)", (layer,)
        )
        connection.execute(
            "CREATE TABLE gpkg_geometry_columns "
            "(table_name TEXT, column_name TEXT, geometry_type_name TEXT)"
        )
        connection.execute(
            "INSERT INTO gpkg_geometry_columns "
            "(table_name, column_name, geometry_type_name) VALUES (?, ?, ?)",
            (layer, "geom", "LINESTRING"),
        )
        connection.execute(
            f'CREATE TABLE "{layer}" (fid INTEGER PRIMARY KEY, geom BLOB, Source TEXT)'
        )
        connection.execute(
            f'INSERT INTO "{layer}" (Source) VALUES (?)', (file_name,)
        )


def test_gpkg_feature_linked_csv_must_exist(tmp_path: Path) -> None:
    gpkg = tmp_path / "links.gpkg"
    _linked_gpkg(gpkg, layer="1d_xs_link", file_name="xs_data.csv")
    (tmp_path / "xs_data.csv").write_text("chainage,z\n0,1\n", encoding="utf-8")
    (tmp_path / "model.tcf").write_text(
        "Read GIS Code == links.gpkg >> 1d_xs_link\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert result.passed, result.issues
    assert result.gis_sources_added == 1
    assert result.gis_files_scanned == 1
    assert result.validation.files_examined == 2
    assert any(
        item.path and item.path.name == "xs_data.csv"
        and item.kind == "file" and item.status == "present"
        for item in result.validation.findings
    )

    (tmp_path / "xs_data.csv").unlink()
    missing = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert not missing.passed
    assert any(
        item.kind == "file" and item.status == "missing"
        and item.path and item.path.name == "xs_data.csv"
        for item in missing.issues
    )


def test_attribute_linked_sources_are_checked_for_each_run(tmp_path: Path) -> None:
    _linked_gpkg(tmp_path / "links.gpkg", layer="1d_xs_link", file_name="data.csv")
    (tmp_path / "data.csv").write_text("x,z\n0,2\n", encoding="utf-8")
    (tmp_path / "model.tcf").write_text(
        "Read GIS Code == links.gpkg >> 1d_xs_link\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-e1 A", "-e1 B"])
    assert result.passed, result.issues
    assert result.gis_files_scanned == 1
    assert result.gis_sources_added == 2
    assert result.validation.files_examined == 2


def test_unknown_gis_attribute_schema_fails_closed(tmp_path: Path) -> None:
    gpkg = tmp_path / "invalid.gpkg"
    with sqlite3.connect(gpkg) as connection:
        connection.execute("CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY)")
        connection.execute(
            "INSERT INTO gpkg_contents VALUES ('1d_xs_bad')"
        )
        connection.execute(
            "CREATE TABLE gpkg_geometry_columns "
            "(table_name TEXT, column_name TEXT, geometry_type_name TEXT)"
        )
        connection.execute(
            "INSERT INTO gpkg_geometry_columns VALUES "
            "('1d_xs_bad', 'geom', 'LINESTRING')"
        )
        connection.execute('CREATE TABLE "1d_xs_bad" (fid INTEGER PRIMARY KEY, geom BLOB)')
    (tmp_path / "model.tcf").write_text(
        "Read GIS Code == invalid.gpkg >> 1d_xs_bad\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert not result.passed
    assert any(
        item.kind == "attribute" and item.status == "unresolved"
        for item in result.issues
    )


def _bc_gpkg(path: Path, *, name: str) -> None:
    layer = "2d_bc_lines"
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE gpkg_contents (table_name TEXT PRIMARY KEY)")
        con.execute("INSERT INTO gpkg_contents VALUES (?)", (layer,))
        con.execute(
            "CREATE TABLE gpkg_geometry_columns "
            "(table_name TEXT, column_name TEXT, geometry_type_name TEXT)"
        )
        con.execute(
            "INSERT INTO gpkg_geometry_columns VALUES (?, 'geom', 'LINESTRING')",
            (layer,),
        )
        con.execute(
            f'CREATE TABLE "{layer}" '
            "(fid INTEGER PRIMARY KEY, geom BLOB, "
            "Type TEXT, Flags TEXT, Name TEXT, f4 TEXT, f5 TEXT, "
            "f6 TEXT, f7 TEXT, b REAL)"
        )
        con.execute(
            f'INSERT INTO "{layer}" (Type, Flags, Name, b) VALUES (?, ?, ?, ?)',
            ("QT", "", name, None),
        )


@pytest.mark.parametrize("read_command", ["Read GIS BC", "Read MI BC"])
def test_missing_active_bc_identifier_fails_closed(
    tmp_path: Path, read_command: str,
) -> None:
    _bc_gpkg(tmp_path / "bc.gpkg", name="NOT_IN_DATABASE")
    (tmp_path / "bc.csv").write_text(
        "Name,Source,Column 1,Column 2\nvalid,inflow.csv,Time,Flow\n",
        encoding="utf-8",
    )
    (tmp_path / "inflow.csv").write_text(
        "Time,Flow\n0,1\n", encoding="utf-8"
    )
    (tmp_path / "model.tcf").write_text(
        "BC Database == bc.csv\n"
        f"{read_command} == bc.gpkg >> 2d_bc_lines\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert not result.passed
    assert any(
        finding.kind == "attribute"
        and "NOT_IN_DATABASE" in finding.detail
        for finding in result.issues
    ), result.issues


def test_feature_linked_wildcard_geopackages_scan_every_match(tmp_path: Path) -> None:
    _linked_gpkg(tmp_path / "link_A.gpkg", layer="1d_xs_link", file_name="A.csv")
    _linked_gpkg(tmp_path / "link_B.gpkg", layer="1d_xs_link", file_name="B.csv")
    for name in ("A.csv", "B.csv"):
        (tmp_path / name).write_text("X,Z\n0,1\n", encoding="utf-8")
    (tmp_path / "model.tcf").write_text(
        "Read GIS Code == link_*.gpkg >> 1d_xs_link\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert result.passed, result.issues
    assert result.gis_files_scanned == 2
    assert result.gis_sources_added == 2
    assert result.validation.files_examined == 4


def test_missing_root_control_file_cannot_pass_empty_inventory(tmp_path: Path) -> None:
    missing = tmp_path / "absent.tcf"
    with pytest.raises(FileNotFoundError, match="was not loaded"):
        validate_batch_inputs(missing, ["-s1 DEV"])
    model = TCF(missing)
    assert not model.loaded
    with pytest.raises(FileNotFoundError, match="was not loaded"):
        validate_batch_inputs(model, ["-s1 DEV"])
    with pytest.raises(ValueError, match="empty, unnamed"):
        validate_batch_inputs(TCF(), ["-s1 DEV"])


@pytest.mark.parametrize("database_first", [True, False])
@pytest.mark.parametrize("read_command", ["Read GIS BC", "Read MI BC"])
def test_unused_bc_database_source_does_not_create_missing_file(
    tmp_path: Path, database_first: bool, read_command: str,
) -> None:
    _bc_gpkg(tmp_path / "bc.gpkg", name="valid")
    (tmp_path / "bc.csv").write_text(
        "Name,Source,Column 1,Column 2\n"
        "valid,inflow.csv,Time,Flow\n"
        "unused,not_loaded.csv,Time,Flow\n",
        encoding="utf-8",
    )
    (tmp_path / "inflow.csv").write_text("Time,Flow\n0,5\n", encoding="utf-8")
    database = "BC Database == bc.csv\n"
    gis = f"{read_command} == bc.gpkg >> 2d_bc_lines\n"
    (tmp_path / "model.tcf").write_text(
        database + gis if database_first else gis + database,
        encoding="utf-8",
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-e1 Q10", "-e1 Q100"])
    assert result.passed, result.issues
    assert result.validation.csv_headers_examined == 1
    assert result.validation.files_examined == 3
    assert not (tmp_path / "not_loaded.csv").exists()
    # Syntactic data records are unchanged: only the validation-only
    # projection excludes BC rows not referenced by active GIS features.
    assert all(
        any(x.entry_name == "unused" for x in run.database_sources)
        for run in result.dependencies.runs
    )


def test_late_conditional_database_binds_nested_bcf(tmp_path: Path) -> None:
    _bc_gpkg(tmp_path / "bc.gpkg", name="flow")
    (tmp_path / "nested.tbc").write_text(
        "Read GIS BC == bc.gpkg >> 2d_bc_lines\n", encoding="utf-8"
    )
    for name in ("dev", "exg"):
        (tmp_path / f"{name}.csv").write_text(
            f"Name,Source,Column 1,Column 2\nflow,{name}_flow.csv,Time,Flow\n",
            encoding="utf-8",
        )
        (tmp_path / f"{name}_flow.csv").write_text("Time,Flow\n0,1\n", encoding="utf-8")
    (tmp_path / "model.tcf").write_text(
        "BC Control File == nested.tbc\n"
        "If Scenario == DEV\n BC Database == dev.csv\n"
        "Else\n BC Database == exg.csv\nEnd If\n", encoding="utf-8"
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 DEV", "-s1 EXG"])
    assert result.passed, result.issues
    assert result.validation.csv_headers_examined == 2
    for index, name in enumerate(("dev", "exg")):
        checked = {
            item.path for item in result.validation.findings
            if item.run_index == index and item.kind == "file"
        }
        assert tmp_path / f"{name}_flow.csv" in checked
        other = "exg" if name == "dev" else "dev"
        assert tmp_path / f"{other}_flow.csv" not in checked


def test_multiple_late_bc_databases_remain_ambiguous(tmp_path: Path) -> None:
    _bc_gpkg(tmp_path / "bc.gpkg", name="flow")
    for name in ("first", "second"):
        (tmp_path / f"{name}.csv").write_text(
            "Name,Source,Column 1,Column 2\nflow,inflow.csv,Time,Flow\n",
            encoding="utf-8",
        )
    (tmp_path / "inflow.csv").write_text("Time,Flow\n0,1\n", encoding="utf-8")
    (tmp_path / "model.tcf").write_text(
        "Read GIS BC == bc.gpkg >> 2d_bc_lines\n"
        "BC Database == first.csv\nBC Database == second.csv\n", encoding="utf-8"
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert not result.passed
    assert any("no preceding active BC Database" in item.detail for item in result.issues)
    assert result.validation.csv_headers_examined == 0


def test_multiple_active_bc_database_declarations_select_by_order(tmp_path: Path) -> None:
    _bc_gpkg(tmp_path / "first.gpkg", name="FIRST")
    _bc_gpkg(tmp_path / "second.gpkg", name="SECOND")
    for basename, name in (("first", "FIRST"), ("second", "SECOND")):
        (tmp_path / f"{basename}.csv").write_text(
            f"Name,Source,Column 1,Column 2\n{name},{basename}_inflow.csv,Time,Flow\n"
            f"unused_{basename},missing_{basename}.csv,Time,Flow\n",
            encoding="utf-8",
        )
        (tmp_path / f"{basename}_inflow.csv").write_text(
            "Time,Flow\n0,2\n", encoding="utf-8"
        )
    (tmp_path / "model.tcf").write_text(
        "BC Database == first.csv\n"
        "Read GIS BC == first.gpkg >> 2d_bc_lines\n"
        "BC Database == second.csv\n"
        "Read GIS BC == second.gpkg >> 2d_bc_lines\n",
        encoding="utf-8",
    )
    report = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert report.passed, report.issues
    assert report.validation.csv_headers_examined == 2
    assert report.validation.files_examined == 6
    assert len(report.dependencies.runs[0].database_activations) == 2


def test_bc_all_selector_with_no_bc_layers_cannot_pass(tmp_path: Path) -> None:
    _gpkg(tmp_path / "unrelated.gpkg", "2d_code_misc")
    (tmp_path / "bc.csv").write_text(
        "Name,Source,Column 1,Column 2\n"
        "flow,not_loaded.csv,Time,Flow\n",
        encoding="utf-8",
    )
    (tmp_path / "model.tcf").write_text(
        "BC Database == bc.csv\n"
        "Read GIS BC == unrelated.gpkg >> all\n",
        encoding="utf-8",
    )
    report = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 DEV"])
    assert not report.passed
    # Parser rejection, a missing selected layer, or an unresolved attribute
    # source are all valid fail-closed outcomes. No unselected BC Source can
    # certify this malformed Read GIS BC selection.
    assert any(
        issue.run_index == 0 and issue.status != "present"
        for issue in report.issues
    ), report.issues


def test_context_expanded_inline_bc_constant_uses_cached_parser(tmp_path: Path) -> None:
    _bc_gpkg(tmp_path / "bc.gpkg", name="GT01")
    (tmp_path / "bc.csv").write_text(
        "Name,Source,Column 1,Column 2\n"
        "GT01,,,<<BCConstant>>\n",
        encoding="utf-8",
    )
    (tmp_path / "model.tcf").write_text(
        "Set Variable BCConstant == 2.75\n"
        "BC Database == bc.csv\n"
        "Read GIS BC == bc.gpkg >> 2d_bc_lines\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 Existing", "-s1 Proposed"])
    assert result.passed, result.issues
    assert result.validation.files_examined == 2
    assert result.validation.csv_headers_examined == 0
    assert all(not run.database_sources for run in result.dependencies.runs)


@pytest.mark.parametrize('as_generator', [False, True])
def test_inline_bc_constant_preserves_structured_flags(tmp_path: Path, as_generator: bool) -> None:
    _bc_gpkg(tmp_path / 'bc.gpkg', name='GT01')
    (tmp_path / 'bc.csv').write_text(
        'Name,Source,Column 1,Column 2\nGT01,,,<<BCConstant>>\n', encoding='utf-8',
    )
    top = tmp_path / 'model.tcf'
    top.write_text(
        'If Scenario == Existing State\n'
        'Set Variable BCConstant == 2.75\n'
        'Else\nSet Variable BCConstant == 3.5\nEnd If\n'
        'BC Database == bc.csv\nRead GIS BC == bc.gpkg >> 2d_bc_lines\n',
        encoding='utf-8',
    )
    flags = [{'s1': 'Existing State'}, '-s1 Proposed']
    result = validate_batch_inputs(top, (item for item in flags) if as_generator else flags)
    assert result.passed, result.issues
    assert len(result.dependencies.runs) == 2
    assert result.validation.csv_headers_examined == 0
    assert flags == [{'s1': 'Existing State'}, '-s1 Proposed']


@pytest.mark.parametrize(('case_policy', 'filename', 'requested'), [
    (1, 'bc.CSV', 'bc.csv'),
    (2, 'BC.csv', 'bc.csv'),
])
def test_inline_bc_constant_preserves_cached_filename_policy(
    tmp_path: Path, case_policy: int, filename: str, requested: str,
) -> None:
    from pytuflow import TCF

    _bc_gpkg(tmp_path / 'bc.gpkg', name='GT01')
    (tmp_path / filename).write_text('Name,Source,Column 1,Column 2\nGT01,,,2.75\n', encoding='utf-8')
    top = tmp_path / 'model.tcf'
    top.write_text(f'BC Database == {requested}\nRead GIS BC == bc.gpkg >> 2d_bc_lines\n', encoding='utf-8')
    result = validate_batch_inputs(TCF(top, case_sensitivity=case_policy), ['-s1 Existing'])
    assert result.passed, result.issues
    assert result.validation.csv_headers_examined == 0


def test_bc_group_name_uses_existing_database_group_semantics(tmp_path: Path) -> None:
    _bc_gpkg(tmp_path / "bc.gpkg", name="N1|Group")
    (tmp_path / "bc.csv").write_text(
        "Name,Source,Column 1,Column 2\n"
        "Group,group.ts1,Time,Stage\n",
        encoding="utf-8",
    )
    (tmp_path / "group.ts1").write_text(
        "TS1 group source supplied\n", encoding="utf-8"
    )
    (tmp_path / "model.tcf").write_text(
        "BC Database == bc.csv\n"
        "Read GIS BC == bc.gpkg >> 2d_bc_lines\n",
        encoding="utf-8",
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 Existing"])
    assert result.passed, result.issues
    assert result.validation.files_examined == 3
    assert any(
        f.kind == "file"
        and f.status == "present"
        and f.path is not None
        and f.path.name == "group.ts1"
        for f in result.validation.findings
    )


def _mif_with_link(path: Path, filename: str) -> None:
    """A valid MapInfo MIF/MID pair using the original PyTUFLOW GIS reader."""
    path.write_text(
        'Version 300\n'
        'Charset "WindowsLatin1"\n'
        'Delimiter ","\n'
        'CoordSys NonEarth Units "m"\n'
        'Columns 1\n'
        '  Source Char(254)\n'
        'Data\n'
        'Point 0 0\n',
        encoding="utf-8",
    )
    path.with_suffix(".mid").write_text(
        f'"{filename}"\n', encoding="utf-8"
    )


@pytest.mark.parametrize("channel", ["M", "QO"])
@pytest.mark.parametrize("geometry", ["mixed", "line", "point"])
def test_mif_network_geometry_does_not_hide_missing_matrix(
    tmp_path: Path, channel: str, geometry: str,
) -> None:
    path = tmp_path / "1d_nwk_test.mif"
    shapes = {
        "mixed": "Line 0 0 1 1\nPoint 2 2\n",
        "line": "Line 0 0 1 1\n",
        "point": "Point 2 2\n",
    }
    path.write_text(
        'Version 300\nCharset "WindowsLatin1"\nDelimiter ","\n'
        'CoordSys NonEarth Units "m"\nColumns 11\n'
        + ''.join(f'  F{i} Char(254)\n' for i in range(11))
        + 'Data\n' + shapes[geometry], encoding="utf-8",
    )
    matrix = "missing.csv" if channel == "M" else "control|missing.csv"
    row = ["id", channel, "", "", "", "", "", "", "", "", matrix]
    path.with_suffix(".mid").write_text(
        (','.join(f'"{value}"' for value in row) + '\n')
        * (2 if geometry == "mixed" else 1), encoding="utf-8",
    )
    (tmp_path / "model.tcf").write_text(
        "Read GIS Network == 1d_nwk_test.mif\n", encoding="utf-8"
    )
    result = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    if geometry == "mixed":
        assert not result.passed
        assert any(
            item.status == "unresolved" and item.kind == "attribute"
            and "Mixed network geometry" in item.detail
            for item in result.issues
        ), result.issues
    elif geometry == "line":
        assert not result.passed
        assert any(
            item.status == "missing" and item.path == tmp_path / "missing.csv"
            for item in result.issues
        ), result.issues
    else:
        assert result.passed, result.issues


def test_existing_mif_mid_reader_discovers_linked_1d_file(tmp_path: Path) -> None:
    mif = tmp_path / "1d_xs_section.mif"
    _mif_with_link(mif, "section.csv")
    (tmp_path / "section.csv").write_text(
        "x,z\n0,1\n", encoding="utf-8"
    )
    (tmp_path / "model.tcf").write_text(
        "Read GIS Code == 1d_xs_section.mif\n",
        encoding="utf-8",
    )
    ok = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert ok.passed, ok.issues
    assert ok.gis_sources_added == 1
    assert any(
        finding.path and finding.path.name == "section.csv"
        and finding.status == "present"
        for finding in ok.validation.findings
    )
    (tmp_path / "section.csv").unlink()
    missing = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert not missing.passed
    assert any(
        item.path and item.path.name == "section.csv"
        and item.status == "missing"
        for item in missing.issues
    )


def test_shapefile_companions_use_matching_extension_case_not_fuzzy_search(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pytuflow import validation_gis

    primary = tmp_path / "1d_xs_case.SHP"
    header = bytearray(100)
    header[32:36] = (1).to_bytes(4, "little")
    primary.write_bytes(header)
    primary.with_suffix(".DBF").write_bytes(b"test")
    primary.with_suffix(".SHX").write_bytes(b"test")

    class FakeDBF:
        field_names = ("Source",)

        def __init__(self, filename: str, **kwargs: object) -> None:
            assert Path(filename).name == "1d_xs_case.DBF"

        def __iter__(self):
            yield OrderedDict((("Source", "linked.csv"),))

    monkeypatch.setattr(validation_gis, "DBF", FakeDBF)
    sources, identifiers, names = validation_gis._scan_shapefile(primary)
    assert not identifiers and not names
    assert tuple(x.name for x in sources) == ("linked.csv",)

    if os.name != "nt":
        primary.with_suffix(".SHX").rename(primary.with_suffix(".shx"))
        with pytest.raises(ValueError, match="matching DBF and SHX"):
            validation_gis._scan_shapefile(primary)



def test_ordinary_read_gis_code_checks_shapefile_companions(tmp_path: Path) -> None:
    """Shapefile physical checks cannot depend on 1D attribute inspection."""
    primary = tmp_path / "2d_code_area.shp"
    primary.write_bytes(b"shapefile fixture")
    (tmp_path / "model.tcf").write_text(
        "Read GIS Code == 2d_code_area.shp\n", encoding="utf-8"
    )
    incomplete = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert not incomplete.passed
    assert any(
        item.status == "missing" and "2d_code_area.dbf" in item.detail
        for item in incomplete.issues
    ), incomplete.issues

    primary.with_suffix(".dbf").write_bytes(b"dbf fixture")
    missing_shx = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert not missing_shx.passed
    assert any(
        item.status == "missing" and "2d_code_area.shx" in item.detail
        for item in missing_shx.issues
    ), missing_shx.issues

    primary.with_suffix(".shx").write_bytes(b"shx fixture")
    complete = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert complete.passed, complete.issues
    assert complete.gis_files_scanned == 0



def test_read_mi_code_requires_mid_even_without_linked_attribute_sources(
    tmp_path: Path,
) -> None:
    """A non-1D MapInfo GIS layer must never pass with an absent .mid."""
    mif = tmp_path / "2d_code_area.mif"
    _mif_with_link(mif, "ignored_code_value")
    (tmp_path / "model.tcf").write_text(
        "Read MI Code == 2d_code_area.mif\n", encoding="utf-8"
    )

    mif.with_suffix(".mid").unlink()
    missing = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert not missing.passed
    assert any(
        finding.kind == "file"
        and finding.status == "missing"
        and "MID" in finding.detail
        for finding in missing.issues
    ), missing.issues
    assert missing.gis_files_scanned == 0

    mif.with_suffix(".mid").write_text(
        '"ignored_code_value"\n', encoding="utf-8"
    )
    complete = validate_batch_inputs(tmp_path / "model.tcf", ["-s1 EXG"])
    assert complete.passed, complete.issues
    assert complete.gis_files_scanned == 0
