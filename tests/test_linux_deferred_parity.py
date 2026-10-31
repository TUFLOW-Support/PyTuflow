"""Native Linux path alias regressions for deferred TUFLOW input discovery."""

from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

from pytuflow import TCF
from pytuflow._tmf import TuflowPath
from pytuflow._tmf.parsers.command import Command
from pytuflow._tmf.settings import TCFConfig

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux filesystem semantics")


def test_exact_filename_preferred_with_case_only_siblings(tmp_path: Path) -> None:
    """A valid exact spelling must not raise an ambiguous-case error."""
    upper = tmp_path / "Materials.csv"
    lower = tmp_path / "materials.csv"
    upper.write_text("1,0.03\n", encoding="utf-8")
    lower.write_text("2,0.04\n", encoding="utf-8")

    assert TuflowPath.init_case_insensitive_path("Materials.csv", tmp_path).dbpath == Path("Materials.csv")
    assert TuflowPath.init_case_insensitive_path("materials.csv", tmp_path).dbpath == Path("materials.csv")


def test_nonexact_ambiguous_filename_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "Materials.csv").touch()
    (tmp_path / "materials.csv").touch()

    with pytest.raises(RuntimeError, match="Ambiguous case-insensitive match"):
        TuflowPath.init_case_insensitive_path("MATERIALS.csv", tmp_path)


def test_unique_nonexact_filename_preserves_found_spelling(tmp_path: Path) -> None:
    actual = tmp_path / "Materials.csv"
    actual.touch()
    assert TuflowPath.init_case_insensitive_path("materials.csv", tmp_path).dbpath == Path("Materials.csv")


def test_symlink_alias_keeps_original_spelling(tmp_path: Path) -> None:
    target = tmp_path / "Materials.csv"
    target.touch()
    alias = tmp_path / "linked.csv"
    try:
        alias.symlink_to(target)
    except OSError:
        pytest.skip("No symlink support")
    assert TuflowPath.init_case_insensitive_path("linked.csv", tmp_path).dbpath == Path("linked.csv")


def test_deferred_and_eager_nested_reference_agree(tmp_path: Path) -> None:
    """No control-file rescan may substitute an unrelated case-only sibling."""
    selected = tmp_path / "Geometry.TGC"
    selected.write_text("Read GIS Code == gis/selected.shp\n", encoding="utf-8")
    other = tmp_path / "geometry.tgc"
    other.write_text("Read GIS Code == gis/other.shp\n", encoding="utf-8")
    tcf = tmp_path / "model.tcf"
    tcf.write_text("Geometry Control File == Geometry.TGC\n", encoding="utf-8")

    model = TCF(tcf)
    inventories: list[set[str]] = []
    for mode in ("eager", "deferred"):
        run = model.context(file_resolution=mode)
        inventories.append(
            {
                reference.path_pattern.name
                for item in run.find_input(recursive=True)
                for reference in item.file_references
            }
        )
    assert inventories[0] == inventories[1]
    assert "selected.shp" in inventories[1]
    assert "other.shp" not in inventories[1]


def test_gpkg_case_only_siblings_select_exact_database_and_layer(tmp_path: Path) -> None:
    """A layer check must not silently read an unrelated differently cased GPKG."""
    for filename, layer in (
        ("Boundary.gpkg", "2d_bc_upper"),
        ("boundary.gpkg", "2d_bc_lower"),
    ):
        with closing(sqlite3.connect(tmp_path / filename)) as connection:
            connection.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
            connection.execute("INSERT INTO gpkg_contents VALUES (?)", (layer,))
            connection.commit()

    for filename, layer, wrong_layer in (
        ("Boundary.gpkg", "2d_bc_upper", "2d_bc_lower"),
        ("boundary.gpkg", "2d_bc_lower", "2d_bc_upper"),
    ):
        chosen = TuflowPath.init_case_insensitive_path(filename, tmp_path)
        assert chosen.dbpath == Path(filename)
        full_path = tmp_path / chosen.dbpath
        assert TuflowPath(f"{full_path} >> {layer}").exists()
        assert not TuflowPath(f"{full_path} >> {wrong_layer}").exists()


