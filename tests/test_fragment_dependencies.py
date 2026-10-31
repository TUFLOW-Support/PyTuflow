"""Correctness and avoided-construction contracts, without timing assertions."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from pytuflow import TCF
from pytuflow._tmf.context import Context
from pytuflow._tmf.deferred_dependency_fallback import collect_fallback_dependencies
from pytuflow._tmf.fragment_dependencies import ExpressionPool
from pytuflow._tmf.inp.inp_run_state import InputRunState


def model_files(tmp_path: Path) -> TCF:
    (tmp_path / "events.tef").write_text(
        "Define Event == Q10\n BC Event Source == _event_ | ten\nEnd Define\n"
        "Define Event == Q100\n BC Event Source == _event_ | hundred\nEnd Define\n"
    )
    (tmp_path / "geometry.tgc").write_text(
        "IF Scenario == DEV\n Read GIS Code == dev.shp\nELSE\n Read GIS Code == exg.shp\nEND IF\n"
        "Read Grid Zpts == terrain.tif\n"
    )
    (tmp_path / "boundary.tbc").write_text("Read GIS BC == boundary_<<Dir>>.shp\n")
    (tmp_path / "bc.csv").write_text("Name,Source,Column 1,Column 2\nflow,inflow__event_.csv,Time,Flow\n")
    top = tmp_path / "model.tcf"
    top.write_text(
        "Event File == events.tef\n"
        "Set Variable Dir == _event_\n"
        "Geometry Control File == geometry.tgc\n"
        "BC Database == bc.csv\n"
        "BC Control File == boundary.tbc\n"
    )
    return TCF(top)


def test_subtrees_match_ordinary_batch_and_share_across_unrelated_flags(tmp_path: Path) -> None:
    model = model_files(tmp_path)
    flags = [
        f"-s1 {scenario} -e1 {event} -e2 unused{i}"
        for i in range(3)
        for scenario in ("DEV", "EXG")
        for event in ("Q10", "Q100")
    ]
    expected = collect_fallback_dependencies(model, flags)
    actual = model.collect_file_dependencies(flags)
    assert expected.passed and actual.passed
    assert actual.fallback_runs == 0, actual.fallback_reason
    assert actual.runs == expected.runs
    assert actual.fragment_reuses > 0
    assert actual.expression_reuses > 0
    # References are shared objects even though per-run ordinal bindings differ.
    terrain = [
        next(ref for ref in run.file_references if ref.path_pattern.name == "terrain.tif") for run in actual.runs
    ]
    assert all(ref is terrain[0] for ref in terrain)
    assert {source.path_pattern.name for run in actual.runs for source in run.database_sources} == {
        "inflow_ten.csv",
        "inflow_hundred.csv",
    }


def test_invariant_subtree_avoids_initializers(tmp_path: Path) -> None:
    (tmp_path / "geometry.tgc").write_text("Read Grid Zpts == terrain.tif\nRead GIS Code == code.shp\n")
    top = tmp_path / "model.tcf"
    top.write_text("Geometry Control File == geometry.tgc\n")
    model = TCF(top)
    calls: list[str] = []
    original = InputRunState.__init__

    def observe(self: Any, *args: Any, **kwargs: Any) -> None:
        calls.append(args[0].lhs)
        original(self, *args, **kwargs)

    with patch.object(InputRunState, "__init__", observe):
        result = model.collect_file_dependencies([f"-e1 E{i}" for i in range(20)])
    assert result.passed
    assert len(calls) == 3
    assert result.fragment_reuses == 19


def test_failed_run_does_not_seed_fragments(tmp_path: Path) -> None:
    top = tmp_path / "model.tcf"
    top.write_text("Read Grid Zpts == terrain.tif\nIF Scenario == BAD\n PAUSE\nEND IF\n")
    model = TCF(top)
    result = model.collect_file_dependencies(["-s1 BAD", "-s1 GOOD"])
    assert result.runs[0].error
    assert result.runs[0].file_references == ()
    assert result.runs[1].error is None
    expected = collect_fallback_dependencies(model, ["-s1 GOOD"])
    assert result.runs[1].file_references == expected.runs[0].file_references


def test_no_physical_input_reads_after_parse(tmp_path: Path) -> None:
    model = model_files(tmp_path)
    with (
        patch.object(Path, "open", side_effect=AssertionError("open")),
        patch.object(Path, "stat", side_effect=AssertionError("stat")),
    ):
        result = model.collect_file_dependencies(["-s1 DEV -e1 Q10", "-s1 EXG -e1 Q100"])
    assert result.passed


@pytest.mark.parametrize("expression", ["rain_<<D>>_<<E>>.csv", "<<A>>", "<<~s~>>.shp", "plain.tif"])
def test_compiled_expression_matches_context(expression: str) -> None:
    pool = ExpressionPool()
    for variables in ({"D": "two", "E": "ten", "A": "<<D>>"}, {"D": "four", "E": "hundred", "A": "<<E>>"}):
        ctx = Context("-s1 DEV")
        ctx.load_variables(variables)
        assert pool.translate(ctx, expression) == ctx.translate(expression)


def test_event_cascade_and_transitive_variable_invalidation() -> None:
    pool = ExpressionPool()
    ctx = Context("-s1 DEV")
    ctx.load_variables({"A": "<<B>>", "B": "one"})
    ctx.event_variables = {"_X_": "<<A>>", "_Y_": "_X_"}
    for value in ("one", "two"):
        ctx.load_variables({"B": value})
        for expression in ("file__X_.csv", "file__Y_.csv", "<<A>>"):
            assert pool.translate(ctx, expression) == ctx.translate(expression)


def test_scoped_transitive_variables_and_flag_slots(tmp_path: Path) -> None:
    (tmp_path / "geometry.tgc").write_text(
        "Read GIS Code == <<Folder>>/<<~s2~>>.shp\nRead Grid Zpts == <<Alias>>.tif\n"
    )
    top = tmp_path / "model.tcf"
    top.write_text(
        "IF Scenario == DEV\n Set Variable Folder == dev\nELSE\n Set Variable Folder == exg\nEND IF\n"
        "Set Variable Alias == <<Folder>>\nGeometry Control File == geometry.tgc\n"
    )
    model = TCF(top)
    flags = ["-s1 DEV -s2 fine -e1 A", "-s1 DEV -s2 fine -e1 B", "-s1 EXG -s2 coarse -e1 A"]
    actual = model.collect_file_dependencies(flags)
    assert actual.passed
    assert actual.fallback_runs == 0
    assert actual.runs == collect_fallback_dependencies(model, flags).runs
    assert actual.runs[0].file_references == actual.runs[1].file_references
    assert actual.runs[0].file_references != actual.runs[2].file_references


def test_database_switches_keep_command_ordinals(tmp_path: Path) -> None:
    for name in ("first", "second"):
        (tmp_path / f"{name}.csv").write_text(f"Name,Source,Column 1,Column 2\nflow,{name}_flow.csv,Time,Flow\n")
    top = tmp_path / "model.tcf"
    top.write_text(
        "BC Database == first.csv\nRead GIS BC == first.shp\n"
        "IF Scenario == DEV\n BC Database == second.csv\nEND IF\nRead GIS BC == second.shp\n"
    )
    model = TCF(top)
    flags = ["-s1 EXG -e1 A", "-s1 DEV -e1 A", "-s1 DEV -e1 B"]
    actual = model.collect_file_dependencies(flags)
    assert actual.passed
    assert actual.runs == collect_fallback_dependencies(model, flags).runs
    assert len(actual.runs[0].database_activations) == 1
    assert len(actual.runs[1].database_activations) == 2


def test_new_invocation_does_not_reuse_previous_model_snapshot(tmp_path: Path) -> None:
    top = tmp_path / "model.tcf"
    top.write_text("Read Grid Zpts == first.tif\n")
    first = TCF(top).collect_file_dependencies(["-e1 A"])
    top.write_text("Read Grid Zpts == second.tif\n")
    second = TCF(top).collect_file_dependencies(["-e1 A"])
    assert first.runs[0].file_references[0].path_pattern.name == "first.tif"
    assert second.runs[0].file_references[0].path_pattern.name == "second.tif"


def test_empty_batch_rejected(tmp_path: Path) -> None:
    top = tmp_path / "model.tcf"
    top.write_text("Read Grid Zpts == terrain.tif\n")
    with pytest.raises(ValueError, match="At least one"):
        TCF(top).collect_file_dependencies([])


def test_custom_context_hook_uses_reported_fallback(tmp_path: Path) -> None:
    top = tmp_path / "model.tcf"
    top.write_text("Read Grid Zpts == terrain.tif\n")
    model = TCF(top)
    source: Any = model.inputs[0]
    original = source.context

    def custom(*args: Any, **kwargs: Any) -> Any:
        return original(*args, **kwargs)

    source.context = custom
    flags = ["-e1 A", "-e1 B"]
    actual = model.collect_file_dependencies(flags)
    assert actual.passed
    assert actual.fallback_runs == 2
    assert actual.fallback_reason == "Custom input context hook"
    assert actual.runs == collect_fallback_dependencies(model, flags).runs


def test_fallback_reuse_preserves_structured_flag_identity(tmp_path: Path) -> None:
    top = tmp_path / 'model.tcf'
    top.write_text('Read Grid Zpts == <<~s1~>>.tif\n')
    model = TCF(top)
    original = model.context
    model.context = lambda *args, **kwargs: original(*args, **kwargs)
    flags = [{'s1': 'A -s2 B'}, {'s1': 'A', 's2': 'B'}, '-s1 A -s2 B', {'s1': 'A -s2 B'}]
    fallback = collect_fallback_dependencies(model, flags)
    assert fallback.passed
    assert fallback.contexts_constructed == 3
    assert fallback.contexts_reused == 1
    assert len({run.flags for run in fallback.runs}) == 1
    assert [run.file_references[0].path_pattern.name for run in fallback.runs] == [
        'A -s2 B.tif', 'A.tif', 'A.tif', 'A -s2 B.tif',
    ]
    actual = model.collect_file_dependencies(flags)
    assert actual.fallback_runs == 4
    assert actual.runs == fallback.runs


def test_failed_database_projection_invalidates_entire_run(tmp_path: Path) -> None:
    (tmp_path / "bc.csv").write_text("Name,Source,Column 1,Column 2\nflow,<<MISSING>>.csv,Time,Flow\n")
    top = tmp_path / "model.tcf"
    top.write_text("Read Grid Zpts == terrain.tif\nBC Database == bc.csv\n")
    result = TCF(top).collect_file_dependencies(["-e1 A", "-e1 B"])
    assert not result.passed
    assert not result.fragments
    assert all(run.error and not run.file_references and not run.ordered_inputs for run in result.runs)


def test_bc_csv_columns_follow_transitive_events_without_reading_sources(tmp_path: Path) -> None:
    (tmp_path / "events.tef").write_text(
        "Define Event == A\n BC Event Source == _col_ | <<Choice>>\nEnd Define\n"
        "Define Event == B\n BC Event Source == _col_ | Other\nEnd Define\n"
    )
    (tmp_path / "bc.csv").write_text("Name,Source,Column 1,Column 2\nrain,rain.csv,Time,_col_\n")
    top = tmp_path / "model.tcf"
    top.write_text("Event File == events.tef\nSet Variable Choice == Selected\nBC Database == bc.csv\n")
    model = TCF(top)
    flags = ["-e1 A", "-e1 B", "-e1 A"]
    with patch.object(Path, "open", side_effect=AssertionError("Opened a source CSV")):
        expected = collect_fallback_dependencies(model, flags)
        result = model.collect_file_dependencies(flags)
    assert result.passed
    assert result.runs == expected.runs
    assert [run.database_sources[0].csv_columns for run in result.runs] == [
        ("Time", "Selected"),
        ("Time", "Other"),
        ("Time", "Selected"),
    ]
    assert result.fragment_reuses > 0


def test_bc_fews_csv_does_not_claim_ordinary_header_selectors(tmp_path: Path) -> None:
    (tmp_path / "bc.csv").write_text("Name,Source,Column 1,Column 2\nrain,FEWS | rain.csv,Time,Rain\n")
    top = tmp_path / "model.tcf"
    top.write_text("BC Database == bc.csv\n")
    result = TCF(top).collect_file_dependencies(["-e1 A"])
    assert result.passed
    assert result.runs[0].database_sources[0].csv_columns == ()


def test_tef_token_exposed_by_second_variable_pass_invalidates_fragment(tmp_path: Path) -> None:
    """A late _EVENT_ token must not reuse another event's file reference."""
    (tmp_path / "events.tef").write_text(
        "Define Event == A\n BC Event Source == _EVENT_ | first\nEnd Define\n"
        "Define Event == B\n BC Event Source == _EVENT_ | second\nEnd Define\n",
        encoding="utf-8",
    )
    top = tmp_path / "model.tcf"
    top.write_text(
        "Event File == events.tef\nSet Variable A == <<B>>\nSet Variable B == _EVENT_\nRead GIS Code == <<A>>.shp\n",
        encoding="utf-8",
    )
    model = TCF(top)
    flags = ["-e1 A", "-e1 B", "-e1 A"]
    expected = collect_fallback_dependencies(model, flags)
    actual = model.collect_file_dependencies(flags)
    assert expected.passed and actual.passed
    assert actual.fallback_runs == 0, actual.fallback_reason
    assert actual.runs == expected.runs
    assert actual.runs[0].file_references == actual.runs[2].file_references
    assert actual.runs[0].file_references != actual.runs[1].file_references
    names = [{ref.path_pattern.name for ref in run.file_references} for run in actual.runs]
    assert "first.shp" in names[0]
    assert "second.shp" in names[1]
    assert "first.shp" in names[2]


