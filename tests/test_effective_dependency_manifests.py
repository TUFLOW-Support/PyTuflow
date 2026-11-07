"""Complete-record selection contracts for variable-dependent includes."""

from __future__ import annotations

from pathlib import Path

import pytest

from pytuflow import TCF
from pytuflow._tmf.deferred_dependency_fallback import collect_fallback_dependencies


def assert_parity(model: TCF, flags: list[str | dict[str, str]]):
    reference = collect_fallback_dependencies(model, flags)
    fragments = model.collect_file_dependencies(flags)
    assert reference.runs == fragments.runs
    return fragments


@pytest.mark.parametrize(
    "command,suffix",
    [
        ("Geometry Control File", "tgc"),
        ("BC Control File", "tbc"),
        ("Geometry Control File", "trd"),
        ("Event File", "tef"),
        ("ESTRY Control File", "ecf"),
        ("Geometry Control File", "tscf"),
    ],
)
@pytest.mark.parametrize(
    "filename,assignments,slot",
    [
        ("<<~s1~>>", "", "s1"),
        ("<<~e1~>>", "", "e1"),
        (
            "<<Alias>>",
            "Set Variable Alias == <<Next>>\nSet Variable Next == <<~s1~>>\n",
            "s1",
        ),
    ],
)
def test_selected_source_identity(
    tmp_path: Path,
    command: str,
    suffix: str,
    filename: str,
    assignments: str,
    slot: str,
) -> None:
    for name in ("EXG", "DEV"):
        (tmp_path / f"design_{name}_03.{suffix}").write_text(
            f"Read GIS Code == {name}.shp\n"
        )
    top = tmp_path / "model.tcf"
    top.write_text(
        assignments
        + "Set Variable VarCellSize == 32\n"
        + f"{command} == design_{filename}_03.{suffix}\n"
    )
    model = TCF(top)
    result = assert_parity(
        model,
        [f"-{slot} EXG -e2 rain1", f"-{slot} DEV -e2 rain2", f"-{slot} EXG -e2 rain3"],
    )
    assert result.passed
    for run, name in zip(result.runs, ("EXG", "DEV", "EXG"), strict=True):
        names = [ref.path_pattern.name for ref in run.file_references]
        assert f"design_{name}_03.{suffix}" in names
        assert f"{name}.shp" in names
    assert result.fragment_reuses > 0


def test_nested_variable_selected_files(tmp_path: Path) -> None:
    for name in ("EXG", "DEV"):
        (tmp_path / f"nested_{name}.trd").write_text(f"Read GIS Code == {name}.shp\n")
    (tmp_path / "geometry.tgc").write_text(
        "Geometry Control File == nested_<<~s1~>>.trd\n"
    )
    top = tmp_path / "model.tcf"
    top.write_text("Geometry Control File == geometry.tgc\n")
    result = assert_parity(TCF(top), ["-s1 EXG", "-s1 DEV", "-s1 EXG"])
    assert result.passed
    assert [run.file_references[-1].path_pattern.name for run in result.runs] == [
        "EXG.shp",
        "DEV.shp",
        "EXG.shp",
    ]


def test_missing_selected_file_does_not_reuse_prior_result(tmp_path: Path) -> None:
    (tmp_path / "design_EXG.tgc").write_text("Read GIS Code == EXG.shp\n")
    top = tmp_path / "model.tcf"
    top.write_text("Geometry Control File == design_<<~s1~>>.tgc\n")
    model = TCF(top)
    result = assert_parity(model, ["-s1 EXG", "-s1 MISSING", "-s1 EXG"])
    assert result.runs[0].error is None
    assert result.runs[1].error
    assert result.runs[2].error is None
    assert not result.runs[1].ordered_inputs


