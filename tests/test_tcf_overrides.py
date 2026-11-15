"""Public API regressions for implicit TCF overrides (issue #64)."""

from io import StringIO
from unittest.mock import patch

import pytest

from pytuflow import TCF, FileResolution
from pytuflow._tmf.settings import TCFConfig
from pytuflow.batch_validation import validate_batch_inputs


@pytest.mark.parametrize("resolution", list(FileResolution))
@pytest.mark.parametrize("selection", ["none", "generic", "machine", "both", "other-machine"])
def test_override_folder_precedence_and_model_identity(tmp_path, resolution, selection):
    tcf = tmp_path / "demo_~e1~.tcf"
    tcf.write_text(
        "Set Variable OutputBase == base\n"
        "Set Variable LogName == logs\n"
        "Log Folder == <<OutputBase>>/<<LogName>>\n"
        "Output Folder == <<OutputBase>>/results\n"
        "BC Event File == events.tef\n"
        "Start Time == 0\nEnd Time == 1\n",
        encoding="utf-8",
    )
    (tmp_path / "events.tef").write_text(
        "Define Event == storm\nBC Event Source == ~RAIN~ | wet\nEnd Define\n",
        encoding="utf-8",
    )
    for kind in ("generic", "machine", "other-machine"):
        if kind == selection or (selection == "both" and kind != "other-machine"):
            name = {"generic": "_TUFLOW_Override.tcf",
                    "machine": "_TUFLOW_Override_test-node.tcf",
                    "other-machine": "_TUFLOW_Override_other-node.tcf"}[kind]
            (tmp_path / name).write_text(
                f"Set Variable OutputBase == {kind}\n"
                "Log Folder == <<OutputBase>>/<<LogName>>/~RAIN~\n"
                "Output Folder == <<OutputBase>>/results/~RAIN~\n",
                encoding="utf-8",
            )

    with patch("pytuflow._tmf.settings.platform.node", return_value="test-node"):
        model = TCF(tcf)
        run = model.context({"e1": "storm"}, file_resolution=resolution)

    selected = "machine" if selection == "both" else selection
    overridden = selected in ("machine", "generic")
    base = tmp_path / (selected if overridden else "base")
    assert run.log_folder_path() == (base / "logs" / "wet" if overridden else base / "logs")
    assert run.output_folder_2d() == (base / "results" / "wet" if overridden else base / "results")
    assert run.tlf_path() == run.log_folder_path() / "demo_storm.tlf"
    assert run.output_name() == "demo_storm"
    assert run.fpath == tcf
    assert model.config.tcf == tcf
    assert model.config.control_file == tcf
    assert model.config.model_name == TCFConfig.get_model_name(tcf)
    assert len(model.config.event_db.inputs) == 1
    assert len(model.find_input(lhs="log folder", recursive=True)) == (2 if overridden else 1)
    buf = StringIO()
    model.preview(buf)
    assert "_TUFLOW_Override" not in buf.getvalue()


@pytest.mark.parametrize("resolution", list(FileResolution))
def test_override_absolute_variable_and_relative_include(tmp_path, resolution):
    runs = tmp_path / "runs"
    runs.mkdir()
    local = tmp_path / "local-output"
    tcf = runs / "demo.tcf"
    tcf.write_text("Set Variable OutputBase == ../base\nLog Folder == <<OutputBase>>/logs\n", encoding="utf-8")
    (runs / "_TUFLOW_Override.tcf").write_text(
        f"Set Variable OutputBase == {local}\nRead File == ../folders.trd\n",
        encoding="utf-8",
    )
    (tmp_path / "folders.trd").write_text(
        "Log Folder == <<OutputBase>>/logs\nOutput Folder == ../relative-results\n",
        encoding="utf-8",
    )
    model = TCF(tcf)
    run = model.context({}, file_resolution=resolution)
    assert run.log_folder_path() == local / "logs"
    assert run.tlf_path() == local / "logs" / "demo.tlf"
    assert run.output_folder_2d().resolve() == (tmp_path / "relative-results").resolve()
    # The same include traversal must remain valid for deferred batch callers.
    result = validate_batch_inputs(model, [{}])
    assert result.passed, result.issues


