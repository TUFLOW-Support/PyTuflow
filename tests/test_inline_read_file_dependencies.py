"""Regression coverage for inline Read File declarations in batch inventories."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pytuflow import TCF
from pytuflow._tmf.deferred_dependency_fallback import collect_fallback_dependencies
from pytuflow._tmf.tfpathlib import TuflowPath
from pytuflow.batch_validation import validate_batch_inputs


def _trd_references(model: TCF, flags: list[str]) -> tuple[tuple[str, ...], ...]:
    """List inline source names from each selected dependency run."""
    result = model.collect_file_dependencies(flags)
    assert result.passed, result.runs
    assert result.fallback_runs == 0
    return tuple(
        tuple(ref.path_pattern.name for ref in run.file_references
              if ref.path_pattern.suffix.lower() == ".trd")
        for run in result.runs
    )


def test_missing_static_inline_read_file_never_passes_preflight(tmp_path: Path) -> None:
    """Missing Read File must not disappear when there are no child commands."""
    top = tmp_path / "model.tcf"
    top.write_text(
        "Start Time == 0\nRead File == missing.trd\n", encoding="utf-8"
    )
    model = TCF(top)
    assert not model.find_input(lhs="Read File")
    assert _trd_references(model, ["-s1 Existing"]) == (("missing.trd",),)

    report = validate_batch_inputs(model, ["-s1 Existing"])
    assert not report.passed
    assert report.dependencies.runs[0].error is None
    assert any(
        issue.status == "missing"
        and issue.path == tmp_path / "missing.trd"
        and issue.owner_control_file == top
        for issue in report.issues
    ), report.issues
    assert "Read File" in [
        item.command_name for item in report.dependencies.runs[0].ordered_inputs
    ]


def test_empty_existing_inline_file_is_still_a_required_source(tmp_path: Path) -> None:
    """An empty TRD has a declaration even though it contains no commands."""
    (tmp_path / "empty.trd").write_text("! no commands\n", encoding="utf-8")
    top = tmp_path / "model.tcf"
    top.write_text("Start Time == 0\nRead File == empty.trd\n", encoding="utf-8")
    model = TCF(top)
    assert _trd_references(model, ["-s1 Existing"]) == (("empty.trd",),)

    report = validate_batch_inputs(model, ["-s1 Existing"])
    assert report.passed, report.issues
    assert any(
        item.path == tmp_path / "empty.trd" and item.status == "present"
        for item in report.validation.findings
    )


def test_parsed_trd_deleted_before_preflight_is_missing(tmp_path: Path) -> None:
    """A deleted TRD must not be hidden by its initially expanded commands."""
    trd = tmp_path / "include.trd"
    trd.write_text("Start Time == 0\n", encoding="utf-8")
    top = tmp_path / "model.tcf"
    top.write_text("Read File == include.trd\n", encoding="utf-8")
    model = TCF(top)
    assert model.find_input(lhs="Start Time")

    trd.unlink()
    assert _trd_references(model, ["-s1 Existing"]) == (("include.trd",),)
    report = validate_batch_inputs(model, ["-s1 Existing"])
    assert not report.passed
    assert any(
        issue.kind == "file"
        and issue.path == trd
        and issue.status == "missing"
        for issue in report.issues
    )


def test_inline_declaration_precedes_expanded_content_in_both_evaluators(
    tmp_path: Path,
) -> None:
    """Fast fragments and ordinary deferred fallback agree on source order."""
    trd = tmp_path / "include.trd"
    trd.write_text("Read Grid Zpts == grid.tif\n", encoding="utf-8")
    top = tmp_path / "model.tcf"
    top.write_text(
        "Start Time == 0\n"
        "Read File == include.trd\n"
        "End Time == 1\n",
        encoding="utf-8",
    )
    model = TCF(top)
    flags = ["-s1 Existing", "-s1 Proposed"]
    fast = model.collect_file_dependencies(flags)
    slow = collect_fallback_dependencies(model, flags)
    assert fast.passed and slow.passed
    assert fast.runs == slow.runs
    assert [item.command_name for item in fast.runs[0].ordered_inputs] == [
        "Start Time", "Read File", "Read Grid Zpts", "End Time",
    ]
    assert [ref.path_pattern.name for ref in fast.runs[0].file_references] == [
        "include.trd", "grid.tif",
    ]
    assert [ref.path_pattern.name for inp in model.context(
        file_resolution="deferred"
    ).find_input() for ref in inp.file_references] == [
        "include.trd", "grid.tif",
    ]


def test_scoped_inline_read_file_requires_only_selected_source(tmp_path: Path) -> None:
    """An inactive scenario's missing TRD must not create a false finding."""
    active = tmp_path / "active.trd"
    active.write_text("Start Time == 0\n", encoding="utf-8")
    top = tmp_path / "model.tcf"
    top.write_text(
        "IF Scenario == DEV\n"
        " Read File == active.trd\n"
        "ELSE\n"
        " Read File == absent.trd\n"
        "END IF\n",
        encoding="utf-8",
    )
    model = TCF(top)
    flags = ["-s1 DEV", "-s1 EXG"]
    assert _trd_references(model, flags) == (("active.trd",), ("absent.trd",))
    result = validate_batch_inputs(model, flags)
    assert not result.passed
    assert not any(issue.run_index == 0 for issue in result.issues)
    assert any(
        issue.run_index == 1 and issue.path == tmp_path / "absent.trd"
        and issue.status == "missing"
        for issue in result.issues
    )