@pytest.mark.parametrize(
    ("case_sensitivity", "requested", "expected_file"),
    [
        (0, "materials.csv", "materials.csv"),
        (1, "materials.csv", "materials.csv"),
        (2, "materials.csv", "Materials.csv"),
        (0, "Materials.CSV", "Materials.CSV"),
        (1, "Materials.CSV", "Materials.csv"),
        (2, "MATERIALS.CSV", "Materials.csv"),
    ],
)
def test_linux_literal_case_modes(case_sensitivity: int, requested: str, expected_file: str, tmp_path: Path) -> None:
    """Default -cs0 must retain incorrect filenames; -cs1/-cs2 match TUFLOW."""
    (tmp_path / "Materials.csv").write_text("Material, Manning\n1,0.04\n", encoding="utf-8")
    selected = TuflowPath.init_case_policy_path(requested, tmp_path, case_sensitivity)
    assert selected.dbpath == Path(expected_file)
    assert (tmp_path / selected.dbpath).is_file() == (expected_file == "Materials.csv")


def test_linux_strict_default_and_database_input_status(tmp_path: Path) -> None:
    """PyTUFLOW eager and explicit deferred materialisation must flag bad casing."""
    actual = tmp_path / "Materials.csv"
    actual.write_text("Material, Manning\n1,0.04\n", encoding="utf-8")
    tcf = tmp_path / "case_policy.tcf"
    tcf.write_text("Read Materials File == Materials.csv\n", encoding="utf-8")

    assert TCFConfig().case_sensitivity == 0
    assert TCF(tcf).config.case_sensitivity == 0

    tcf.write_text("Read Materials File == materials.csv\n", encoding="utf-8")
    strict = TCF(tcf)
    assert strict.config.case_sensitivity == 0
    strict_input = strict.find_input(lhs="Read Materials File")[0]
    assert strict_input.has_missing_files
    strict_deferred = strict.context(file_resolution="deferred").find_input(lhs="Read Materials File")[0]
    assert strict_deferred.file_references[0].path_pattern.name == "materials.csv"

    tolerant = TCF(tcf, case_sensitivity=2)
    tolerant_input = tolerant.find_input(lhs="Read Materials File")[0]
    assert not tolerant_input.has_missing_files
    assert tolerant_input.files[0].name == "Materials.csv"


@pytest.mark.parametrize(
    ("level", "expected"),
    [(0, "Materials.CSV"), (1, "Materials.csv"), (2, "Materials.csv")],
)
def test_linux_extension_only_policy(level: int, expected: str, tmp_path: Path) -> None:
    (tmp_path / "Materials.csv").touch()
    selected = TuflowPath.init_case_policy_path("Materials.CSV", tmp_path, level)
    assert selected.dbpath.name == expected


def test_linux_directories_remain_case_sensitive_under_cs2(tmp_path: Path) -> None:
    (tmp_path / "Model").mkdir()
    (tmp_path / "Model" / "Materials.csv").touch()
    actual = TuflowPath.init_case_policy_path("model/materials.csv", tmp_path, 2)
    assert actual.dbpath == Path("model/materials.csv")
    assert not (tmp_path / actual.dbpath).exists()
    correct_directory = TuflowPath.init_case_policy_path("Model/materials.csv", tmp_path, 2)
    assert correct_directory.dbpath == Path("Model/Materials.csv")


def test_linux_case_policy_with_distinct_filename_siblings(tmp_path: Path) -> None:
    (tmp_path / "Materials.csv").touch()
    (tmp_path / "materials.csv").touch()
    assert TuflowPath.init_case_policy_path("materials.csv", tmp_path, 2).dbpath == Path("materials.csv")
    with pytest.raises(ValueError, match="Ambiguous"):
        TuflowPath.init_case_policy_path("MATERIALS.csv", tmp_path, 2)


