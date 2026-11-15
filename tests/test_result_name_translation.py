"""Regression tests for reordered flags, aliases and dotted result names."""

from __future__ import annotations

from pytuflow import TCF
from pytuflow._tmf.context import Context


def test_permuted_flags_translate_without_mutating_context() -> None:
    flags = {
        "e3": "TP01",
        "e2": "00540m",
        "e1": "01.0p",
        "e4": "EnsembleILCL",
        "e5": "CCNear",
        "s1": "EXG",
        "s2": "M3W",
        "s4": "16M",
    }
    before_flags = flags.copy()
    ctx = Context(flags)
    before_args = ctx.context_args.copy()
    filename = "UON_04_~s2~_~s1~_~e1~_~e2~_~e4~_~e3~_~e5~_~s4~.tcf"
    expected = "UON_04_M3W_EXG_01.0p_00540m_EnsembleILCL_TP01_CCNear_16M"

    assert ctx.translate_result_name(filename) == expected
    assert ctx.translate_result_name(filename) == expected
    assert flags == before_flags
    assert ctx.context_args == before_args


def test_aliases_repeated_placeholders_and_unused_flags() -> None:
    ctx = Context({"s2": "Other", "e2": "Duration", "e1": "01.0p", "s1": "EXG"})
    assert ctx.translate_result_name("demo_~E~_~e1~_~S~_~s1~.tcf") == (
        "demo_01.0p_01.0p_EXG_EXG_Duration_Other"
    )
    bare = Context({"e": "TP01", "s": "EXG", "e2": "2h"})
    assert bare.translate_result_name("demo_~e1~_~s1~.tcf") == "demo_TP01_EXG_2h"
    assert bare.translate_result_name("demo_~e~_~s~_~e2~.tcf") == "demo_TP01_EXG_2h"


def test_missing_placeholders_remain_unresolved() -> None:
    ctx = Context({"e1": "storm", "s1": "EXG"})
    assert ctx.translate_result_name("demo_~s9~_~e1~.tcf") == "demo_~s9~_storm_EXG"


def test_tcf_result_and_log_paths_keep_dotted_aep_stem(tmp_path) -> None:
    file = tmp_path / "UON_04_~s2~_~s1~_~e1~_~e2~_~e3~.tcf"
    file.write_text("Log Folder == log\nOutput Folder == output\n", encoding="utf-8")
    run = TCF(file).context(
        {"e3": "TP01", "e2": "00540m", "e1": "01.0p", "s1": "EXG", "s2": "M3W"}
    )
    expected = "UON_04_M3W_EXG_01.0p_00540m_TP01"
    assert run.output_name() == expected
    assert run.tlf_path().name == f"{expected}.tlf"
    assert run.tpc_path().name == f"{expected}.tpc"