def test_wildcard_include_preserves_all_matched_sources_and_order(
    tmp_path: Path,
) -> None:
    for name in ("first", "second"):
        (tmp_path / f"geometry_{name}.tgc").write_text(f"Read GIS Code == {name}.shp\n")
    top = tmp_path / "model.tcf"
    top.write_text("Geometry Control File == geometry_*.tgc\n")
    result = assert_parity(TCF(top), ["-e1 A", "-e1 B"])
    assert result.passed
    assert {ref.path_pattern.name for ref in result.runs[0].file_references} >= {
        "first.shp",
        "second.shp",
    }
    assert result.runs[0].ordered_inputs == result.runs[1].ordered_inputs


def test_selected_child_has_its_own_dependency_manifest(tmp_path: Path) -> None:
    from pytuflow._tmf.fragment_dependencies import _Plan

    (tmp_path / "design_EXG.tgc").write_text("Read GIS Code == fixed.shp\n")
    (tmp_path / "design_DEV.tgc").write_text("Read GIS Code == <<~e1~>>.shp\n")
    top = tmp_path / "model.tcf"
    top.write_text("Geometry Control File == design_<<~s1~>>.tgc\n")
    model = TCF(top)
    plan = _Plan(model)
    manifests = {
        Path(child.fpath).stem: plan.file_manifests[id(child)]
        for child in plan.children[id(model.inputs[0])]
    }
    assert manifests["design_EXG"].variables == ()
    assert manifests["design_DEV"].variables == ("E1",)
    result = assert_parity(model, ["-s1 EXG -e1 A", "-s1 EXG -e1 B", "-s1 DEV -e1 B"])
    assert result.passed
    assert result.fragment_reuses > 0


def test_assembled_event_token_uses_full_key(tmp_path: Path) -> None:
    from pytuflow._tmf.cf.cf_run_state import prepare_run_context
    from pytuflow._tmf.fragment_dependencies import _FragmentContext, _Plan

    (tmp_path / "events.tef").write_text(
        "Define Event == A\n BC Event Source == _rain_ | first\nEnd Define\n"
        "Define Event == B\n BC Event Source == _rain_ | second\nEnd Define\n"
    )
    top = tmp_path / "model.tcf"
    top.write_text(
        "Event File == events.tef\nSet Variable Part == ain\nRead GIS Code == _r<<Part>>_.shp\n"
    )
    model = TCF(top)
    result = assert_parity(model, ["-e1 A", "-e1 B", "-e1 A"])
    assert result.passed
    assert [r.file_references[-1].path_pattern.name for r in result.runs] == [
        "first.shp",
        "second.shp",
        "first.shp",
    ]
    plan = _Plan(model)
    ctx = _FragmentContext("-e1 A", model.config, plan.expressions, plan.scope_program)
    ctx._batch_variable_assignments = plan.assignments
    prepare_run_context(model, ctx)
    plan._key(model.inputs[-1], ctx)
    assert plan.manifest_fallbacks["event-substitution"]


@pytest.mark.parametrize("with_event_database", [False, True])
def test_substitutions_assembling_new_flag_token_reject_compact_key(
    tmp_path: Path, with_event_database: bool
) -> None:
    """Late <<~s1~>> assembled from variables must not alias distinct files."""
    from pytuflow._tmf.cf.cf_run_state import prepare_run_context
    from pytuflow._tmf.fragment_dependencies import _FragmentContext, _Plan

    event_line = ""
    if with_event_database:
        (tmp_path / "events.tef").write_text(
            "Define Event == W\n BC Event Source == _unrelated_ | constant\nEnd Define\n",
            encoding="utf-8",
        )
        event_line = "Event File == events.tef\n"
    top = tmp_path / "model.tcf"
    top.write_text(
        event_line
        + "Set Variable Left == <\n"
        + "Set Variable Right == >\n"
        + "Read GIS Code == generated_<<Left>><~s1~><<Right>>.shp\n",
        encoding="utf-8",
    )
    model = TCF(top)
    flags = ["-s1 A -e1 W", "-s1 B -e1 W", "-s1 A -e1 W"]
    result = assert_parity(model, flags)
    assert result.passed
    assert [run.file_references[-1].path_pattern.name for run in result.runs] == [
        "generated_A.shp",
        "generated_B.shp",
        "generated_A.shp",
    ]
    plan = _Plan(model)
    inp = model.inputs[-1]
    manifest = plan.manifests[id(inp)]
    assert manifest.variables == ("LEFT", "RIGHT")
    for flag in flags[:2]:
        ctx = _FragmentContext(
            flag, model.config, plan.expressions, plan.scope_program
        )
        ctx._batch_variable_assignments = plan.assignments
        prepare_run_context(model, ctx)
        assert not manifest.event_independent(ctx)
        assert plan._key(inp, ctx)[1][0] != "manifest"
    assert plan.manifest_fallbacks.get("event-substitution", 0) >= 2