@pytest.mark.parametrize("case_sensitivity", [-1, 3, True, "2", None])
def test_invalid_tuflow_case_sensitivity_rejected(case_sensitivity: object) -> None:
    with pytest.raises(ValueError, match="case_sensitivity"):
        TCFConfig(case_sensitivity=case_sensitivity)


def test_linux_wildcard_filename_mode_not_directory_mode(tmp_path: Path) -> None:
    (tmp_path / "Model").mkdir()
    source = tmp_path / "Model" / "Grid_01.TIF"
    source.touch()
    assert list(TuflowPath(tmp_path / "Model").glob("grid_*.tif", case_sensitivity=0)) == []
    assert list(TuflowPath(tmp_path / "Model").glob("grid_*.tif", case_sensitivity=1)) == []
    assert list(TuflowPath(tmp_path / "Model").glob("grid_*.tif", case_sensitivity=2)) == [source]
    assert list(TuflowPath(tmp_path).glob("model/grid_*.tif", case_sensitivity=2)) == []


def test_tcf_case_level_argument_validation(tmp_path: Path) -> None:
    tcf = tmp_path / "model.tcf"
    tcf.write_text("! Empty model\n", encoding="utf-8")
    for level in (0, 1, 2):
        assert TCF(tcf, case_sensitivity=level).config.case_sensitivity == level
    with pytest.raises(ValueError, match="case_sensitivity"):
        TCF(tcf, case_sensitivity=3)
    with pytest.raises(ValueError, match="not both"):
        TCF(tcf, config=TCFConfig(tcf=tcf), case_sensitivity=2)


def test_linux_default_rejects_wrong_case_nested_control_file(tmp_path: Path) -> None:
    nested = tmp_path / "Geometry.TGC"
    nested.write_text("Read GRID Zpts == grid.tif\n", encoding="utf-8")
    tcf = tmp_path / "main.tcf"
    tcf.write_text("Geometry Control File == geometry.tgc\n", encoding="utf-8")
    strict = TCF(tcf)
    refs = {
        ref.path_pattern.name
        for item in strict.context(file_resolution="deferred").find_input()
        for ref in item.file_references
    }
    assert "geometry.tgc" in refs
    assert "grid.tif" not in refs  # Wrong-cased nested control file was not loaded.

    permissive = TCF(tcf, case_sensitivity=2)
    corrected = {
        ref.path_pattern.name
        for item in permissive.context(file_resolution="deferred").find_input()
        for ref in item.file_references
    }
    assert "grid.tif" in corrected  # Explicit -cs2 resolves filename spelling.


def test_linux_literal_case_collision_is_not_silently_accepted(tmp_path: Path) -> None:
    (tmp_path / "Material.csv").touch()
    (tmp_path / "material.csv").touch()
    # Exact reference is unique despite a case-only sibling.
    exact = list(TuflowPath(tmp_path).glob("Material.csv", case_sensitivity=2))
    assert exact == [tmp_path / "Material.csv"]
    # An ambiguous non-exact spelling is not accepted by a broad casefold scan.
    with pytest.raises(ValueError, match="Ambiguous"):
        list(TuflowPath(tmp_path).glob("MATERIAL.csv", case_sensitivity=2))


def test_linux_directory_wildcard_stays_strict_with_leaf_case_modes(tmp_path: Path) -> None:
    for dirname in ("Area_A", "area_B"):
        (tmp_path / dirname).mkdir()
        (tmp_path / dirname / "Grid_01.TIF").touch()
    root = TuflowPath(tmp_path)
    upper = tmp_path / "Area_A" / "Grid_01.TIF"
    assert list(root.glob("Area_*/grid_*.tif", case_sensitivity=0)) == []
    assert list(root.glob("Area_*/grid_*.tif", case_sensitivity=1)) == []
    assert list(root.glob("Area_*/Grid_*.tif", case_sensitivity=1)) == [upper]
    assert list(root.glob("Area_*/grid_*.tif", case_sensitivity=2)) == [upper]


