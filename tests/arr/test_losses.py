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
    interpolate_missing_durations,
    linear_interp_loss,
    linear_interp_pb_depth,
    log_interp_loss,
    log_interp_pb_depth,
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


def test_log_interp_loss_matches_log_axis_interpolation():
    ref_duration, ref_value = 60.0, 20.0
    xp = [0.0, np.log10(ref_duration)]
    fp = [0.0, ref_value]
    durations = [15, 30]
    expected = np.interp(np.log10(durations), xp, fp)
    result = log_interp_loss(durations, ref_duration, ref_value)
    np.testing.assert_allclose(result, expected)


def test_linear_interp_pb_depth_matches_linear_interp_loss():
    result = linear_interp_pb_depth([15, 30], ref_duration=60, ref_value=20.0)
    np.testing.assert_allclose(result, linear_interp_loss([15, 30], 60, 20.0))


def test_log_interp_pb_depth_matches_log_interp_loss():
    result = log_interp_pb_depth([15, 30], ref_duration=60, ref_value=20.0)
    np.testing.assert_allclose(result, log_interp_loss([15, 30], 60, 20.0))


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


def test_extrapolate_log_interpolate(known_losses):
    result = extrapolate_short_duration_losses(known_losses, [15], method='log_interpolate')
    expected = log_interp_loss([15], 30.0, 10.0)[0]
    assert result.loc[15.0, '1.0'] == pytest.approx(expected)


def test_extrapolate_interpolate_preburst_requires_ils(known_losses):
    with pytest.raises(ArrError, match='ils'):
        extrapolate_short_duration_losses(known_losses, [15], method='interpolate_preburst')


def test_extrapolate_log_interpolate_preburst_requires_ils(known_losses):
    with pytest.raises(ArrError, match='ils'):
        extrapolate_short_duration_losses(known_losses, [15], method='log_interpolate_preburst')


def test_extrapolate_interpolate_preburst(known_losses):
    # storm ils = 50mm; known burst IL at duration=30 (threshold) is 10.0 for AEP '1.0'
    # => implied preburst depth at 30min = 50 - 10 = 40mm; extrapolated linearly to 15min
    # => pb_depth(15) = 40 * (15/30) = 20mm; burst_il(15) = 50 - 20 = 30mm
    result = extrapolate_short_duration_losses(known_losses, [15], method='interpolate_preburst', ils=50.0)
    assert result.loc[15.0, '1.0'] == pytest.approx(30.0)


def test_extrapolate_log_interpolate_preburst(known_losses):
    ref_pb_depth = 50.0 - 10.0
    expected_pb_depth = log_interp_pb_depth([15], 30.0, ref_pb_depth)[0]
    expected = 50.0 - expected_pb_depth
    result = extrapolate_short_duration_losses(known_losses, [15], method='log_interpolate_preburst', ils=50.0)
    assert result.loc[15.0, '1.0'] == pytest.approx(expected)


def test_extrapolate_preburst_handles_non_numeric_reference_cell():
    table = pd.DataFrame({'1.0': ['Use PB TP', 20.0]}, index=[30.0, 60.0])
    result = extrapolate_short_duration_losses(table, [15], method='interpolate_preburst', ils=50.0)
    assert pd.isna(result.loc[15.0, '1.0'])


def test_extrapolate_unknown_method_raises(known_losses):
    with pytest.raises(ArrError, match='Unknown loss extrapolation method'):
        extrapolate_short_duration_losses(known_losses, [15], method='bogus')


def test_interpolate_missing_durations_fills_internal_gap():
    table = pd.DataFrame({'1.0': [10.0, 40.0]}, index=[180.0, 360.0])
    result = interpolate_missing_durations(table, [180.0, 270.0, 360.0])
    assert list(result.index) == [180.0, 270.0, 360.0]
    assert result.loc[270.0, '1.0'] == pytest.approx(25.0)


def test_interpolate_missing_durations_ignores_out_of_range_and_existing():
    table = pd.DataFrame({'1.0': [10.0, 40.0]}, index=[180.0, 360.0])
    result = interpolate_missing_durations(table, [15.0, 180.0, 5000.0])
    assert list(result.index) == [180.0, 360.0]


def test_interpolate_missing_durations_multiple_gaps():
    table = pd.DataFrame({'1.0': [10.0, 40.0, 100.0]}, index=[60.0, 180.0, 360.0])
    result = interpolate_missing_durations(table, [90.0, 270.0])
    assert result.loc[90.0, '1.0'] == pytest.approx(10.0 + (40.0 - 10.0) * (90.0 - 60.0) / (180.0 - 60.0))
    assert result.loc[270.0, '1.0'] == pytest.approx(40.0 + (100.0 - 40.0) * (270.0 - 180.0) / (360.0 - 180.0))


def test_interpolate_missing_durations_non_numeric_reference_leaves_nan():
    table = pd.DataFrame({'1.0': ['Use PB TP', 40.0]}, index=[180.0, 360.0])
    result = interpolate_missing_durations(table, [270.0])
    assert pd.isna(result.loc[270.0, '1.0'])


def test_interpolate_missing_durations_empty_table_raises():
    with pytest.raises(ArrError, match='empty'):
        interpolate_missing_durations(pd.DataFrame(), [270.0])