def test_nested_control_file_keeps_inline_declaration_and_ownership(tmp_path: Path) -> None:
    """An inline declaration in a TGC is attributed to that child file."""
    geometry = tmp_path / "geometry.tgc"
    geometry.write_text("Read File == missing_geometry.trd\n", encoding="utf-8")
    top = tmp_path / "model.tcf"
    top.write_text("Geometry Control File == geometry.tgc\n", encoding="utf-8")
    model = TCF(top)
    fast = model.collect_file_dependencies(["-s1 DEV"])
    slow = collect_fallback_dependencies(model, ["-s1 DEV"])
    assert fast.passed and slow.passed
    assert fast.runs == slow.runs
    matches = [
        item for item in fast.runs[0].input_references
        if item.reference.path_pattern.name == "missing_geometry.trd"
    ]
    assert len(matches) == 1
    assert matches[0].owner_control_file == geometry
    assert matches[0].line_number == 1
    checked = validate_batch_inputs(model, ["-s1 DEV"])
    assert any(
        issue.status == "missing"
        and issue.path == tmp_path / "missing_geometry.trd"
        and issue.owner_control_file == geometry
        for issue in checked.issues
    )


def test_wildcard_inline_includes_remain_lexical_after_parse(tmp_path: Path) -> None:
    """The collector itself must not glob included files a second time."""
    includes = tmp_path / "include"
    includes.mkdir()
    (includes / "one.trd").write_text("Start Time == 0\n", encoding="utf-8")
    (includes / "two.trd").write_text("End Time == 1\n", encoding="utf-8")
    top = tmp_path / "model.tcf"
    top.write_text("Read File == include/*.trd\n", encoding="utf-8")
    model = TCF(top)
    with patch.object(TuflowPath, "glob", side_effect=AssertionError("collector glob")):
        result = model.collect_file_dependencies(["-s1 DEV", "-s1 EXG"])
    assert result.passed, result.runs
    assert all(
        any(ref.path_pattern.name == "*.trd"
            and ref.requires_directory_scan for ref in run.file_references)
        for run in result.runs
    )


@pytest.mark.parametrize("scenario", ["DEV", "EXG"])
def test_inline_read_file_keeps_scenario_path_expansion(
    tmp_path: Path, scenario: str
) -> None:
    """A late-bound Read File filename is retained as an active dependency."""
    top = tmp_path / "model.tcf"
    top.write_text(
        "Read File == include_<<~s1~>>.trd\n", encoding="utf-8"
    )
    model = TCF(top)
    result = model.collect_file_dependencies([f"-s1 {scenario}"])
    assert result.passed, result.runs
    assert any(
        ref.path_pattern.name == f"include_{scenario}.trd"
        for ref in result.runs[0].file_references
    )