def test_linux_primary_tcf_filename_honours_case_policy(tmp_path: Path) -> None:
    source = tmp_path / "Main.tcf"
    source.write_text("! example\n", encoding="utf-8")
    assert not TCF(tmp_path / "main.TCF").loaded
    assert not TCF(tmp_path / "main.TCF", case_sensitivity=1).loaded
    assert TCF(tmp_path / "Main.TCF", case_sensitivity=1).loaded
    assert TCF(tmp_path / "main.TCF", case_sensitivity=2).loaded


def test_linux_primary_tcf_directory_stays_strict(tmp_path: Path) -> None:
    folder = tmp_path / "Models"
    folder.mkdir()
    (folder / "Main.tcf").write_text("! example\n", encoding="utf-8")
    assert not TCF(tmp_path / "models" / "Main.tcf", case_sensitivity=2).loaded
    assert TCF(folder / "main.TCF", case_sensitivity=2).loaded


def test_linux_folder_command_is_not_case_relaxed_at_cs2(tmp_path: Path) -> None:
    """Output Folder is a directory value, not a filename to normalise."""
    (tmp_path / "Outputs").mkdir()
    config = TCFConfig(control_file=tmp_path / "model.tcf", init_from_tcf=False, case_sensitivity=2)
    command = Command("Output Folder == outputs", config)
    assert Path(command.value_expanded_path).name == "outputs"


@pytest.mark.parametrize(
    ("level", "include_name", "event_name", "expected"),
    [
        (0, "extra.trd", "events.tef", False),
        (1, "Extra.trd", "Events.tef", True),
        (1, "extra.trd", "events.tef", False),
        (2, "extra.trd", "events.tef", True),
    ],
)
def test_preliminary_scans_match_nested_files_under_case_policy(
    tmp_path: Path, level: int, include_name: str, event_name: str, expected: bool,
) -> None:
    """Variables, settings and event definitions must agree with file loading."""
    (tmp_path / "Extra.TRD").write_text(
        "Set Variable FROM_INCLUDE == included\n"
        "GIS Format == SHP\n",
        encoding="utf-8",
    )
    (tmp_path / "Events.TEF").write_text(
        "Define Event == CASE_EVENT\n"
        "BC Event Source == _event_ | case.csv\n"
        "End Define\n",
        encoding="utf-8",
    )
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        f"Read File == {include_name}\n"
        f"Event File == {event_name}\n",
        encoding="utf-8",
    )
    config = TCFConfig(tcf=tcf, case_sensitivity=level)
    assert ("FROM_INCLUDE" in config.variables) is expected
    assert ("CASE_EVENT" in config.event_db) is expected
    # Format directives inside includes must be discovered by the third pass.
    from pytuflow._tmf.gis import GisFormat
    assert (config.gis_format == GisFormat.SHP) is expected


def test_preliminary_nested_include_uses_containing_directory(tmp_path: Path) -> None:
    """A second-level include is located relative to the containing TRD."""
    folder = tmp_path / "sub"
    folder.mkdir()
    (folder / "Extra.TRD").write_text(
        "Read File == nested.trd\n",
        encoding="utf-8",
    )
    (folder / "Nested.TRD").write_text(
        "Set Variable NESTED == yes\n", encoding="utf-8",
    )
    tcf = tmp_path / "main.tcf"
    tcf.write_text("Read File == sub/extra.trd\n", encoding="utf-8")
    assert "NESTED" in TCFConfig(tcf=tcf, case_sensitivity=2).variables
    assert "NESTED" not in TCFConfig(tcf=tcf, case_sensitivity=0).variables


