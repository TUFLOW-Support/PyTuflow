"""Missing TCF projection is reported by parsing, independent of CRS preflight."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from pytuflow import TCF
from pytuflow._tmf import gis
from pytuflow._tmf.settings import TCFConfig
from pytuflow.batch_validation import validate_batch_inputs
from pytuflow.validation import ValidationOptions


_MISSING = "does not define a GIS Projection or TIF Projection"


def _write_tcf(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "model.tcf"
    path.write_text(text, encoding="utf-8")
    return path


def _missing_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == "pytuflow"
        and record.levelno == logging.WARNING
        and _MISSING in record.getMessage()
    ]


def test_missing_projection_warns_when_tcf_is_loaded(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    path = _write_tcf(tmp_path, "Output Folder == output\n")
    with caplog.at_level(logging.WARNING, logger="pytuflow"):
        model = TCF(path, case_sensitivity=0)

    assert model.loaded
    assert len(_missing_warnings(caplog)) == 1
    assert str(path) in _missing_warnings(caplog)[0].getMessage()


def test_missing_projection_warns_without_crs_validation(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    path = _write_tcf(tmp_path, "Output Folder == output\n")
    with caplog.at_level(logging.WARNING, logger="pytuflow"):
        model = TCF(path, case_sensitivity=0)
        result = validate_batch_inputs(
            model,
            ["-s1 A"],
            options=ValidationOptions(
                case_sensitivity=0,
                check_crs=False,
                check_raster_metadata=False,
            ),
        )

    assert model.loaded
    assert result.passed, result.issues
    assert not result.warnings
    # This comes from initial model parsing, not from physical validation.
    assert len(_missing_warnings(caplog)) == 1


@pytest.mark.parametrize(
    "declaration",
    [
        "GIS Projection == reference.prj",
        "TIF Projection == reference.tif",
        'MI Projection == CoordSys Earth Projection 8, 104, "m", '
        "177, 0, 0.9996, 500000, 10000000",
    ],
)
def test_specified_projection_does_not_emit_missing_declaration_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    declaration: str,
) -> None:
    path = _write_tcf(tmp_path, declaration + "\n")
    monkeypatch.setattr(gis, "ogr_projection", lambda _source: "EPSG:28350")
    monkeypatch.setattr(gis, "gdal_projection", lambda _source: "EPSG:28350")

    with caplog.at_level(logging.WARNING, logger="pytuflow"):
        config = TCFConfig(tcf=path, case_sensitivity=0)

    assert config.tcf == path
    assert not _missing_warnings(caplog)


def test_invalid_declared_projection_keeps_specific_warning_without_false_omission(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_tcf(tmp_path, "GIS Projection == missing.prj\n")

    def invalid(_source: object) -> str:
        raise RuntimeError("No usable reference projection")

    monkeypatch.setattr(gis, "ogr_projection", invalid)
    with caplog.at_level(logging.WARNING, logger="pytuflow"):
        TCFConfig(tcf=path, case_sensitivity=0)

    assert not _missing_warnings(caplog)
    assert any(
        "Error extracting projection" in record.getMessage()
        for record in caplog.records
    )


def test_included_projection_prevents_missing_warning(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_tcf(tmp_path, "Read File == included.trd\n")
    (tmp_path / "included.trd").write_text(
        "GIS Projection == reference.prj\n", encoding="utf-8",
    )
    monkeypatch.setattr(gis, "ogr_projection", lambda _source: "EPSG:28350")

    with caplog.at_level(logging.WARNING, logger="pytuflow"):
        config = TCFConfig(tcf=path, case_sensitivity=0)

    assert config.projection_wkt == "EPSG:28350"
    assert not _missing_warnings(caplog)


def test_missing_tcf_does_not_generate_a_misleading_projection_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="pytuflow"):
        TCFConfig(tcf=tmp_path / "not_found.tcf", case_sensitivity=0)

    assert not _missing_warnings(caplog)


def test_override_context_preserves_projection_declaration() -> None:
    """The final TCF parse must not forget a declaration when copying context."""
    from pytuflow._tmf.settings import _ParseContext, _copy_parse_context

    initial = _ParseContext(_projection_declared=True)
    copied = _copy_parse_context(initial)

    assert copied is not initial
    assert copied._projection_declared