def test_selected_tgc_does_not_hide_late_child_scenario_dependency(
    tmp_path: Path,
) -> None:
    """Same selected TGC and cell size must not mask assembled flag-dependent GIS."""
    for selected in ("EXG", "DEV"):
        (tmp_path / f"design_{selected}_03.tgc").write_text(
            "Read GIS Code == child_<<Left>><~s1~><<Right>>.shp\n",
            encoding="utf-8",
        )
    top = tmp_path / "model.tcf"
    top.write_text(
        "Set Variable Left == <\n"
        "Set Variable Right == >\n"
        "Set Variable VarCellSize == 32\n"
        "Geometry Control File == design_<<~s2~>>_03.tgc\n",
        encoding="utf-8",
    )
    result = assert_parity(
        TCF(top),
        [
            "-s2 EXG -s1 A",
            "-s2 EXG -s1 B",
            "-s2 DEV -s1 B",
            "-s2 EXG -s1 A",
        ],
    )
    assert result.passed
    assert [run.file_references[-1].path_pattern.name for run in result.runs] == [
        "child_A.shp",
        "child_B.shp",
        "child_B.shp",
        "child_A.shp",
    ]
    assert [run.file_references[0].path_pattern.name for run in result.runs] == [
        "design_EXG_03.tgc",
        "design_EXG_03.tgc",
        "design_DEV_03.tgc",
        "design_EXG_03.tgc",
    ]


def test_fragment_expression_pool_handles_assembled_flag_token_without_tef() -> None:
    """Expression reuse must not alias A/B/A when bindings assemble a new token."""
    from pytuflow._tmf.context import Context
    from pytuflow._tmf.fragment_dependencies import ExpressionPool

    pool = ExpressionPool()
    expression = "generated_<<Left>><~s1~><<Right>>.shp"
    for scenario, expected in (("A", "generated_A.shp"), ("B", "generated_B.shp"),
                               ("A", "generated_A.shp")):
        context = Context(f"-s1 {scenario}")
        context.load_variables({"Left": "<", "Right": ">"})
        assert pool.translate(context, expression) == expected
        assert pool.translate(context, expression) == context.translate(expression)
    assert pool.evaluations == 2
    assert pool.reuses == 4


def test_fragment_expression_pool_uses_context_for_literal_bracket_fragments() -> None:
    """Malformed/partial original tokens must never take the one-pass shortcut."""
    from pytuflow._tmf.context import Context
    from pytuflow._tmf.fragment_dependencies import ExpressionPool

    pool = ExpressionPool()
    expression = "source_<<<<Alias>>>>.shp"
    for scenario in ("A", "B", "A"):
        context = Context(f"-s1 {scenario}")
        context.load_variables({"Alias": "~s1~"})
        assert pool.translate(context, expression) == context.translate(expression)
    # Source-literal bracket pieces require a conservative context-dependent key.
    assert pool.evaluations == 2
    assert pool.reuses == 1