def test_direct_override_does_not_load_itself(tmp_path):
    override = tmp_path / "_TUFLOW_Override.tcf"
    override.write_text("Log Folder == logs\n", encoding="utf-8")
    run = TCF(override).context({}, file_resolution=FileResolution.DEFERRED)
    assert run.log_folder_path() == tmp_path / "logs"


@pytest.mark.parametrize("resolution", list(FileResolution))
def test_variable_only_override_and_scoped_run_isolation(tmp_path, resolution):
    tcf = tmp_path / "demo.tcf"
    tcf.write_text(
        "Set Variable OutputBase == base\n"
        "Log Folder == <<OutputBase>>/logs\n"
        "Output Folder == <<OutputBase>>/results\n",
        encoding="utf-8",
    )
    override = tmp_path / "_TUFLOW_Override.tcf"
    override.write_text(
        "If Scenario == local\nSet Variable OutputBase == local\n"
        "Else\nSet Variable OutputBase == remote\nEnd If\n",
        encoding="utf-8",
    )
    original = tcf.read_text(encoding="utf-8")
    original_override = override.read_text(encoding="utf-8")
    model = TCF(tcf)
    for scenario in ("local", "remote", "local"):
        run = model.context({"s1": scenario}, file_resolution=resolution)
        assert run.log_folder_path() == tmp_path / scenario / "logs"
        assert run.output_folder_2d() == tmp_path / scenario / "results"
    model.write(inc="inplace")
    assert tcf.read_text(encoding="utf-8") == original
    assert override.read_text(encoding="utf-8") == original_override


def test_implicit_override_fragment_collector_reuses_40_distinct_runs(tmp_path):
    """A normal implicit override is a supported include, not a fallback."""
    from pytuflow._tmf.deferred_dependency_fallback import collect_fallback_dependencies

    top = tmp_path / "model_~s1~_~e1~.tcf"
    top.write_text(
        "Read Grid Zpts == common.tif\n"
        "If Scenario == EXG\nRead GIS Code == existing.shp\nEnd If\n",
        encoding="utf-8",
    )
    (tmp_path / "_TUFLOW_Override.tcf").write_text(
        "Read GIS Code == additional.shp\n"
        "If Scenario == NEW\nRead Grid Zpts == new.tif\nEnd If\n",
        encoding="utf-8",
    )
    model = TCF(top)
    flags = [
        {"s1": "EXG" if index % 2 else "NEW", "e1": f"TP{index:02d}"}
        for index in range(40)
    ]
    actual = model.collect_file_dependencies(flags)
    expected = collect_fallback_dependencies(model, flags)

    assert actual.passed
    assert actual.fallback_runs == 0, actual.fallback_reason
    assert actual.fragment_reuses > 0
    assert actual.runs == expected.runs
    assert len(actual.runs) == 40
    first = {r.path_pattern.name for r in actual.runs[0].file_references}
    second = {r.path_pattern.name for r in actual.runs[1].file_references}
    assert {"common.tif", "new.tif", "additional.shp"} <= first
    assert {"common.tif", "existing.shp", "additional.shp"} <= second


def test_monkeypatched_override_evaluator_still_forces_fallback(tmp_path):
    """Never allow custom implicit-override context hooks into fragment reuse."""
    from pytuflow._tmf.deferred_dependency_fallback import collect_fallback_dependencies

    top = tmp_path / "model.tcf"
    top.write_text("Read Grid Zpts == common.tif\n", encoding="utf-8")
    (tmp_path / "_TUFLOW_Override.tcf").write_text(
        "Read GIS Code == additional.shp\n", encoding="utf-8",
    )
    model = TCF(top)
    override = next(inp for inp in model.inputs if type(inp).__name__ == "_OverrideInput")
    original = override.context

    def wrapper(*args, **kwargs):
        return original(*args, **kwargs)

    override.context = wrapper
    flags = [{"s1": "EXG"}, {"s1": "NEW"}]
    actual = model.collect_file_dependencies(flags)
    expected = collect_fallback_dependencies(model, flags)
    assert actual.fallback_runs == len(flags)
    assert actual.fallback_reason == "Custom input context hook"
    assert actual.runs == expected.runs
