"""Tests for :mod:`pytuflow.arr.losses`, including a cross-check of the ``rahman``/
``hill``/``static`` formulas against the legacy ``ARR_TUFLOW_func_lib`` implementations
(which operate on numpy arrays/rows rather than plain durations, so the comparison
recreates their inputs rather than calling them directly with identical signatures).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pytuflow.arr.exceptions import ArrError
from pytuflow.arr.losses import (
    extrapolate_short_duration_losses,
    hill_loss,
    linear_interp_loss,
    rahman_loss,
    static_loss,
)


def test_rahman_loss_matches_legacy_formula():
    # legacy: ils * (0.5 + 0.25 * log10(d / 60.0)), only defined for d < 60
    ils = 20.0
    durations = [15, 30, 45]
    expected = [ils * (0.5 + 0.25 * np.log10(d / 60.0)) for d in durations]
    result = rahman_loss(durations, ils)
    np.testing.assert_allclose(result, expected)


def test_hill_loss_matches_legacy_formula():
    ils, mar = 20.0, 900.0
    durations = [15, 30, 45]
    expected = [ils * (1.0 - (1.0 / (1.0 + 142.0 * (d / 60.0) ** 0.5 / mar))) for d in durations]
    result = hill_loss(durations, ils, mar)
    np.testing.assert_allclose(result, expected)


def test_static_loss_is_constant():
    result = static_loss([10, 20, 30], 15.0)
    np.testing.assert_allclose(result, [15.0, 15.0, 15.0])


def test_linear_interp_loss_scales_from_reference():
    result = linear_interp_loss([15, 30], ref_duration=60, ref_value=20.0)
    np.testing.assert_allclose(result, [5.0, 10.0])


@pytest.fixture
def known_losses() -> pd.DataFrame:
    return pd.DataFrame(
        {'1.0': [10.0, 20.0], '50.0': [30.0, 40.0]},
        index=[30.0, 60.0],
    )


def test_extrapolate_static(known_losses):
    result = extrapolate_short_duration_losses(known_losses, [15, 30, 60], method='static', static_loss_value=5.0)
    assert 15.0 in result.index
    assert result.loc[15.0, '1.0'] == 5.0
    assert result.loc[15.0, '50.0'] == 5.0
    # existing rows untouched
    assert result.loc[30.0, '1.0'] == 10.0


def test_extrapolate_rahman(known_losses):
    result = extrapolate_short_duration_losses(known_losses, [15], method='rahman', ils=20.0)
    expected = rahman_loss([15], 20.0)[0]
    assert result.loc[15.0, '1.0'] == pytest.approx(expected)


def test_extrapolate_rahman_requires_ils(known_losses):
    with pytest.raises(ArrError, match='ils'):
        extrapolate_short_duration_losses(known_losses, [15], method='rahman')


def test_extrapolate_hill_requires_mar(known_losses):
    with pytest.raises(ArrError, match='mar'):
        extrapolate_short_duration_losses(known_losses, [15], method='hill', ils=20.0)


def test_extrapolate_no_short_durations_returns_copy(known_losses):
    result = extrapolate_short_duration_losses(known_losses, [60, 90], method='static', static_loss_value=5.0)
    pd.testing.assert_frame_equal(result, known_losses)
    assert result is not known_losses


def test_extrapolate_empty_table_raises():
    with pytest.raises(ArrError, match='empty'):
        extrapolate_short_duration_losses(pd.DataFrame(), [15], method='static', static_loss_value=5.0)


def test_extrapolate_interpolate_handles_non_numeric_reference_cell():
    table = pd.DataFrame({'1.0': ['Use PB TP', 20.0]}, index=[30.0, 60.0])
    result = extrapolate_short_duration_losses(table, [15], method='interpolate')
    assert pd.isna(result.loc[15.0, '1.0'])