@pytest.mark.parametrize(
    ("level", "database_value", "resolved"),
    [
        (0, "data.gpkg", False),
        (1, "Data.GPKG", True),
        (1, "data.gpkg", False),
        (2, "data.gpkg", True),
    ],
)
def test_spatial_database_stores_physical_filename(
    tmp_path: Path, level: int, database_value: str, resolved: bool,
) -> None:
    """Layer-only commands use the actual case-matched GPKG, not the raw alias."""
    actual = tmp_path / "Data.gpkg"
    actual.touch()
    config = TCFConfig(control_file=tmp_path / "model.tcf",
                       init_from_tcf=False, case_sensitivity=level)
    config.set_spatial_database(database_value)
    assert (config.spatial_database == actual) is resolved
    from pytuflow._tmf.parsers.command import Command
    cmd = Command("Read GIS Code == code", config)
    db = TuflowPath(cmd.value_expanded_path).dbpath
    assert (db == actual) is resolved


def test_spatial_database_case_policy_rejects_wrong_directory(tmp_path: Path) -> None:
    """Explicit -cs2 must not repair directory components."""
    (tmp_path / "Data").mkdir()
    actual = tmp_path / "Data" / "Source.gpkg"
    actual.touch()
    cfg = TCFConfig(control_file=tmp_path / "model.tcf",
                    init_from_tcf=False, case_sensitivity=2)
    cfg.set_spatial_database("data/source.gpkg")
    assert cfg.spatial_database == tmp_path / "data/source.gpkg"
    assert not cfg.spatial_database.exists()