def test_known_transitive_flag_dependency_remains_compact(tmp_path: Path) -> None:
    """The fix must not disable proofs for normally declared transitive tokens."""
    from pytuflow._tmf.cf.cf_run_state import prepare_run_context
    from pytuflow._tmf.fragment_dependencies import _FragmentContext, _Plan

    top = tmp_path / "model.tcf"
    top.write_text(
        "Set Variable Alias == <<~s1~>>\nRead GIS Code == <<Alias>>.shp\n",
        encoding="utf-8",
    )
    model = TCF(top)
    plan = _Plan(model)
    inp = model.inputs[-1]
    assert plan.manifests[id(inp)].variables == ("ALIAS", "S1")
    for flag in ("-s1 A", "-s1 B"):
        ctx = _FragmentContext(
            flag, model.config, plan.expressions, plan.scope_program
        )
        ctx._batch_variable_assignments = plan.assignments
        prepare_run_context(model, ctx)
        assert plan._key(inp, ctx)[1][0] == "manifest"
    assert_parity(model, ["-s1 A", "-s1 B", "-s1 A"])


def test_unknown_and_cyclic_lineage_use_full_key(tmp_path: Path) -> None:
    from pytuflow._tmf.fragment_dependencies import _Plan

    top = tmp_path / "model.tcf"
    top.write_text(
        "Set Variable A == <<B>>\nSet Variable B == <<A>>\nRead GIS Code == <<A>>.shp\n"
    )
    model = TCF(top)
    plan = _Plan(model)
    assert plan.manifests[id(model.inputs[-1])].fallback_reason == "cyclic-variable"
    result = assert_parity(model, ["-e1 A", "-e1 B"])
    assert not result.passed


def test_case_spelling_uses_the_existing_path_policy(tmp_path: Path) -> None:
    (tmp_path / "design_EXG.tgc").write_text("Read GIS Code == EXG.shp\n")
    top = tmp_path / "model.tcf"
    top.write_text("Geometry Control File == design_<<~s1~>>.tgc\n")
    # A nonexact include spelling requires -cs2; the default Linux
    # -cs0 policy must not silently select a differently cased file.
    result = assert_parity(TCF(top, case_sensitivity=2),
                           ["-s1 EXG", "-s1 exg", "-s1 EXG"])
    assert result.passed
    assert [r.file_references[0].path_pattern.name for r in result.runs] == [
        "design_EXG.tgc",
        "design_exg.tgc",
        "design_EXG.tgc",
    ]


def test_dynamic_inline_read_file_uses_explicit_fallback(tmp_path: Path) -> None:
    for name in ("EXG", "DEV"):
        (tmp_path / f"design_{name}.trd").write_text(f"Read GIS Code == {name}.shp\n")
    top = tmp_path / "model.tcf"
    top.write_text("Read File == design_<<~s1~>>.trd\n")
    result = assert_parity(TCF(top), ["-s1 EXG", "-s1 DEV"])
    assert result.fallback_runs == 2
    assert (
        result.fallback_reason
        == "Dynamic inline Read File requires the ordinary evaluator"
    )


def test_independent_optimisations_and_parent_full_key_have_complete_parity(
    tmp_path: Path,
) -> None:
    from typing import Any
    from unittest.mock import patch

    from pytuflow._tmf.fragment_dependencies import _Plan
    from tests.test_fragment_dependencies import model_files

    model = model_files(tmp_path)
    flags = ["-s1 DEV -e1 Q10", "-s1 EXG -e1 Q100", "-s1 DEV -e1 Q10"]
    expected = assert_parity(model, flags).runs
    original = _Plan.__init__
    for scopes, manifests in (
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ):

        def configure(
            self: Any,
            source: Any,
            use_scopes: bool = scopes,
            use_manifests: bool = manifests,
        ) -> None:
            original(self, source, use_scopes=use_scopes, use_manifests=use_manifests)

        with patch.object(_Plan, "__init__", configure):
            assert model.collect_file_dependencies(flags).runs == expected


