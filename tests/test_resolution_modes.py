"""Public option contracts for file resolution and Linux filename-case policy."""

from __future__ import annotations

from pathlib import Path

import pytest

from pytuflow import TCF, CaseSensitivity, FileResolution
from pytuflow._tmf.options import parse_case_sensitivity
from pytuflow._tmf.settings import TCFConfig
from pytuflow.validation import ValidationOptions


def test_linux_case_modes_have_documented_integer_values() -> None:
    """Match TUFLOW's -cs0/-cs1/-cs2 filename rules."""
    assert CaseSensitivity.STRICT.value == 0
    assert CaseSensitivity.EXTENSION_INSENSITIVE.value == 1
    assert CaseSensitivity.FILENAME_INSENSITIVE.value == 2


def test_configuration_uses_named_case_modes() -> None:
    """Normalise TUFLOW numeric levels to their named policies."""
    assert TCFConfig().case_sensitivity is CaseSensitivity.STRICT
    assert TCFConfig(case_sensitivity=2, init_from_tcf=False).case_sensitivity is (
        CaseSensitivity.FILENAME_INSENSITIVE
    )
    assert ValidationOptions(case_sensitivity=1).case_sensitivity is (
        CaseSensitivity.EXTENSION_INSENSITIVE
    )


@pytest.mark.parametrize("invalid", [-1, 3, True, "2", None, 1.0])
def test_invalid_case_policy_is_rejected(invalid: object) -> None:
    """Reject booleans and unsupported TUFLOW numeric levels."""
    with pytest.raises(ValueError, match="case_sensitivity"):
        parse_case_sensitivity(invalid)


def test_public_context_exposes_eager_and_deferred(tmp_path: Path) -> None:
    """Keep eager as the default, while accepting an explicit deferred mode."""
    path = tmp_path / "mode.tcf"
    path.write_text("! Empty model\n", encoding="utf-8")
    model = TCF(path)

    assert TCFConfig().file_resolution is FileResolution.EAGER
    assert model.context().ctx.file_resolution is FileResolution.EAGER
    assert (
        model.context(file_resolution=FileResolution.DEFERRED).ctx.file_resolution
        is FileResolution.DEFERRED
    )
    assert model.context(file_resolution=FileResolution.EAGER).ctx.file_resolution is FileResolution.EAGER
    with pytest.raises(ValueError, match="file_resolution"):
        model.context(file_resolution="unknown")