@pytest.mark.parametrize(
    ("case_sensitivity", "requested", "expected"),
    [
        (0, "geom_A.tgc", "upper"),
        (0, "geom_a.tgc", "lower"),
        (1, "geom_A.TGC", "upper"),
        (2, "geom_A.tgc", "upper"),
        (2, "geom_a.tgc", "lower"),
    ],
)
def test_cached_include_case_policy_and_exact_precedence(
    tmp_path: Path, case_sensitivity: int, requested: str, expected: str
) -> None:
    """Choose the appropriate preloaded include without a filesystem scan."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from pytuflow._tmf.inp.cf import select_deferred_children

    children = {"upper": object(), "lower": object()}
    loaded = (tmp_path / "geom_A.tgc", tmp_path / "geom_a.tgc")
    build = SimpleNamespace(
        lhs="Geometry Control File",
        config=SimpleNamespace(case_sensitivity=case_sensitivity),
        cf=tuple(children.values()),
        _cf_loaded_paths=list(loaded),
    )
    ref = SimpleNamespace(path_pattern=tmp_path / requested,
                          unresolved_variables=())
    with patch.object(Path, "stat", side_effect=AssertionError("stat")):
        selected = select_deferred_children(build, (ref,))
    assert selected == (children[expected],)


def test_cached_include_nonexact_collision_fails_closed(tmp_path: Path) -> None:
    """Case-insensitive names must fail when neither literal is exact."""
    from types import SimpleNamespace
    from unittest.mock import patch

    from pytuflow._tmf.abc.run_state import ResolveError
    from pytuflow._tmf.inp.cf import select_deferred_children

    build = SimpleNamespace(
        lhs="Geometry Control File",
        config=SimpleNamespace(case_sensitivity=2),
        cf=(object(), object()),
        _cf_loaded_paths=[tmp_path / "geom_A.tgc", tmp_path / "geom_a.tgc"],
    )
    ref = SimpleNamespace(path_pattern=tmp_path / "geom_A.TGC",
                          unresolved_variables=())
    with patch.object(Path, "stat", side_effect=AssertionError("stat")):
        with pytest.raises(ResolveError, match="Ambiguous cached child"):
            select_deferred_children(build, (ref,))


def test_cached_include_parent_directory_case_is_strict(tmp_path: Path) -> None:
    """-cs2 relaxes filenames, never the directory containing an include."""
    from types import SimpleNamespace

    from pytuflow._tmf.abc.run_state import ResolveError
    from pytuflow._tmf.inp.cf import select_deferred_children

    expected = object()
    wrong = object()
    build = SimpleNamespace(
        lhs="Geometry Control File",
        config=SimpleNamespace(case_sensitivity=2),
        cf=(expected, wrong),
        _cf_loaded_paths=[
            tmp_path / "Area" / "geom_A.tgc",
            tmp_path / "area" / "geom_B.tgc",
        ],
    )
    ref = SimpleNamespace(path_pattern=tmp_path / "Area" / "geom_a.tgc",
                          unresolved_variables=())
    assert select_deferred_children(build, (ref,)) == (expected,)
    bad = SimpleNamespace(path_pattern=tmp_path / "AREA" / "geom_A.tgc",
                          unresolved_variables=())
    with pytest.raises(ResolveError, match="No cached nested control file"):
        select_deferred_children(build, (bad,))


@pytest.mark.parametrize("scenario,expected", [("A", "upper.shp"), ("a", "lower.shp")])
def test_deferred_case_only_sibling_includes_match_eager(
    tmp_path: Path, scenario: str, expected: str
) -> None:
    """Scenario-specific cached includes preserve eager selection on Linux."""
    for name, layer in (("geom_A.tgc", "upper.shp"),
                        ("geom_a.tgc", "lower.shp")):
        (tmp_path / name).write_text(
            f"Read GIS Code == gis/{layer}\n", encoding="utf-8"
        )
    tcf = tmp_path / "model.tcf"
    tcf.write_text("Geometry Control File == geom_<<~s1~>>.tgc\n", encoding="utf-8")
    model = TCF(tcf)
    build = model.find_input(lhs="Geometry Control File")[0]
    assert {Path(child).name for child in build._cf_loaded_paths} == {
        "geom_A.tgc", "geom_a.tgc",
    }
    eager = model.context(f"-s1 {scenario}")
    deferred = model.context(f"-s1 {scenario}", file_resolution="deferred")
    def inventory(run):
        return {reference.path_pattern.name
                for item in run.find_input(recursive=True)
                for reference in item.file_references}
    assert expected in inventory(eager) == inventory(deferred)
    result = model.collect_file_dependencies([f"-s1 {scenario}"])
    assert result.passed, [run.error for run in result.runs]
    assert expected in {ref.path_pattern.name for ref
                        in result.runs[0].file_references}


def test_cached_child_suffix_never_selects_different_scenario_ancestor(
    tmp_path: Path,
) -> None:
    """A matching immediate parent and basename cannot bypass other parents."""
    from types import SimpleNamespace

    from pytuflow._tmf.abc.run_state import ResolveError
    from pytuflow._tmf.inp.cf import select_deferred_children

    build = SimpleNamespace(
        lhs="Geometry Control File",
        config=SimpleNamespace(case_sensitivity=2),
        cf=(object(),),
        _cf_loaded_paths=[tmp_path / "Area" / "shared" / "geom.tgc"],
    )
    missing = SimpleNamespace(
        path_pattern=tmp_path / "area" / "shared" / "geom.tgc",
        unresolved_variables=(),
    )
    with pytest.raises(ResolveError, match="No cached nested control file"):
        select_deferred_children(build, (missing,))


def test_cs1_cached_include_wildcard_can_span_extension(tmp_path: Path) -> None:
    child = tmp_path / 'geom_A.tgc'
    child.write_text('Read GIS Code == gis/code.shp\n', encoding='utf-8')
    top = tmp_path / 'model.tcf'
    top.write_text('Geometry Control File == geom_*\n', encoding='utf-8')
    model = TCF(top, case_sensitivity=1)
    assert model.find_input(lhs='Geometry Control File')[0].cf
    result = model.collect_file_dependencies(['-s1 A'])
    assert result.passed, [run.error for run in result.runs]
    assert 'code.shp' in {ref.path_pattern.name for ref in result.runs[0].file_references}