def test_different_selected_files_with_identical_contents_keep_uuid_provenance(
    tmp_path: Path,
) -> None:
    for name in ("EXG", "DEV"):
        (tmp_path / f"design_{name}.tgc").write_text(
            "Read GIS Code == same.gpkg >> codes\n"
        )
    top = tmp_path / "model.tcf"
    top.write_text(
        "Set Variable VarCellSize == 32\nGeometry Control File == design_<<~s1~>>.tgc\n"
    )
    result = assert_parity(TCF(top), ["-s1 EXG", "-s1 DEV", "-s1 EXG"])
    assert result.passed
    uuids = [run.ordered_inputs[-1].input_uuid for run in result.runs]
    assert uuids[0] != uuids[1]
    assert uuids[0] == uuids[2]


def test_ambiguous_cached_source_retains_ordinary_error(tmp_path: Path) -> None:
    from typing import Any

    (tmp_path / "geometry.tgc").write_text("Read GIS Code == code.shp\n")
    top = tmp_path / "model.tcf"
    top.write_text("Geometry Control File == geometry.tgc\n")
    model = TCF(top)
    include: Any = model.inputs[0]
    include.cf.append(include.cf[0])
    include._cf_loaded_paths.append(include._cf_loaded_paths[0])
    result = assert_parity(model, ["-e1 A", "-e1 B"])
    assert not result.passed
    assert all("Ambiguous cached child" in (run.error or "") for run in result.runs)


def test_changed_parsed_model_gets_fresh_manifests(tmp_path: Path) -> None:
    (tmp_path / "geometry.tgc").write_text("Read GIS Code == first.shp\n")
    top = tmp_path / "model.tcf"
    top.write_text("Geometry Control File == geometry.tgc\n")
    model = TCF(top)
    first = assert_parity(model, ["-e1 A"])
    model.inputs[0].cf[0].inputs[0].rhs = "second.shp"
    second = assert_parity(model, ["-e1 A"])
    assert first.runs[0].file_references[-1].path_pattern.name == "first.shp"
    assert second.runs[0].file_references[-1].path_pattern.name == "second.shp"


def test_custom_translation_hook_requires_ordinary_batch_fallback(tmp_path: Path) -> None:
    """Custom translation can change literal paths absent from token signatures."""
    from unittest.mock import patch

    from pytuflow._tmf.context import Context
    from pytuflow._tmf.fragment_dependencies import _Plan

    top = tmp_path / "model.tcf"
    top.write_text("Read GIS Code == code.shp\n", encoding="utf-8")
    model = TCF(top)
    flags = ["-s1 A", "-s1 B", "-s1 A"]
    original = Context.translate

    def dynamic_translate(self: Context, item: object) -> object:
        result = original(self, item)
        if isinstance(result, str) and "code.shp" in result:
            scenarios = self._create_list("S")
            scenario = scenarios[0] if scenarios else "UNKNOWN"
            return result.replace("code.shp", f"code_{scenario}.shp")
        return result

    with patch.object(Context, "translate", dynamic_translate):
        with pytest.raises(NotImplementedError, match=r"Custom Context\.translate"):
            _Plan(model)
        ordinary = collect_fallback_dependencies(model, flags)
        fragments = model.collect_file_dependencies(flags)
        assert ordinary.runs == fragments.runs
        assert ordinary.passed and fragments.passed
        # Custom translation changes require the ordinary evaluator on each run.
        assert fragments.fallback_runs == len(flags)
        assert "Custom Context.translate" in (fragments.fallback_reason or "")
        assert [run.file_references[-1].path_pattern.name for run in fragments.runs] == [
            "code_A.shp",
            "code_B.shp",
            "code_A.shp",
        ]