def test_custom_included_control_file_context_hook_falls_back(tmp_path: Path) -> None:
    model = model_files(tmp_path)
    include: Any = model.find_input(lhs="geometry control file")[0]
    child: Any = include.cf[0]

    def deny_context(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Custom child context rejected the run")

    child.context = deny_context
    flags = ["-s1 DEV -e1 Q10", "-s1 EXG -e1 Q100"]
    expected = collect_fallback_dependencies(model, flags)
    actual = model.collect_file_dependencies(flags)
    assert not expected.passed and not actual.passed
    assert actual.runs == expected.runs
    assert actual.fallback_runs == len(flags)
    assert actual.fallback_reason == "Custom included control file context hook"
    assert all("Custom child context" in (run.error or "") for run in actual.runs)


def test_custom_control_file_class_hook_falls_back(tmp_path: Path) -> None:
    model = model_files(tmp_path)
    include: Any = model.find_input(lhs="geometry control file")[0]
    child: Any = include.cf[0]
    ordinary_class = type(child)

    def deny_context(self: Any, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Custom control file class context")

    # Creating a class-level override also bypasses the inherited base
    # method. Snapshot only originally trusted class implementations.
    with patch.object(ordinary_class, "context", deny_context):
        flags = ["-s1 DEV -e1 Q10"]
        expected = collect_fallback_dependencies(model, flags)
        actual = model.collect_file_dependencies(flags)
    assert not expected.passed and not actual.passed
    assert actual.runs == expected.runs
    assert actual.fallback_runs == 1
    assert actual.fallback_reason == "Custom included control file context hook"


def test_custom_root_model_context_hook_falls_back(tmp_path: Path) -> None:
    model = model_files(tmp_path)

    def deny_context(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("Custom root model context")

    root: Any = model
    root.context = deny_context
    flags = ["-s1 DEV -e1 Q10"]
    expected = collect_fallback_dependencies(model, flags)
    actual = model.collect_file_dependencies(flags)
    assert not expected.passed and not actual.passed
    assert actual.runs == expected.runs
    assert actual.fallback_runs == 1
    assert actual.fallback_reason == "Custom model control file context hook"


def test_tef_only_chained_event_substitutions_invalidate_fragments(tmp_path: Path) -> None:
    """A later TEF pass must not reuse a dependency for a different event."""
    (tmp_path / "events.tef").write_text(
        "Define Event == A\n"
        " BC Event Source == _y_ | first\n"
        " BC Event Source == _x_ | _Y_\n"
        "End Define\n"
        "Define Event == B\n"
        " BC Event Source == _y_ | second\n"
        " BC Event Source == _x_ | _Y_\n"
        "End Define\n",
        encoding="utf-8",
    )
    top = tmp_path / "model.tcf"
    top.write_text(
        "Event File == events.tef\nRead GIS Code == _x_.shp\n",
        encoding="utf-8",
    )
    model = TCF(top)
    flags = ["-e1 A", "-e1 B", "-e1 A"]
    # An independent, unoptimised run is the semantic oracle here. The
    # original evaluator must not preserve event A's
    # constructor expansion when event B has the same first-pass text.
    baseline = collect_fallback_dependencies(model, flags)
    expected = collect_fallback_dependencies(model, flags)
    actual = model.collect_file_dependencies(flags)
    assert baseline.passed and expected.passed and actual.passed
    assert expected.runs == baseline.runs
    assert actual.fallback_runs == 0, actual.fallback_reason
    assert actual.runs == expected.runs
    names = [{ref.path_pattern.name for ref in run.file_references} for run in actual.runs]
    assert "first.shp" in names[0]
    assert "second.shp" in names[1]
    assert "first.shp" in names[2]


def test_join_reuses_zero_offset_records_and_rebases_later_fragments(tmp_path: Path) -> None:
    """Avoid copying frozen first records but preserve all later public ordinals."""
    from pytuflow._tmf.dependency_records import BatchInputCommand, BatchInputReference
    from pytuflow._tmf.file_reference import DeferredDatabaseActivation, FileReference
    from pytuflow._tmf.fragment_dependencies import DependencyFragment, _join

    def fragment(label: str) -> DependencyFragment:
        path = tmp_path / f"{label}.csv"
        ref = FileReference(path.parent, path.name, path, None, label, False, False, False, False)
        command = BatchInputCommand(
            label, 0, tmp_path / "model.tcf", 1, "BC Database", f"BC Database == {label}.csv", 1
        )
        reference = BatchInputReference(label, 0, command.owner_control_file, 1, ref)
        activation = DeferredDatabaseActivation(0, label, "bc", path, "BC Database", command.owner_control_file, 1)
        return DependencyFragment((command,), (reference,), (), (activation,))

    first = fragment("first")
    second = fragment("second")
    output = _join((first, second))
    assert len(output.commands) == len(output.references) == len(output.activations) == 2
    assert output.commands[0] is first.commands[0]
    assert output.references[0] is first.references[0]
    assert output.activations[0] is first.activations[0]
    assert output.commands[1].command_index == 1
    assert output.references[1].command_index == 1
    assert output.activations[1].sequence == 1
    assert output.commands[1].input_uuid == second.commands[0].input_uuid
    assert output.references[1].reference is second.references[0].reference
    assert second.commands[0].command_index == 0
    assert second.references[0].command_index == 0
    assert second.activations[0].sequence == 0

    # One already-offset-correct immutable subtree needs no new records.
    single = _join((first,))
    assert single == first
    assert single.commands[0] is first.commands[0]
    assert single.references[0] is first.references[0]
    assert single.activations[0] is first.activations[0]


def test_fragment_context_memo_reuses_translations_and_invalidates_on_variables() -> None:
    """Within-run reuse must not alias values after an approved variable change."""
    from pytuflow._tmf.fragment_dependencies import ExpressionPool, _FragmentContext
    from pytuflow._tmf.settings import TCFConfig

    pool = ExpressionPool()
    ctx = _FragmentContext("-s1 DEV", TCFConfig(), pool)
    ctx.load_variables({"A": "first"})
    expression = "input_<<A>>.csv"
    assert ctx.translate(expression) == "input_first.csv"
    before = pool.evaluations + pool.reuses
    assert ctx.translate(expression) == "input_first.csv"
    assert pool.evaluations + pool.reuses == before
    assert ctx.translation_hits >= 1

    ctx.load_variables({"A": "second"})
    assert ctx.translate(expression) == "input_second.csv"
    assert pool.evaluations + pool.reuses == before + 1
    assert ctx.translate(expression) == "input_second.csv"
    assert pool.evaluations + pool.reuses == before + 1


def test_subtree_signature_parts_are_reused_per_run_and_invalidated(tmp_path: Path) -> None:
    """A shared expression is evaluated once per context, not once per parent."""
    from pytuflow._tmf.cf.cf_run_state import prepare_run_context
    from pytuflow._tmf.fragment_dependencies import _FragmentContext, _Plan

    model = model_files(tmp_path)
    plan = _Plan(model)
    ctx = _FragmentContext("-s1 DEV -e1 Q10", model.config, plan.expressions)
    ctx._batch_variable_assignments = plan.assignments
    prepare_run_context(model, ctx)
    boundary = next(inp for inp in plan.roots if str(inp.lhs).casefold() == "bc control file")

    with patch.object(ctx, "translate", wraps=ctx.translate) as translated:
        first = plan._key(boundary, ctx)
        first_calls = translated.call_count
        assert first_calls > 0
        assert ctx._fragment_signature_values
        assert plan._key(boundary, ctx) == first
        assert translated.call_count == first_calls

        ctx.load_variables({"Dir": "different"})
        assert not ctx._fragment_signature_values
        second = plan._key(boundary, ctx)
        assert second != first
        assert translated.call_count > first_calls

    # Context rejects redefining an existing flag slot. Remove the old event
    # binding before loading its replacement, retaining the scenario slot.
    delattr(ctx, "E1")
    legacy_context: Any = ctx  # Context exposes untyped mutable binding maps.
    legacy_context.var_map.pop("E1")
    legacy_context.event_variables.clear()
    legacy_context.load_context_from_dict({"e1": "Q100"})
    assert not ctx._fragment_signature_values
    ctx.load_variables({"Dir": "_event_"})
    third = plan._key(boundary, ctx)
    assert third != first
    assert third != second
