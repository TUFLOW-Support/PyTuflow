"""Regression contracts for inactive conditional inputs in fragment batches.

All paths and flags here are synthetic; no solver or external model is needed.
Compare the normal collector with a controlled variant that also computes
cache keys for inactive commands, while preserving complete run records.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pytuflow import TCF
from pytuflow._tmf.cf.cf_run_state import prepare_run_context
from pytuflow._tmf.deferred_dependency_fallback import collect_fallback_dependencies
from pytuflow._tmf.fragment_dependencies import _FragmentContext, _Plan


def _four_path_parity(model: TCF, flags: list[str]) -> None:
    """Compare complete run records, not just resolved file paths."""
    reference = collect_fallback_dependencies(model, flags)
    optimized = model.collect_file_dependencies(flags)

    original = _Plan.evaluate

    def form_inactive_key_first(plan: _Plan, inp: Any, ctx: Any) -> Any:
        # Emulate the alternative key work on excluded inputs; the actual
        # evaluator still owns selection, construction and error semantics.
        if not ctx.in_context_by_scope(inp.scope):
            plan._key(inp, ctx)
        return original(plan, inp, ctx)

    with patch.object(_Plan, "evaluate", form_inactive_key_first):
        inactive_key_variant = model.collect_file_dependencies(flags)

    assert reference.runs == inactive_key_variant.runs == optimized.runs
    assert optimized.fallback_runs == inactive_key_variant.fallback_runs == 0


def test_fourteen_var_cell_size_declarations_skip_thirteen_keys(tmp_path: Path) -> None:
    """The -s4 scenario selects one of fourteen mutually exclusive values."""
    scenarios = [(f"{number:02d}M", str(number)) for number in range(1, 14)]
    scenarios.append(("32M", "32"))
    lines = []
    for index, (scenario, value) in enumerate(scenarios):
        lines.append(f"{'If' if index == 0 else 'Else If'} Scenario == {scenario}")
        lines.append(f" Set Variable VarCellSize == {value}")
    lines.extend((
        "End If",
        "Cell Size == <<VarCellSize>>",
        "Read GIS Code == code_<<VarCellSize>>.shp",
    ))
    top = tmp_path / "model.tcf"
    top.write_text("\n".join((*lines, "")), encoding="utf-8")
    model = TCF(top)
    flags = ["-s1 BASE -s4 32M -e1 A", "-s1 BASE -s4 03M -e1 B", "-s1 BASE -s4 32M -e1 C"]
    _four_path_parity(model, flags)

    result = model.collect_file_dependencies(flags)
    assert result.passed
    assert [
        next(ref.path_pattern.name for ref in run.file_references if ref.path_pattern.suffix == ".shp")
        for run in result.runs
    ] == ["code_32.shp", "code_3.shp", "code_32.shp"]

    plan = _Plan(model)
    declarations = {id(inp): str(value) for inp, (_, value) in plan.assignments}
    assert len(declarations) == 14
    key_calls: Counter[int] = Counter()
    original_key = _Plan._key
    translations: list[tuple[str, str]] = []
    original_translate = _FragmentContext.translate

    def record_key(self: _Plan, inp: Any, ctx: Any) -> Any:
        key_calls[id(inp)] += 1
        return original_key(self, inp, ctx)

    def record_translate(self: _FragmentContext, value: Any) -> Any:
        if isinstance(value, str):
            translations.append((str(self.var_map.get("VARCELLSIZE")), value))
        return original_translate(self, value)

    with (
        patch.object(_Plan, "_key", record_key),
        patch.object(_FragmentContext, "translate", record_translate),
    ):
        for flag, expected in zip(flags, ("32", "3", "32"), strict=True):
            ctx = _FragmentContext(flag, model.config, plan.expressions)
            ctx._batch_variable_assignments = plan.assignments
            prepare_run_context(model, ctx)
            assert str(ctx.translate("<<VarCellSize>>")) == expected
            assert sum(
                ctx.in_context_by_scope(inp.scope) for inp, _ in plan.assignments
            ) == 1
            # Preparation has already cached each declaration's scope decision.
            assert all(id(inp.scope) in ctx._batch_scope_decisions for inp, _ in plan.assignments)
            for root in plan.roots:
                plan.evaluate(root, ctx)
            plan.cache.update(plan.pending)
            plan.pending.clear()

    # All three selected declarations are keyed once. The other 39
    # declaration-context pairs are excluded before any full key construction.
    assert sum(key_calls[id(inp)] for inp, _ in plan.assignments) == len(flags)
    assert key_calls[next(id(inp) for inp, (_, value) in plan.assignments if value == "32")] == 2
    for expected in ("32", "3"):
        inactive_rhs = {value for value in declarations.values() if value != expected}
        assert not any(
            selected == expected and translated in inactive_rhs
            for selected, translated in translations
        )


def test_nested_scenario_event_else_and_inactive_includes(tmp_path: Path) -> None:
    """Inactive includes and descendants do not form keys or emit references."""
    (tmp_path / "dev.tgc").write_text(
        "If Event == A\n"
        " Read GIS Code == event_a.shp\n"
        " Else If Event == B\n"
        " Read GIS Code == event_b.shp\n"
        " Else\n"
        " Read GIS Code == event_other.shp\n"
        " End If\n"
        " SGS Max Sample Frequency == 1\n",
        encoding="utf-8",
    )
    (tmp_path / "exg.tgc").write_text(
        "Read Grid Zpts == existing.tif\n"
        "End Time == 1440\n",
        encoding="utf-8",
    )
    top = tmp_path / "model.tcf"
    top.write_text(
        "If Scenario == DEV\n"
        " Geometry Control File == dev.tgc\n"
        "Else\n"
        " Geometry Control File == exg.tgc\n"
        "End If\n"
        "Start Time == 0\n",
        encoding="utf-8",
    )
    model = TCF(top)
    flags = [
        "-s1 DEV -e1 A",
        "-s1 DEV -e1 B",
        "-s1 DEV -e1 UNKNOWN",
        "-s1 EXG -e1 A",
        "-s1 DEV -e1 A",
    ]
    _four_path_parity(model, flags)

    plan = _Plan(model)
    original_key = _Plan._key
    keyed: Counter[int] = Counter()

    def record_key(self: _Plan, inp: Any, ctx: Any) -> Any:
        keyed[id(inp)] += 1
        return original_key(self, inp, ctx)

    with patch.object(_Plan, "_key", record_key):
        result = model.collect_file_dependencies(flags)

    assert result.passed
    assert result.runs[0].file_references == result.runs[4].file_references
    assert result.runs[0].ordered_inputs == result.runs[4].ordered_inputs
    names = [
        {ref.path_pattern.name for ref in run.file_references}
        for run in result.runs
    ]
    assert names == [
        {"dev.tgc", "event_a.shp"},
        {"dev.tgc", "event_b.shp"},
        {"dev.tgc", "event_other.shp"},
        {"exg.tgc", "existing.tif"},
        {"dev.tgc", "event_a.shp"},
    ]
    # The excluded control-file input is never keyed in that context, and
    # its children are not visited while the alternate branch is selected.
    exg = next(inp for inp in plan.roots if str(inp.rhs).strip() == "exg.tgc")
    assert keyed[id(exg)] == 1


def test_overlapping_variable_declarations_database_and_failed_run(tmp_path: Path) -> None:
    """Last applicable assignment wins; excluded errors and BCs stay excluded."""
    for name in ("base", "dev"):
        (tmp_path / f"{name}.csv").write_text(
            f"Name,Source,Column 1,Column 2\nflow,{name}.csv,Time,Flow\n",
            encoding="utf-8",
        )
    top = tmp_path / "model.tcf"
    top.write_text(
        "Set Variable Choice == base\n"
        "BC Database == base.csv\n"
        "If Scenario == DEV\n"
        " Set Variable Choice == dev\n"
        " BC Database == dev.csv\n"
        " If Event == ERROR\n"
        "  PAUSE\n"
        " End If\n"
        "End If\n"
        "Read GIS BC == <<Choice>>.shp\n",
        encoding="utf-8",
    )
    model = TCF(top)
    flags = [
        "-s1 EXG -e1 A",
        "-s1 DEV -e1 A",
        "-s1 DEV -e1 ERROR",
        "-s1 EXG -e1 B",
        "-s1 DEV -e1 A",
    ]
    _four_path_parity(model, flags)
    result = model.collect_file_dependencies(flags)
    assert result.runs[2].error and "Pause" in result.runs[2].error
    assert not result.runs[2].ordered_inputs
    assert not result.runs[2].file_references
    assert len(result.runs[0].database_activations) == 1
    assert len(result.runs[1].database_activations) == 2
    assert result.runs[0].file_references[-1].path_pattern.name == "base.shp"
    assert result.runs[1].file_references[-1].path_pattern.name == "dev.shp"
    assert result.runs[4].error is None


def test_custom_hook_in_inactive_branch_uses_ordinary_fallback(tmp_path: Path) -> None:
    top = tmp_path / "model.tcf"
    top.write_text(
        "If Scenario == ACTIVE\n"
        " Read Grid Zpts == active.tif\n"
        "Else\n"
        " Read Grid Zpts == other.tif\n"
        "End If\n",
        encoding="utf-8",
    )
    model = TCF(top)
    other: Any = next(inp for inp in model.inputs if str(inp.rhs).strip() == "other.tif")
    original = other.context

    def custom(*args: Any, **kwargs: Any) -> Any:
        return original(*args, **kwargs)

    other.context = custom
    flags = ["-s1 ACTIVE"]
    result = model.collect_file_dependencies(flags)
    ordinary = collect_fallback_dependencies(model, flags)
    assert result.runs == ordinary.runs
    assert result.fallback_runs == len(flags)
    assert result.fallback_reason == "Custom input context hook"
