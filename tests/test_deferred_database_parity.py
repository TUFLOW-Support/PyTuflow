"""Regression tests for deferred database roles and secondary file sources."""
import ntpath
import os
import posixpath
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from pytuflow import TCF
from pytuflow._tmf.deferred_database import (
    DeferredDatabaseResolutionError,
    _cached_database_path_key,
    database_source_references,
)
from pytuflow._tmf.file_reference import make_file_reference
from pytuflow._tmf.parsers.command import Command
from pytuflow._tmf.settings import TCFConfig
from pytuflow._tmf.tfpathlib import TuflowPath


@pytest.mark.parametrize("mode", ["eager", "deferred"])
def test_shared_database_sources_preserve_nested_ad_ownership_without_io(tmp_path, mode):
    """AD ownership and global-relative paths are identical in both APIs."""
    for directory in ("controls", "global", "tables"):
        (tmp_path / directory).mkdir()
    tcf = tmp_path / "model.tcf"
    tcf.write_text("AD Control File == controls/model.adcf\n", encoding="utf-8")
    owner = tmp_path / "controls" / "model.adcf"
    owner.write_text(
        "AD Global Database == ../global/constituents.csv\n"
        "AD BC Database == ../tables/boundaries.csv\n",
        encoding="utf-8",
    )
    (tmp_path / "global" / "constituents.csv").write_text(
        "Name,Initial Condition,Minimum Dispersion\nTracer,initial.shp,0\n",
        encoding="utf-8",
    )
    (tmp_path / "tables" / "boundaries.csv").write_text(
        "Name,Source,Column 1,Column 2\n"
        "West__Tracer,concentration.csv,time,west\n"
        "East__Tracer,concentration.csv,time,east\n",
        encoding="utf-8",
    )
    (tmp_path / "global" / "concentration.csv").write_text("time,west,east\n0,1,2\n", encoding="utf-8")
    (tmp_path / "global" / "initial.shp").touch()
    run = TCF(tcf).context(file_resolution=mode)
    with (
        patch.object(Path, "open", side_effect=AssertionError("file opened")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
        patch("sqlite3.connect", side_effect=AssertionError("SQLite")),
    ):
        sources = run.database_sources()
        if mode == "deferred":
            assert run.deferred_database_sources() == sources
    assert {(s.database_kind, s.entry_name) for s in sources} == {
        ("ad_bc", "West__Tracer"), ("ad_bc", "East__Tracer"), ("ad_global", "Tracer"),
    }
    # Physical comparison follows the relative ../ components in nested owners.
    assert all(s.owner_control_file.resolve() == owner.resolve() for s in sources)
    assert {s.path_pattern.resolve() for s in sources if s.database_kind == "ad_bc"} == {
        (tmp_path / "global" / "concentration.csv").resolve(),
    }
    assert {s.owning_command.casefold() for s in sources} == {"ad bc database", "ad global database"}


@pytest.mark.parametrize("mode", ["eager", "deferred"])
@pytest.mark.parametrize("role", ["BC Database", "AD BC Database"])
def test_shared_database_sources_exclude_inactive_scenario_inputs(tmp_path, mode, role):
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "AD Global Database == global.csv\n"
        f"If Scenario == A\n{role} == first.csv\n"
        f"Else\n{role} == second.csv\nEnd If\n",
        encoding="utf-8",
    )
    _bc_csv(tmp_path / "first.csv", "first_source.csv")
    _bc_csv(tmp_path / "second.csv", "second_source.csv")
    (tmp_path / "global.csv").write_text(
        "Name,Initial Condition,Minimum Dispersion\nTracer,0,0\n", encoding="utf-8",
    )
    model = TCF(tcf)
    assert [s.path_pattern.name for s in model.context('-s1 A', file_resolution=mode).database_sources()] == [
        "first_source.csv",
    ]
    assert [s.path_pattern.name for s in model.context('-s1 B', file_resolution=mode).database_sources()] == [
        "second_source.csv",
    ]


def _cfg(tmp_path: Path) -> TCFConfig:
    return TCFConfig(
        control_file=tmp_path / "model.tcf",
        init_from_tcf=False,
        file_resolution="deferred",
    )


@pytest.mark.parametrize('mode', ['eager', 'deferred', 'batch'])
def test_single_context_selects_one_of_multiple_preloaded_database_files(tmp_path, mode):
    """One declaration can preload scenario candidates; do not combine their rows."""
    tcf = tmp_path / 'model.tcf'
    tcf.write_text('BC Database == bc_<<~s1~>>.csv\n', encoding='utf-8')
    _bc_csv(tmp_path / 'bc_A.csv', 'a_source.csv')
    _bc_csv(tmp_path / 'bc_B.csv', 'b_source.csv')
    model = TCF(tcf)
    assert len(model.find_input(lhs='BC Database')[0].cf) == 2
    for scenario in ('A', 'B'):
        if mode == 'eager':
            context = model.context(f'-s1 {scenario}', file_resolution=mode)
        with (
            patch.object(Path, 'open', side_effect=AssertionError('file opened')),
            patch.object(Path, 'stat', side_effect=AssertionError('stat')),
            patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')),
            patch('sqlite3.connect', side_effect=AssertionError('SQLite')),
        ):
            if mode == 'batch':
                result = model.collect_file_dependencies((f'-s1 {scenario}',))
                assert result.passed, [run.error for run in result.runs]
                sources = result.runs[0].database_sources
            else:
                if mode == 'deferred':
                    context = model.context(f'-s1 {scenario}', file_resolution=mode)
                sources = context.database_sources()
        assert [source.path_pattern.name for source in sources] == [f'{scenario.lower()}_source.csv']