@pytest.mark.parametrize("fallback", [False, True])
def test_inline_order_tracks_edits_on_parsed_model(tmp_path: Path, fallback: bool) -> None:
    """Collect current input order after insertion and removal without reparsing."""
    (tmp_path / "include.trd").write_text("Read Grid Zpts == inner.tif\n")
    top = tmp_path / "model.tcf"
    top.write_text("Start Time == 0\nRead File == include.trd\nEnd Time == 1\n")
    model = TCF(top)
    collect = collect_fallback_dependencies if fallback else TCF.collect_file_dependencies

    def names() -> list[str]:
        result = collect(model, ["-s1 DEV", "-s1 EXG"])
        assert result.passed, result.runs
        if not fallback:
            assert result.fallback_runs == 0
        for run in result.runs:
            assert [ref.owner_control_file for ref in run.input_references] == [
                top, top,
            ]
        return [item.command_name for item in result.runs[0].ordered_inputs]

    assert names() == ["Start Time", "Read File", "Read Grid Zpts", "End Time"]
    start = model.find_input(lhs="Start Time")[0]
    added = model.insert_input(start, "Timestep == 1")
    assert names() == ["Timestep", "Start Time", "Read File", "Read Grid Zpts", "End Time"]
    model.remove_input(added)
    model.remove_input(start)
    assert names() == ["Read File", "Read Grid Zpts", "End Time"]


@pytest.mark.parametrize("fallback", [False, True])
@pytest.mark.parametrize("empty", [False, True])
def test_edited_nested_dependencies_keep_current_sources(
    tmp_path: Path, fallback: bool, empty: bool,
) -> None:
    """Nested edits include new sources, drop removed ones, and preserve ownership."""
    (tmp_path / "include.trd").write_text(
        "" if empty else "Read Grid Zpts == inside.tif\n"
    )
    child = tmp_path / "geometry.tgc"
    child.write_text(
        "Read Grid Zpts == first.tif\nRead File == include.trd\n"
        "Read Grid Zpts == last.tif\n"
    )
    top = tmp_path / "model.tcf"
    top.write_text("Geometry Control File == geometry.tgc\n")
    model = TCF(top)
    geometry = model.find_input(lhs="Geometry Control File")[0].cf[0]
    collect = collect_fallback_dependencies if fallback else TCF.collect_file_dependencies
    middle = [] if empty else ["inside.tif"]

    def check(expected: list[str]) -> None:
        result = collect(model, ["-s1 DEV", "-s1 EXG"])
        assert result.passed, result.runs
        if not fallback:
            assert result.fallback_runs == 0
        for run in result.runs:
            refs = [ref for ref in run.input_references
                    if ref.reference.path_pattern.name != "geometry.tgc"]
            assert [ref.reference.path_pattern.name for ref in refs] == expected
            assert all(ref.owner_control_file == child for ref in refs)

    original = ["first.tif", "include.trd", *middle, "last.tif"]
    check(original)
    first = geometry.find_input(rhs="first.tif")[0]
    new = geometry.insert_input(first, "Read File == added.trd")
    check(["added.trd", *original])
    geometry.undo()
    check(original)
    new = geometry.insert_input(first, "Read File == added.trd")
    geometry.remove_input(new)
    check(original)
    geometry.remove_input(first)
    check(["include.trd", *middle, "last.tif"])
    geometry.append_input("Read Grid Zpts == added.tif")
    check(["include.trd", *middle, "last.tif", "added.tif"])
    last = geometry.find_input(rhs="last.tif")[0]
    geometry.remove_input(last)
    geometry.insert_input(geometry.inputs[0], last)
    check(["last.tif", "include.trd", *middle, "added.tif"])
