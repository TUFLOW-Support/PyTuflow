"""Regression for TEF substitutions in BC Database CSV selectors (issue #61).

All inputs are disposable text files. No GIS provider or TUFLOW solver is needed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytuflow import TCF
from pytuflow._tmf.context import Context
from pytuflow.batch_validation import validate_batch_inputs
from pytuflow.validation import ValidationOptions


def _model(tmp_path: Path, *, event_command: str = "BC Event File") -> tuple[Path, Path]:
    runs = tmp_path / "runs"
    events = tmp_path / "model"
    boundaries = tmp_path / "bc_dbase"
    for directory in (runs, events, boundaries):
        directory.mkdir()

    (events / "EVENTS_01.tef").write_text(
        "Define Event == 01.0p\n"
        "    BC Event Source == ~AEP~ | 01.0p\n"
        "End Define\n"
        "Define Event == 02.0p\n"
        "    BC Event Source == ~AEP~ | 02.0p\n"
        "End Define\n"
        "Define Event == 01440m\n"
        "    BC Event Source == ~DUR~ | 01440m\n"
        "End Define\n",
        encoding="utf-8",
    )
    (boundaries / "bc_dbase.csv").write_text(
        "Name,Source,Column 1,Column 2,Add Col 1,Mult Col 2,Add Col 2,Column 3,Column 4\n"
        "Rainfall_003,TUFLOW-ML.csv,Time,~AEP~_~DUR~_M,,,,,\n",
        encoding="utf-8",
    )
    source = boundaries / "TUFLOW-ML.csv"
    source.write_text("Time,01.0p_01440m_M,02.0p_01440m_M\n0,1,2\n", encoding="utf-8")
    tcf = runs / "model.tcf"
    tcf.write_text(
        f"{event_command} == ../model/EVENTS_01.tef\n"
        "BC Database == ../bc_dbase/bc_dbase.csv\n",
        encoding="utf-8",
    )
    return tcf, source


def _options() -> ValidationOptions:
    return ValidationOptions(
        check_bc_csv_headers=True,
        check_raster_metadata=False,
        check_crs=False,
    )


@pytest.mark.parametrize("event_command", ["BC Event File", "Event File"])
@pytest.mark.parametrize(
    "flags",
    [
        pytest.param({"e1": "01.0p", "e2": "01440m"}, id="structured-flags"),
        pytest.param("-e1 01.0p -e2 01440m", id="text-flags"),
    ],
)
def test_tef_substitutions_expand_selected_bc_csv_header(
    tmp_path: Path, event_command: str, flags: str | dict[str, str],
) -> None:
    tcf, _ = _model(tmp_path, event_command=event_command)
    model = TCF(tcf)
    assert model.config.event_db
    assert Context(flags, config=model.config).translate("~AEP~_~DUR~_M") == (
        "01.0p_01440m_M"
    )

    result = validate_batch_inputs(model, [flags], options=_options())

    assert result.passed, result.issues
    assert result.dependencies.runs[0].database_sources[0].csv_columns == (
        "Time", "01.0p_01440m_M"
    )
    headers = [finding for finding in result.validation.findings if finding.kind == "csv_header"]
    assert len(headers) == 1
    assert headers[0].status == "present"
    assert headers[0].csv_columns == ("Time", "01.0p_01440m_M")
    assert result.validation.csv_headers_examined == 1


def test_tef_bc_csv_header_checks_are_isolated_by_selected_run(tmp_path: Path) -> None:
    tcf, source = _model(tmp_path)
    source.write_text("Time,01.0p_01440m_M\n0,1\n", encoding="utf-8")
    flags = [
        {"e1": "01.0p", "e2": "01440m"},
        {"e1": "02.0p", "e2": "01440m"},
    ]

    result = validate_batch_inputs(tcf, flags, options=_options())

    assert result.dependencies.passed
    assert not result.passed
    assert result.validation.csv_headers_examined == 1
    headers = {
        finding.run_index: finding
        for finding in result.validation.findings
        if finding.kind == "csv_header"
    }
    assert set(headers) == {0, 1}
    assert headers[0].status == "present"
    assert headers[0].csv_columns == ("Time", "01.0p_01440m_M")
    assert headers[1].status != "present"
    assert headers[1].csv_columns == ("Time", "02.0p_01440m_M")
    assert "02.0p_01440m_M" in headers[1].detail
    assert "~AEP~" not in headers[1].detail


def test_unknown_event_cannot_pass_using_literal_bc_selector(tmp_path: Path) -> None:
    tcf, source = _model(tmp_path)
    source.write_text("Time,~AEP~_~DUR~_M\n0,1\n", encoding="utf-8")

    result = validate_batch_inputs(
        tcf, [{"e1": "not-defined", "e2": "01440m"}], options=_options()
    )

    assert not result.passed
    assert result.issues