def test_cached_database_path_key_uses_platform_case_rules(tmp_path):
    path = tmp_path / "bc_A.csv"
    assert _cached_database_path_key(path) == os.path.normcase(
        os.path.normpath(str(path))
    )
    # The two relevant platform policies differ intentionally. The loaded
    # cache must never apply an unconditional casefold on POSIX.
    assert posixpath.normcase("bc_A.csv") != posixpath.normcase("bc_a.csv")
    assert ntpath.normcase("bc_A.csv") == ntpath.normcase("bc_a.csv")


@pytest.mark.parametrize(
    ("chosen_name", "expected_source"),
    [("bc_A.csv", "upper_source.csv"), ("bc_a.csv", "lower_source.csv")],
)
def test_cached_database_selector_preserves_posix_case_distinctions_without_io(
    tmp_path, chosen_name, expected_source,
):
    """Simulate POSIX matching even on Windows-only CI runners.

    Both already-loaded objects are distinct: a casefold match would select
    both and fail closed, rather than returning the explicitly chosen one.
    """
    paths = (tmp_path / "bc_A.csv", tmp_path / "bc_a.csv")
    build_input = SimpleNamespace(
        _database_loaded_paths=paths,
        cf=tuple(
            SimpleNamespace(
                fpath=path,
                loaded=True,
                df=pd.DataFrame(
                    {"Source": [source]},
                    index=["Boundary"],
                ),
            )
            for path, source in zip(
                paths, ("upper_source.csv", "lower_source.csv"), strict=True,
            )
        ),
    )
    context = SimpleNamespace(
        translate=lambda value: value,
        is_resolved=lambda value: True,
    )
    with (
        patch(
            "pytuflow._tmf.deferred_database._cached_database_path_key",
            side_effect=lambda path: posixpath.normcase(
                posixpath.normpath(str(path))
            ),
        ),
        patch.object(Path, "open", side_effect=AssertionError("file opened")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
    ):
        result = database_source_references(
            build_input, context, "bc", _cfg(tmp_path),
            primary_path=tmp_path / chosen_name,
        )
    assert len(result) == 1
    assert result[0].path_pattern.name == expected_source


def _bc_csv(path: Path, source: str) -> None:
    path.write_text(
        "Name,Source,Column 1,Column 2,Add Col 1,Mult Col 2,Add Col 2,Column 3,Column 4\n"
        + "FC01," + source + ",time,flow,,,,,\n",
        encoding="utf-8",
    )


@pytest.mark.parametrize('mode', ['eager', 'deferred', 'batch'])
def test_missing_context_database_does_not_reuse_another_cached_candidate(tmp_path, mode):
    tcf = tmp_path / 'model.tcf'
    tcf.write_text('BC Database == bc_<<~s1~>>.csv\n', encoding='utf-8')
    _bc_csv(tmp_path / 'bc_A.csv', 'a_source.csv')
    model = TCF(tcf)
    if mode == 'eager':
        context = model.context('-s1 MISSING', file_resolution=mode)
    with (
        patch.object(Path, 'open', side_effect=AssertionError('file opened')),
        patch.object(Path, 'stat', side_effect=AssertionError('stat')),
        patch.object(TuflowPath, 'glob', side_effect=AssertionError('glob')),
        patch('sqlite3.connect', side_effect=AssertionError('SQLite')),
    ):
        if mode == 'batch':
            result = model.collect_file_dependencies(('-s1 MISSING',))
            assert not result.passed
            assert 'found 0' in result.runs[0].error
        else:
            if mode == 'deferred':
                context = model.context('-s1 MISSING', file_resolution=mode)
            with pytest.raises(DeferredDatabaseResolutionError, match='found 0'):
                context.database_sources()


def test_hydraulic_and_ad_bc_databases_are_independent(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "BC Database == hydraulic.csv\n"
        "AD BC Database == ad_sources.csv\n",
        encoding="utf-8",
    )
    _bc_csv(tmp_path / "hydraulic.csv", "hydro.csv")
    _bc_csv(tmp_path / "ad_sources.csv", "ad.csv")
    (tmp_path / "ad_global.csv").write_text(
        "Name,Initial Condition,Minimum Dispersion\nTracer,0,0\n",
        encoding="utf-8",
    )
    tcf.write_text(
        tcf.read_text(encoding="utf-8") + "AD Global Database == ad_global.csv\n",
        encoding="utf-8",
    )

    model = TCF(tcf)
    eager = model.context()
    assert eager.bc_dbase().fpath == tmp_path / "hydraulic.csv"
    assert eager.ad_bc_dbase().fpath == tmp_path / "ad_sources.csv"

    with (
        patch.object(Path, "open", side_effect=AssertionError("file opened")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
        patch("sqlite3.connect", side_effect=AssertionError("SQLite")),
    ):
        run = model.context(file_resolution="deferred")
        result = run.deferred_database_sources()

    assert {(x.database_kind, x.database_path.name, x.path_pattern.name)
            for x in result} == {
        ("bc", "hydraulic.csv", "hydro.csv"),
        ("ad_bc", "ad_sources.csv", "ad.csv"),
    }
    assert {x.owning_command.casefold() for x in result} == {
        "bc database", "ad bc database",
    }
    assert all(x.owner_control_file == tcf for x in result)


def test_multiple_hydraulic_databases_fail_closed(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "BC Database == first.csv\nBC Database == second.csv\n",
        encoding="utf-8",
    )
    _bc_csv(tmp_path / "first.csv", "first.dat")
    _bc_csv(tmp_path / "second.csv", "second.dat")
    with pytest.raises(ValueError, match="Multiple active"):
        TCF(tcf).context(file_resolution="deferred").deferred_database_sources()


def test_missing_cached_ad_bc_database_fails_closed(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "AD Global Database == global.csv\nAD BC Database == missing.csv\n",
        encoding="utf-8",
    )
    (tmp_path / "global.csv").write_text(
        "Name,Initial Condition,Minimum Dispersion\nTracer,0,0\n",
        encoding="utf-8",
    )
    with pytest.raises(DeferredDatabaseResolutionError, match="has not been loaded"):
        TCF(tcf).context(file_resolution="deferred").deferred_database_sources()


def test_rainfall_index_secondary_paths_without_raster_reads(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("Read Grid RF == rainfall_index.csv\n", encoding="utf-8")
    (tmp_path / "rainfall_index.csv").write_text(
        "0,grids/step_000.tif\n1,grids/step_001.asc\n", encoding="utf-8",
    )
    model = TCF(tcf)

    with (
        patch.object(Path, "open", side_effect=AssertionError("file opened")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
    ):
        run = model.context(file_resolution="deferred")
        sources = run.deferred_database_sources()

    assert {x.path_pattern for x in sources} == {
        tmp_path / "grids" / "step_000.tif",
        tmp_path / "grids" / "step_001.asc",
    }
    assert all(x.database_kind == "rainfall" for x in sources)
    assert all(x.requires_raster_metadata_scan for x in sources)
    assert all(x.database_path == tmp_path / "rainfall_index.csv" for x in sources)


def test_invalid_rainfall_index_missing_grid_fails_closed(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("Read Grid RF == rainfall_index.csv\n", encoding="utf-8")
    (tmp_path / "rainfall_index.csv").write_text(
        "0,step_000.tif\n1,\n", encoding="utf-8",
    )
    with pytest.raises(DeferredDatabaseResolutionError, match="Empty rainfall"):
        TCF(tcf).context(file_resolution="deferred").deferred_database_sources()


def test_netcdf_rainfall_is_terminal_primary_not_database(tmp_path):
    cfg = _cfg(tmp_path)
    command = Command("Read Grid RF == rain.nc", cfg)
    ref = make_file_reference(next(command.parts()))
    assert ref.database_kind == "rainfall_netcdf"
    assert not ref.requires_database_scan
    assert ref.requires_raster_metadata_scan
    assert ref.path_pattern == tmp_path / "rain.nc"

    tcf = tmp_path / "model.tcf"
    tcf.write_text("Read Grid RF == rain.nc\n", encoding="utf-8")
    model = TCF(tcf)
    run = model.context(file_resolution="deferred")
    assert run.deferred_database_sources() == ()
    assert [x.path_pattern for inp in run.find_input() for x in inp.file_references] == [
        tmp_path / "rain.nc",
    ]


def test_table_link_is_a_gis_attribute_scan_not_csv_database(tmp_path):
    command = Command(
        "Read GIS Table Links == gis/1d_xs_001.shp", _cfg(tmp_path),
    )
    ref = make_file_reference(next(command.parts()))
    assert ref.database_kind == "gis_table_links"
    assert ref.requires_table_link_scan
    assert ref.requires_attribute_scan
    assert not ref.requires_database_scan

    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "Read GIS Table Links == gis/1d_xs_001.shp\n", encoding="utf-8",
    )
    run = TCF(tcf).context(file_resolution="deferred")
    inp = run.find_input(lhs="Read GIS Table Links")[0]
    assert inp.file_references[0].requires_table_link_scan


def test_bc_database_paths_include_context_expansion(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "Set Variable ABC == suffix\nAD Global Database == global.csv\n"
        "AD BC Database == ad.csv\n",
        encoding="utf-8",
    )
    (tmp_path / "global.csv").write_text(
        "Name,Initial Condition,Minimum Dispersion\nTracer,0,0\n",
        encoding="utf-8",
    )
    _bc_csv(tmp_path / "ad.csv", "ad_<<ABC>>.csv")
    run = TCF(tcf).context(file_resolution="deferred")
    sources = run.deferred_database_sources()
    assert len(sources) == 1
    assert sources[0].database_kind == "ad_bc"
    assert sources[0].path_pattern == tmp_path / "ad_suffix.csv"


def test_pit_inlet_and_depth_discharge_sources_are_typed(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "Pit Inlet Database == pit.csv\n"
        "Depth Discharge Database == curves.csv\n",
        encoding="utf-8",
    )
    for filename, source in [
        ("pit.csv", "pit_curve.csv"),
        ("curves.csv", "network_curve.csv"),
    ]:
        (tmp_path / filename).write_text(
            "Name,Source,Depth_Col,Flow_Col,Area,Width\n"
            + "aa," + source + ",Depth,Flow,0,0\n",
            encoding="utf-8",
        )

    model = TCF(tcf)
    with (
        patch.object(Path, "open", side_effect=AssertionError("file opened")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
    ):
        refs = model.context(file_resolution="deferred").deferred_database_sources()
    assert {(ref.database_kind, ref.path_pattern.name) for ref in refs} == {
        ("pit_inlet", "pit_curve.csv"),
        ("depth_discharge", "network_curve.csv"),
    }
    assert all(ref.entry_name == "aa" for ref in refs)


@pytest.mark.parametrize("row", ["aa,,Depth,Flow,0,0", "aa,<<UNKNOWN>>,Depth,Flow,0,0"])
def test_invalid_pit_sources_fail_closed(tmp_path, row):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("Pit Inlet Database == pit.csv\n", encoding="utf-8")
    (tmp_path / "pit.csv").write_text(
        "Name,Source,Depth_Col,Flow_Col,Area,Width\n" + row + "\n",
        encoding="utf-8",
    )
    with pytest.raises(DeferredDatabaseResolutionError):
        TCF(tcf).context(file_resolution="deferred").deferred_database_sources()


def test_network_file_roles_do_not_treat_curve_ids_as_paths():
    from pytuflow._tmf.gis import network_attribute_file_sources

    attrs = ["id", "Q", "", "", "", "", "", "", "", "", "aa"]
    assert network_attribute_file_sources(attrs) == ()
    attrs[1] = "P"
    assert network_attribute_file_sources(attrs) == ()
    attrs[1] = "PO"
    assert network_attribute_file_sources(attrs) == ()
    attrs[1] = "QO"
    attrs[10] = "pump_rule | operational.csv"
    assert network_attribute_file_sources(attrs) == ("operational.csv",)
    attrs[1] = "M"
    attrs[10] = "flow.csv | area.csv"
    assert network_attribute_file_sources(attrs) == ("flow.csv", "area.csv")
    attrs[2] = "Y"
    assert network_attribute_file_sources(attrs) == ()
    attrs[2] = "t"
    assert network_attribute_file_sources(attrs) == ()


def test_incomplete_network_qo_expression_rejected():
    from pytuflow._tmf.gis import network_attribute_file_sources

    attrs = ["id", "QO", "", "", "", "", "", "", "", "", "control_only"]
    with pytest.raises(ValueError, match="QO operational"):
        network_attribute_file_sources(attrs)



def test_nested_adcf_materialises_global_layers_and_bc_source_root(tmp_path):
    tcf = tmp_path / "model.tcf"
    adcf = tmp_path / "adcf" / "ad.adcf"
    adcf.parent.mkdir()
    tables = tmp_path / "tables"
    tables.mkdir()
    tcf.write_text("AD Control File == adcf/ad.adcf\n", encoding="utf-8")
    adcf.write_text(
        "AD Global Database == ../tables/constituents.csv\n"
        "AD BC Database == ../adbc/conditions.csv\n",
        encoding="utf-8",
    )
    (tmp_path / "adbc").mkdir()
    _bc_csv(tmp_path / "adbc" / "conditions.csv", "source_series.csv")
    (tables / "constituents.csv").write_text(
        "Name,Initial Condition,Minimum Dispersion\n"
        "Salinity,../gis/2d_ad_ic.gpkg >> 2d_ad_ic_Salinity,../gis/2d_ad_md.shp\n"
        "Heat,12.5,0\n",
        encoding="utf-8",
    )
    model = TCF(tcf)
    with (
        patch.object(Path, "open", side_effect=AssertionError("open")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
        patch("sqlite3.connect", side_effect=AssertionError("sqlite")),
    ):
        run = model.context(file_resolution="deferred")
        refs = run.deferred_database_sources()
    kinds = {(ref.database_kind, ref.path_pattern.name) for ref in refs}
    assert ("ad_bc", "source_series.csv") in kinds
    assert ("ad_global", "2d_ad_ic.gpkg") in kinds
    assert ("ad_global", "2d_ad_md.shp") in kinds
    bc = next(ref for ref in refs if ref.database_kind == "ad_bc")
    assert bc.path_pattern == adcf.parent / "../tables/source_series.csv"
    global_gpkg = next(ref for ref in refs if ref.path_pattern.name == "2d_ad_ic.gpkg")
    assert global_gpkg.layer_pattern == "2d_ad_ic_Salinity"
    assert global_gpkg.requires_layer_scan
    assert global_gpkg.source_field == "initial condition"
    assert global_gpkg.entry_name == "Salinity"
    assert global_gpkg.owner_control_file == adcf


def test_ad_global_blank_minimum_dispersion_is_invalid(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("AD Global Database == ad_global.csv\n", encoding="utf-8")
    (tmp_path / "ad_global.csv").write_text(
        "Name,Initial Condition,Minimum Dispersion\nTracer,3,\n",
        encoding="utf-8",
    )
    with pytest.raises(DeferredDatabaseResolutionError, match="Minimum Dispersion"):
        TCF(tcf).context(file_resolution="deferred").deferred_database_sources()


def test_ad_global_numeric_only_has_no_secondary_files(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("AD Global Database == ad_global.csv\n", encoding="utf-8")
    (tmp_path / "ad_global.csv").write_text(
        "Name,Initial Condition,Minimum Dispersion\nTracer,,0\n",
        encoding="utf-8",
    )
    assert TCF(tcf).context(file_resolution="deferred").deferred_database_sources() == ()


def test_ad_bc_fails_closed_if_global_database_is_ambiguous(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "AD Global Database == one.csv\n"
        "AD Global Database == two.csv\n"
        "AD BC Database == ad_bc.csv\n",
        encoding="utf-8",
    )
    for name in ("one.csv", "two.csv"):
        (tmp_path / name).write_text(
            "Name,Initial Condition,Minimum Dispersion\nTracer,0,0\n",
            encoding="utf-8",
        )
    _bc_csv(tmp_path / "ad_bc.csv", "source.csv")
    with pytest.raises(ValueError, match=r"Multiple active ad global|requires one active"):
        TCF(tcf).context(file_resolution="deferred").deferred_database_sources()



def test_cross_section_csv_database_source_files(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("XS Database == xs.csv\n", encoding="utf-8")
    (tmp_path / "xs.csv").write_text(
        "Name,Source,Type,Flags\n"
        "section1,sections/one.csv,XZ,\n"
        "section2,sections/two.csv,CS,\n",
        encoding="utf-8",
    )
    model = TCF(tcf)
    with (
        patch.object(Path, "open", side_effect=AssertionError("open")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
    ):
        sources = model.context(file_resolution="deferred").deferred_database_sources()
    assert {r.database_kind for r in sources} == {"cross_section"}
    assert {r.path_pattern for r in sources} == {
        tmp_path / "sections" / "one.csv",
        tmp_path / "sections" / "two.csv",
    }


def test_cross_section_without_source_column_fails_closed(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("XS Database == xs.csv\n", encoding="utf-8")
    (tmp_path / "xs.csv").write_text(
        "Name,Other\nsection1,not-a-file\n", encoding="utf-8",
    )
    with pytest.raises(DeferredDatabaseResolutionError, match="no Source column"):
        TCF(tcf).context(file_resolution="deferred").deferred_database_sources()



def test_multiple_rainfall_indexes_and_netcdf_are_independently_projected(tmp_path):
    """Multiple RF commands represent additive inputs, not ambiguous DB roles."""
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "Read Grid RF == east.csv\n"
        "Read Grid RF == satellite.nc\n"
        "Read Grid RF == west.csv\n",
        encoding="utf-8",
    )
    (tmp_path / "east.csv").write_text("0,grids/east_000.tif\n", encoding="utf-8")
    (tmp_path / "west.csv").write_text("0,grids/west_000.tif\n", encoding="utf-8")
    model = TCF(tcf)
    with (
        patch.object(Path, "open", side_effect=AssertionError("file opened")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
        patch("sqlite3.connect", side_effect=AssertionError("SQLite")),
    ):
        run = model.context(file_resolution="deferred")
        secondary = run.deferred_database_sources()
    assert {(ref.database_path.name, ref.path_pattern.name) for ref in secondary} == {
        ("east.csv", "east_000.tif"),
        ("west.csv", "west_000.tif"),
    }
    assert all(ref.requires_raster_metadata_scan for ref in secondary)
    primaries = [
        ref for inp in run.find_input(lhs="Read Grid RF")
        for ref in inp.file_references
    ]
    assert {ref.path_pattern.name for ref in primaries} == {
        "east.csv", "satellite.nc", "west.csv",
    }
    assert {ref.database_kind for ref in primaries} == {
        "rainfall", "rainfall_netcdf",
    }



def test_multiple_material_files_contribute_independent_sources(tmp_path):
    """TUFLOW permits more than one Read Materials File command."""
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "Read Materials File == rock.csv | 0.85\n"
        "Read Material File == soil_roughness.csv\n",
        encoding="utf-8",
    )
    (tmp_path / "rock.csv").write_text(
        "Material ID,Manning's n\n1,rock_roughness.csv\n",
        encoding="utf-8",
    )
    (tmp_path / "soil_roughness.csv").write_text(
        "Material ID,Manning's n\n2,0.04\n",
        encoding="utf-8",
    )
    model = TCF(tcf)
    with (
        patch.object(Path, "open", side_effect=AssertionError("open")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
    ):
        run = model.context(file_resolution="deferred")
        sources = run.deferred_database_sources()
    assert len(sources) == 1
    assert sources[0].path_pattern == tmp_path / "rock_roughness.csv"
    assert sources[0].database_path == tmp_path / "rock.csv"
    assert {
        ref.path_pattern.name for inp in run.find_input()
        for ref in inp.file_references if ref.database_kind == "materials"
    } == {"rock.csv", "soil_roughness.csv"}



def test_bc_database_reassignments_retain_order_and_do_not_merge(tmp_path):
    """A later BC Database changes the active table for subsequent BC inputs."""
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "BC Database == before.csv\n"
        "Read GIS BC == gis/2d_bc_before.shp\n"
        "BC Database == after.csv\n"
        "Read GIS BC == gis/2d_bc_after.shp\n",
        encoding="utf-8",
    )
    _bc_csv(tmp_path / "before.csv", "first.csv")
    _bc_csv(tmp_path / "after.csv", "second.csv")
    model = TCF(tcf)
    with (
        patch.object(Path, "open", side_effect=AssertionError("open")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
        patch("sqlite3.connect", side_effect=AssertionError("sqlite")),
    ):
        run = model.context(file_resolution="deferred")
        activations = run.deferred_database_activations()
    bc = [entry for entry in activations if entry.database_kind == "bc"]
    assert [entry.database_path.name for entry in bc] == ["before.csv", "after.csv"]
    assert bc[0].sequence < bc[1].sequence
    assert bc[0].input_uuid != bc[1].input_uuid
    assert all(entry.owning_command.casefold() == "bc database" for entry in bc)
    assert all(entry.owner_control_file == tcf for entry in bc)
    with pytest.raises(ValueError, match="Multiple active bc"):
        run.deferred_database_sources()


def test_scenario_scoping_of_database_activations(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "If Scenario == EXG\n"
        "    BC Database == exg.csv\n"
        "Else\n"
        "    BC Database == dev.csv\n"
        "End If\n",
        encoding="utf-8",
    )
    _bc_csv(tmp_path / "exg.csv", "existing.csv")
    _bc_csv(tmp_path / "dev.csv", "developed.csv")
    model = TCF(tcf)
    exg = model.context("-s1 EXG", file_resolution="deferred")
    dev = model.context("-s1 DEV", file_resolution="deferred")
    assert [x.database_path.name for x in exg.deferred_database_activations()
            if x.database_kind == "bc"] == ["exg.csv"]
    assert [x.database_path.name for x in dev.deferred_database_activations()
            if x.database_kind == "bc"] == ["dev.csv"]



def test_eager_rainfall_csv_inventory_includes_cached_grid_sources(tmp_path):
    """Correct eager omission rather than accepting extra deferred grids."""
    tcf = tmp_path / "model.tcf"
    tcf.write_text("Read Grid RF == rf_index.csv\n", encoding="utf-8")
    (tmp_path / "rf_index.csv").write_text(
        "0,grids/first.tif\n1,grids/second.asc\n", encoding="utf-8",
    )
    model = TCF(tcf)
    eager = model.context(file_resolution="eager")
    input_ = eager.find_input(lhs="Read Grid RF")[0]
    files = input_.files
    assert {path.name for path in files} == {
        "rf_index.csv", "first.tif", "second.asc",
    }
    deferred = model.context(file_resolution="deferred")
    assert {source.path_pattern for source in deferred.deferred_database_sources()} == {
        path for path in files if path.name != "rf_index.csv"
    }


def test_eager_rainfall_grid_projection_is_cached_in_memory(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("Read Grid RF == rf.csv\n", encoding="utf-8")
    (tmp_path / "rf.csv").write_text("0,grid.tif\n", encoding="utf-8")
    model = TCF(tcf)
    run = model.context(file_resolution="eager")
    input_ = run.find_input(lhs="Read Grid RF")[0]
    source = input_.files
    # Only cached projection is probe-free: ordinary eager context creation
    # and first primary-file resolution may legitimately touch the disk.
    with (
        patch.object(Path, "open", side_effect=AssertionError("file opened")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
    ):
        again = input_.files
    assert source == again
    assert [p.name for p in source] == ["rf.csv", "grid.tif"]



def test_blank_hydraulic_bc_source_uses_numeric_constant_not_file(tmp_path):
    """TUFLOW Table 8.13 permits Source blank with numeric Column 2."""
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "Set Variable BCConstant == 2.75\n"
        "BC Database == conditions.csv\n",
        encoding="utf-8",
    )
    (tmp_path / "conditions.csv").write_text(
        "Name,Source,Column 1,Column 2\n"
        "GT01,,,<<BCConstant>>\n"
        "QT01,flows.csv,Time,Flow\n",
        encoding="utf-8",
    )
    model = TCF(tcf)
    with (
        patch.object(Path, "open", side_effect=AssertionError("file opened")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
    ):
        run = model.context(file_resolution="deferred")
        references = run.deferred_database_sources()
    assert len(references) == 1
    assert references[0].database_kind == "bc"
    assert references[0].entry_name == "QT01"
    assert references[0].path_pattern == tmp_path / "flows.csv"


@pytest.mark.parametrize("blank_row", [
    "GT01,,,",
    "GT01,,,not-numeric",
])
def test_blank_bc_source_without_numeric_constant_fails_closed(tmp_path, blank_row):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("BC Database == conditions.csv\n", encoding="utf-8")
    (tmp_path / "conditions.csv").write_text(
        "Name,Source,Column 1,Column 2\n" + blank_row + "\n",
        encoding="utf-8",
    )
    with pytest.raises(DeferredDatabaseResolutionError, match="Column 2"):
        TCF(tcf).context(file_resolution="deferred").deferred_database_sources()


def test_ad_bc_blank_source_remains_invalid_even_with_column_two(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "AD Global Database == constituents.csv\n"
        "AD BC Database == ad.csv\n",
        encoding="utf-8",
    )
    (tmp_path / "constituents.csv").write_text(
        "Name,Initial Condition,Minimum Dispersion\nSalinity,0,0\n",
        encoding="utf-8",
    )
    (tmp_path / "ad.csv").write_text(
        "Name,Source,Column 1,Column 2\n"
        "Ocean__Salinity,,,3.2\n",
        encoding="utf-8",
    )
    with pytest.raises(DeferredDatabaseResolutionError, match="Empty ad_bc source"):
        TCF(tcf).context(file_resolution="deferred").deferred_database_sources()



def test_rainfall_index_csv_requires_table_scan_not_raster_metadata(tmp_path):
    index = make_file_reference(next(
        Command("Read Grid RF == rain_index.csv", _cfg(tmp_path)).parts()
    ))
    assert index.database_kind == "rainfall"
    assert index.requires_database_scan
    assert not index.requires_raster_metadata_scan
    netcdf = make_file_reference(next(
        Command("Read Grid RF == rain.nc", _cfg(tmp_path)).parts()
    ))
    assert netcdf.database_kind == "rainfall_netcdf"
    assert not netcdf.requires_database_scan
    assert netcdf.requires_raster_metadata_scan



@pytest.mark.parametrize("selector", [
    "FEWS | rainfall.csv",
    "fews|rainfall.xml",
])
def test_bc_fews_selector_references_only_actual_source_file(tmp_path, selector):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("BC Database == bc.csv\n", encoding="utf-8")
    (tmp_path / "bc.csv").write_text(
        "Name,Source,Column 1,Column 2\n"
        + f"Weather,{selector},,\n",
        encoding="utf-8",
    )
    run = TCF(tcf).context(file_resolution="deferred")
    sources = run.deferred_database_sources()
    assert len(sources) == 1
    assert sources[0].path_pattern == tmp_path / selector.split("|")[1].strip()
    assert sources[0].entry_name == "Weather"
    assert all(source.path_pattern.name.upper() != "FEWS" for source in sources)


@pytest.mark.parametrize("selector", [
    "FEWS |",
    "FEWS | rainfall.csv | ambiguous.csv",
    "FEWS | not_a_filename",
])
def test_invalid_fews_source_fails_closed(tmp_path, selector):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("BC Database == bc.csv\n", encoding="utf-8")
    (tmp_path / "bc.csv").write_text(
        "Name,Source,Column 1,Column 2\n"
        + f"Weather,{selector},,\n",
        encoding="utf-8",
    )
    with pytest.raises(DeferredDatabaseResolutionError, match="Invalid FEWS"):
        TCF(tcf).context(file_resolution="deferred").deferred_database_sources()



@pytest.mark.parametrize(
    ("command", "filename", "header", "row", "kind"),
    [
        (
            "AD BC Database", "ad.csv",
            "Name,Source,Column 1,Column 2",
            "Ocean__Tracer,123,Time,Concentration", "ad_bc",
        ),
        (
            "Pit Inlet Database", "pit.csv",
            "Name,Source,Depth_Col,Flow_Col,Area,Width",
            "Inlet_A,123,Depth,Flow,0,0", "pit_inlet",
        ),
        (
            "Depth Discharge Database", "curves.csv",
            "Name,Source,Depth_Col,Flow_Col,Area,Width",
            "Curve_A,123,Depth,Flow,0,0", "depth_discharge",
        ),
        (
            "XS Database", "xs.csv",
            "Name,Source,Type,Flags",
            "XS_A,123,XZ,", "cross_section",
        ),
    ],
)
def test_numeric_required_secondary_source_fails_closed(
    tmp_path, command, filename, header, row, kind
):
    """A numeric-looking required Source must not vanish from the inventory."""
    tcf = tmp_path / "model.tcf"
    prefix = ""
    if kind == "ad_bc":
        (tmp_path / "global.csv").write_text(
            "Name,Initial Condition,Minimum Dispersion\nTracer,0,0\n",
            encoding="utf-8",
        )
        prefix = "AD Global Database == global.csv\n"
    tcf.write_text(
        prefix + f"{command} == {filename}\n", encoding="utf-8",
    )
    (tmp_path / filename).write_text(
        header + "\n" + row + "\n", encoding="utf-8",
    )
    with pytest.raises(
        DeferredDatabaseResolutionError,
        match=f"Numeric {kind} Source",
    ):
        TCF(tcf).context(file_resolution="deferred").deferred_database_sources()


def test_deferred_database_sources_for_selected_bc_activation(tmp_path):
    """The consumer chooses an active table by UUID; unused tables stay distinct."""
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        "BC Database == upstream.csv\n"
        "Read GIS BC == gis/2d_bc_upstream.shp\n"
        "BC Database == downstream.csv\n"
        "Read GIS BC == gis/2d_bc_downstream.shp\n",
        encoding="utf-8",
    )
    _bc_csv(tmp_path / "upstream.csv", "upstream_hydrograph.csv")
    _bc_csv(tmp_path / "downstream.csv", "downstream_hydrograph.csv")
    model = TCF(tcf)
    with (
        patch.object(Path, "open", side_effect=AssertionError("file opened")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
        patch("sqlite3.connect", side_effect=AssertionError("sqlite")),
    ):
        run = model.context(file_resolution="deferred")
        bc = [entry for entry in run.deferred_database_activations()
              if entry.database_kind == "bc"]
        assert len(bc) == 2
        first = run.deferred_database_sources_for_activation(bc[0].input_uuid)
        second = run.deferred_database_sources_for_activation(bc[1].input_uuid)
    assert [ref.path_pattern.name for ref in first] == ["upstream_hydrograph.csv"]
    assert [ref.path_pattern.name for ref in second] == ["downstream_hydrograph.csv"]
    assert all(ref.input_uuid == bc[0].input_uuid for ref in first)
    assert all(ref.input_uuid == bc[1].input_uuid for ref in second)
    assert first[0].database_path == bc[0].database_path
    assert second[0].database_path == bc[1].database_path
    with pytest.raises(ValueError, match="Expected exactly one"):
        run.deferred_database_sources_for_activation("missing")
    with pytest.raises(ValueError, match="Multiple active bc"):
        run.deferred_database_sources()


def test_selected_activation_requires_deferred_mode(tmp_path):
    tcf = tmp_path / "model.tcf"
    tcf.write_text("BC Database == bc.csv\n", encoding="utf-8")
    _bc_csv(tmp_path / "bc.csv", "hydrograph.csv")
    run = TCF(tcf).context(file_resolution="eager")
    with pytest.raises(ValueError, match="requires deferred mode"):
        run.deferred_database_sources_for_activation("any")


@pytest.mark.parametrize(
    ("expression", "filename", "layer"),
    [
        ("gis/1d_xs_model.shp", "1d_xs_model.shp", None),
        ("gis/cross_sections.gpkg >> all", "cross_sections.gpkg", "all"),
        ("gis/cross_sections.gpkg >> 1d_xs_model", "cross_sections.gpkg", "1d_xs_model"),
    ],
)
def test_table_link_requires_shared_gis_scan_without_loading_geometry(
    tmp_path, expression, filename, layer
):
    """A table-link is a GIS attribute lookup, never a source CSV database."""
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        f"Read GIS Table Links == {expression}\n",
        encoding="utf-8",
    )
    model = TCF(tcf)
    with (
        patch.object(Path, "open", side_effect=AssertionError("file opened")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
        patch("sqlite3.connect", side_effect=AssertionError("sqlite")),
    ):
        run = model.context(file_resolution="deferred")
        inp = run.find_input(lhs="Read GIS Table Links")[0]
        (ref,) = inp.file_references
        assert run.deferred_database_sources() == ()
        assert run.deferred_database_activations() == ()
    assert ref.database_kind == "gis_table_links"
    assert ref.requires_table_link_scan
    assert ref.requires_attribute_scan
    assert not ref.requires_database_scan
    assert not ref.requires_raster_metadata_scan
    assert ref.path_pattern == tmp_path / "gis" / filename
    assert ref.layer_pattern == layer
    assert ref.requires_layer_scan == (layer is not None)


def test_material_csv_separator_and_comment_rows_do_not_become_records(tmp_path):
    from pytuflow._tmf.db.mat import MatDatabase
    path = tmp_path / 'materials.csv'
    path.write_text(
        "Material ID,Manning's n,Losses,Description\n"
        '1,0.05,,first\n'
        ',,,\n'
        '! Documentation,,,\n'
        '2,0.06,,second\n', encoding='utf-8',
    )
    database = MatDatabase(path)
    assert database.loaded
    assert list(database.df.index) == [1, 2]
    assert {int(key) for key in database.entries} == {1, 2}
    source = tmp_path / 'material.tcf'
    source.write_text('Read Materials File == materials.csv\n', encoding='utf-8')
    model = TCF(source)
    for mode in ('eager', 'deferred'):
        state = model.context('-s1 Base', file_resolution=mode)
        assert all(not inp.database_source_references for inp in state.find_input())
    batch = model.collect_file_dependencies(('-s1 Base',))
    assert batch.passed
    assert batch.runs[0].database_sources == ()


def test_material_csv_nonempty_row_without_id_remains_invalid(tmp_path):
    from pytuflow._tmf.db.mat import MatDatabase
    path = tmp_path / 'invalid.csv'
    path.write_text("Material ID,Manning's n\n1,0.05\n,0.06\n", encoding='utf-8')
    with pytest.raises(ValueError):
        MatDatabase(path)

def test_direct_netcdf_rainfall_preserves_public_api_and_deferred_inventory(tmp_path: Path) -> None:
    """Direct NetCDF rainfall inputs are not CSV index databases."""
    from pytuflow._tmf.db.rf import RainfallDatabase

    tcf_path = tmp_path / "model.tcf"
    tcf_path.write_text("Read Grid RF == rain.nc\n", encoding="utf-8")
    model = TCF(tcf_path)

    database = model.rainfall_dbase()
    assert isinstance(database, RainfallDatabase)
    assert database.fpath is None
    assert not database.loaded
    assert database.df.empty

    # A compatibility placeholder does not represent a file to enter.
    assert model.context().find_input(lhs="Read Grid RF")
    assert model.context(file_resolution="deferred").find_input(lhs="Read Grid RF")

    dependencies = model.collect_file_dependencies(["-s1 Existing"])
    assert dependencies.passed
    assert [ref.path_pattern.name for ref in dependencies.runs[0].file_references
            if ref.path_pattern.suffix.casefold() == ".nc"] == ["rain.nc"]
    assert not dependencies.runs[0].database_sources

    from pytuflow.batch_validation import validate_batch_inputs

    report = validate_batch_inputs(model, ["-s1 Existing"])
    assert not report.passed
    assert any(issue.path is not None and issue.path.name == "rain.nc"
               for issue in report.issues)


@pytest.mark.skipif(os.name == "nt", reason="Linux filename case policy")
@pytest.mark.parametrize(
    ("level", "requested"),
    [
        (1, "Materials.CSV"),
        (2, "materials.csv"),
    ],
)
def test_cached_materials_database_respects_filename_case_policy(
    tmp_path: Path, level: int, requested: str
) -> None:
    """A syntactic alias must select an already-loaded physical CSV."""
    material = tmp_path / "Materials.csv"
    material.write_text(
        "Material ID,Manning's n\n1,0.03\n", encoding="utf-8"
    )
    tcf = tmp_path / "model.tcf"
    tcf.write_text(
        f"Read Materials File == {requested}\n", encoding="utf-8"
    )
    model = TCF(tcf, case_sensitivity=level)
    loaded = model.find_input(lhs="Read Materials File")[0]
    assert loaded.cf and loaded.cf[0].loaded
    run = model.context(file_resolution="deferred")
    with (
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
        patch.object(Path, "open", side_effect=AssertionError("open")),
        patch.object(TuflowPath, "glob", side_effect=AssertionError("glob")),
        patch("sqlite3.connect", side_effect=AssertionError("SQLite")),
    ):
        assert run.database_sources() == ()
        deps = model.collect_file_dependencies(["-s1 BASE"])
    assert deps.passed, [item.error for item in deps.runs]
    assert [ref.path_pattern.name for ref in deps.runs[0].file_references
            if ref.database_kind == "materials"] == [requested]


@pytest.mark.skipif(os.name == "nt", reason="Linux filename case policy")
def test_cached_database_case_collision_uses_exact_name_without_io(
    tmp_path: Path
) -> None:
    """Exact alias wins; case-only nonexact collisions fail closed."""
    from pytuflow._tmf.context import Context

    cfg = _cfg(tmp_path)
    cfg.case_sensitivity = 2
    database_a = SimpleNamespace(loaded=True, fpath=tmp_path / "Materials.csv",
                                 df=pd.DataFrame({"Manning": [0.03]}))
    database_b = SimpleNamespace(loaded=True, fpath=tmp_path / "materials.csv",
                                 df=pd.DataFrame({"Manning": [0.04]}))
    build = SimpleNamespace(
        cf=[database_a, database_b],
        _database_loaded_paths=[database_a.fpath, database_b.fpath],
    )
    context = Context(config=cfg)
    with patch.object(Path, "stat", side_effect=AssertionError("stat")):
        assert database_source_references(
            build, context, "materials", cfg,
            primary_path=database_a.fpath,
        ) == ()
        with pytest.raises(DeferredDatabaseResolutionError, match="found 2"):
            database_source_references(
                build, context, "materials", cfg,
                primary_path=tmp_path / "MATERIALS.csv",
            )


@pytest.mark.skipif(os.name == "nt", reason="Linux filename case policy")
def test_cached_database_directory_case_mismatch_fails_closed(tmp_path: Path) -> None:
    """-cs2 can relax the filename, but not any directory component."""
    from pytuflow._tmf.context import Context

    cfg = _cfg(tmp_path)
    cfg.case_sensitivity = 2
    original = tmp_path / "Area" / "Materials.csv"
    database = SimpleNamespace(
        loaded=True, fpath=original,
        df=pd.DataFrame({"Manning": [0.03]}),
    )
    build = SimpleNamespace(cf=[database], _database_loaded_paths=[original])
    with pytest.raises(DeferredDatabaseResolutionError, match="found 0"):
        database_source_references(
            build, Context(config=cfg), "materials", cfg,
            primary_path=tmp_path / "area" / "materials.csv",
        )


def test_cached_database_different_root_is_not_an_alias(tmp_path: Path) -> None:
    from pytuflow._tmf.context import Context

    cfg = _cfg(tmp_path)
    original = Path('Q:/models/Materials.csv')
    database = SimpleNamespace(loaded=True, fpath=original,
                               df=pd.DataFrame({'Manning': [0.03]}))
    build = SimpleNamespace(cf=[database], _database_loaded_paths=[original])
    for requested in (Path('R:/models/Materials.csv'),
                      Path(r'\\server\share\models\Materials.csv')):
        with pytest.raises(DeferredDatabaseResolutionError, match='found 0'):
            database_source_references(build, Context(config=cfg), 'materials', cfg,
                                       primary_path=requested)