@pytest.mark.parametrize(
    "declared,exposed", [("\u03a3", "\u03c2"), ("I", "\u0131"), ("S", "\u017f")]
)
def test_unicode_tef_cascade_cannot_reuse_another_selected_file(
    tmp_path: Path, declared: str, exposed: str
) -> None:
    # The first TEF pass exposes a Unicode case variant after its own turn.
    (tmp_path / "events.tef").write_text(
        f"Define Event == A\n BC Event Source == _{declared}_ | first\n"
        f" BC Event Source == _x_ | _{exposed}_\nEnd Define\n"
        f"Define Event == B\n BC Event Source == _{declared}_ | second\n"
        f" BC Event Source == _x_ | _{exposed}_\nEnd Define\n",
        encoding="utf-8",
    )
    for name in ("first", "second"):
        (tmp_path / (name + ".tgc")).write_text(f"Read GIS Code == {name}.shp\n")
    top = tmp_path / "model.tcf"
    top.write_text(
        f"Event File == events.tef\nGeometry Control File == _x_.tgc\nRead GIS Code == _{exposed}_.shp\n",
        encoding="utf-8",
    )
    result = assert_parity(TCF(top), ["-e1 A", "-e1 B", "-e1 A"])
    assert result.passed
    assert [run.file_references[-1].path_pattern.name for run in result.runs] == [
        "first.shp",
        "second.shp",
        "first.shp",
    ]
    assert [run.file_references[1].path_pattern.name for run in result.runs] == [
        "first.tgc",
        "second.tgc",
        "first.tgc",
    ]


@pytest.mark.parametrize(
    "declared,exposed", [("\u03a3", "\u03c2"), ("I", "\u0131"), ("S", "\u017f")]
)
def test_unicode_event_independence_certificate_is_conservative(
    declared: str, exposed: str
) -> None:
    from pytuflow._tmf.effective_dependencies import EffectiveDependencyManifest
    from pytuflow._tmf.fragment_dependencies import ExpressionPool, _FragmentContext
    from pytuflow._tmf.settings import TCFConfig

    manifest = EffectiveDependencyManifest(1, (), (), (f"_{exposed}_.shp",), (), None)
    ctx = _FragmentContext("", TCFConfig(), ExpressionPool())
    ctx.event_variables[f"_{declared}_"] = "different"
    assert not manifest.event_independent(ctx)


@pytest.mark.parametrize("kind,slot", [("Scenario", "s1"), ("Event", "e1")])
def test_negative_alternative_keeps_variable_selection_and_full_records(
    tmp_path: Path, kind: str, slot: str
) -> None:
    top = tmp_path / "model.tcf"
    top.write_text(
        "Set Variable Choice == base\n"
        f"If {kind} == B\n Set Variable Choice == alternative\nEnd If\n"
        "Read GIS Code == code_<<Choice>>.shp\n"
    )
    result = assert_parity(TCF(top), [{slot: "A | !B"}, {slot: "B"}, {slot: "A | !B"}])
    assert result.passed
    assert [run.file_references[-1].path_pattern.name for run in result.runs] == [
        "code_base.shp",
        "code_alternative.shp",
        "code_base.shp",
    ]


def test_event_dependent_inline_read_file_uses_explicit_fallback(
    tmp_path: Path,
) -> None:
    (tmp_path / "events.tef").write_text(
        "Define Event == A\n BC Event Source == _file_ | first\nEnd Define\n"
        "Define Event == B\n BC Event Source == _file_ | second\nEnd Define\n"
    )
    for name in ("first", "second"):
        (tmp_path / (name + ".trd")).write_text(f"Read GIS Code == {name}.shp\n")
    top = tmp_path / "model.tcf"
    top.write_text("Event File == events.tef\nRead File == _file_.trd\n")
    result = assert_parity(TCF(top), ["-e1 A", "-e1 B"])
    assert result.fallback_runs == 2
    assert (
        result.fallback_reason
        == "Dynamic inline Read File requires the ordinary evaluator"
    )
