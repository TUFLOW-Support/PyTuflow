"""Tests for :mod:`pytuflow.arr.complete_storm`, using a cached real Data Hub API
response and cached temporal pattern zip downloads (no live network access required).
"""

from __future__ import annotations

import pytest

from pytuflow.arr import temporal_patterns as tp_module
from pytuflow.arr.complete_storm import (
    build_preburst, constant_preburst, temporal_pattern_preburst, recommended_preburst,
)
from pytuflow.arr.config import ArrConfig
from pytuflow.arr.exceptions import ArrError
from pytuflow.arr.temporal_patterns import TemporalPatternSet

SITE_CONFIG = {
    'site': {'name': '1', 'latitude': -33.9347, 'longitude': 150.8372, 'catchment_area': 11.4},
    'ifd': {'source': 'bom', 'year': 1990},
    'output': {'path': '/tmp/unused', 'format': 'csv'},
}


@pytest.fixture(autouse=True)
def mock_tp_downloads(monkeypatch, point_tp_csv, areal_tp_csv):
    def fake_download(url: str) -> str:
        if 'Areal' in url:
            return areal_tp_csv
        return point_tp_csv
    monkeypatch.setattr(tp_module, '_download_increments_csv', fake_download)


def make_config(**overrides) -> ArrConfig:
    data = {**SITE_CONFIG, **overrides}
    return ArrConfig.from_dict(data)


@pytest.fixture
def tp_set(api_response_1990) -> TemporalPatternSet:
    point_tp = api_response_1990.layer('PointTP', required=True)
    areal_tp = api_response_1990.layer('ArealTP')
    return TemporalPatternSet.from_api_response(point_tp['url'], areal_tp['url'] if areal_tp else None, 11.4)


def test_recommended_preburst_normalises_increments_to_100(api_response_1990):
    pattern = recommended_preburst(api_response_1990, 30, '1%', 1.0)
    assert pattern is not None
    assert pattern.method == 'recommended'
    assert pattern.depth == pytest.approx(69.6)
    assert sum(pattern.increments) == pytest.approx(100.0)
    assert pattern.timestep == pytest.approx(5.0)
    assert pattern.event_id == 3743


def test_recommended_preburst_different_aep_same_duration(api_response_1990):
    pattern = recommended_preburst(api_response_1990, 30, '50%', 50.0)
    assert pattern is not None
    assert pattern.depth == pytest.approx(29.5)
    assert sum(pattern.increments) == pytest.approx(100.0)


def test_recommended_preburst_ratio_uses_preburst_ratio_times_point_depth(api_response_1990):
    # AEP 1%/30min row: Preburst Ratio == 0.455 - scaled to a supplied point depth of
    # 100mm (rather than the raw historical 'Preburst Depth' of 69.6mm).
    pattern = recommended_preburst(
        api_response_1990, 30, '1%', 1.0, point_depth=100.0, recommended_value='ratio',
    )
    assert pattern is not None
    assert pattern.depth == pytest.approx(45.5)


def test_recommended_preburst_ratio_requires_point_depth(api_response_1990):
    with pytest.raises(ArrError, match='point_depth'):
        recommended_preburst(api_response_1990, 30, '1%', 1.0, recommended_value='ratio')


def test_build_preburst_recommended_value_ratio(api_response_1990):
    config = make_config(
        events={'aep': ['1%'], 'duration': [30], 'output_notation': 'ari'},
        preburst={'recommended_value': 'ratio'},
    )
    pattern = build_preburst(api_response_1990, config, None, 30, '1%', 1.0, 100.0)
    assert pattern.method == 'recommended'
    assert pattern.depth == pytest.approx(45.5)


def test_recommended_preburst_falls_back_to_same_duration_and_band(api_response_1990, monkeypatch):
    # remove the exact 1% AEP/30min row, leaving the 2% row (also 'rare' band, per
    # aep_band) at the same duration - the fallback should pick it up.
    layer = api_response_1990.layer('RecPreburstTP')
    rows = [r for r in layer['selected_patterns'] if not (r['Duration'] == 30 and r['AEP'] == 1.0)]
    monkeypatch.setitem(api_response_1990.layers['RecPreburstTP'], 'selected_patterns', rows)
    pattern = recommended_preburst(api_response_1990, 30, '1%', 1.0)
    assert pattern is not None
    assert pattern.depth == pytest.approx(62.4)  # the 2% AEP/30min row's preburst depth


def test_recommended_preburst_returns_none_when_no_fallback_available(api_response_1990):
    # duration=120 has no 'frequent' band (50%/20%) rows at all - neither an exact
    # match nor a same-duration/same-band fallback exists.
    assert recommended_preburst(api_response_1990, 120, '50%', 50.0) is None


def test_build_preburst_recommended_default(api_response_1990):
    config = make_config(events={'aep': ['1%'], 'duration': [30], 'output_notation': 'ari'})
    pattern = build_preburst(api_response_1990, config, None, 30, '1%', 1.0, 58.7)
    assert pattern.method == 'recommended'
    assert pattern.depth == pytest.approx(69.6)


def test_build_preburst_recommended_missing_raises(api_response_1990):
    config = make_config(events={'aep': ['50%'], 'duration': [120], 'output_notation': 'ari'})
    with pytest.raises(ArrError, match='No recommended preburst'):
        build_preburst(api_response_1990, config, None, 120, '50%', 50.0, 58.7)


def test_recommended_preburst_returns_none_for_duration_below_min(api_response_1990):
    # RecPreburstTP's shortest duration is 30min - there is no row (of any AEP/band) at
    # duration=10, so neither an exact match nor the same-duration/band fallback exists.
    assert recommended_preburst(api_response_1990, 10, '1%', 1.0) is None


def test_build_preburst_recommended_falls_back_to_first_point_tp_below_min_duration(api_response_1990, tp_set):
    # duration=10 has no RecPreburstTP data at all - build_preburst should fall back
    # further to the first available point/design temporal pattern (same duration/AEP
    # band) as the preburst shape, rather than raising.
    config = make_config(events={'aep': ['1%'], 'duration': [10], 'output_notation': 'ari'})
    pattern = build_preburst(api_response_1990, config, tp_set, 10, '1%', 1.0, 24.0)
    assert pattern.method == 'recommended'
    assert pattern.depth > 0
    assert sum(pattern.increments) == pytest.approx(100.0)
    expected_row = tp_set.point_tp[
        (tp_set.point_tp['duration'] == 10) & (tp_set.point_tp['aep_band'] == 'rare')
    ].sort_values('tp_number').iloc[0]
    assert pattern.timestep == pytest.approx(float(expected_row.timestep))
    assert pattern.increments == list(expected_row.increments)


def test_constant_preburst_fixed_duration(api_response_1990):
    config = make_config(
        events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
        preburst={'percentile': '50%', 'pattern_method': 'constant', 'pattern_duration': 2.0},
    )
    pattern = constant_preburst(api_response_1990, config, 1440, '1%', 1.0, 74.5)
    assert pattern.method == 'constant'
    assert pattern.timestep == pytest.approx(120.0)  # 2 hours -> 120 min
    assert pattern.increments == [100.0]
    assert pattern.depth > 0


def test_constant_preburst_proportional_duration(api_response_1990):
    config = make_config(
        events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
        preburst={'percentile': '50%', 'pattern_method': 'constant', 'pattern_duration': 0.5,
                  'duration_proportional': True},
    )
    pattern = constant_preburst(api_response_1990, config, 1440, '1%', 1.0, 74.5)
    assert pattern.timestep == pytest.approx(720.0)  # 0.5 * 1440


def test_constant_preburst_requires_pattern_duration(api_response_1990):
    config = make_config(
        events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
        preburst={'percentile': '50%', 'pattern_method': 'constant'},
    )
    with pytest.raises(ArrError, match='pattern_duration'):
        constant_preburst(api_response_1990, config, 1440, '1%', 1.0, 74.5)


def test_temporal_pattern_preburst_uses_specific_tp(api_response_1990, tp_set):
    config = make_config(
        events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
        preburst={'percentile': '50%', 'pattern_method': 'temporal_pattern', 'pattern_duration': 1.0,
                  'pattern_tp': 'TP03'},
    )
    pattern = temporal_pattern_preburst(api_response_1990, config, tp_set, 1440, '1%', 1.0, 74.5)
    assert pattern.method == 'temporal_pattern'
    assert pattern.depth > 0
    assert sum(pattern.increments) > 0
    assert pattern.per_tp_increments is None


def test_temporal_pattern_preburst_requires_pattern_tp(api_response_1990, tp_set):
    config = make_config(
        events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
        preburst={'percentile': '50%', 'pattern_method': 'temporal_pattern', 'pattern_duration': 1.0},
    )
    with pytest.raises(ArrError, match='pattern_tp'):
        temporal_pattern_preburst(api_response_1990, config, tp_set, 1440, '1%', 1.0, 74.5)


def test_temporal_pattern_preburst_design_burst_matches_tp_number(api_response_1990, tp_set):
    config = make_config(
        events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
        preburst={'percentile': '50%', 'pattern_method': 'temporal_pattern', 'pattern_duration': 1.0,
                  'pattern_tp': 'design_burst'},
    )
    design_patterns = tp_set.patterns(1440, '1%', 'ari')
    assert design_patterns  # sanity check the fixture actually has design patterns here
    pattern = temporal_pattern_preburst(
        api_response_1990, config, tp_set, 1440, '1%', 1.0, 74.5, design_patterns=design_patterns)
    assert pattern.method == 'temporal_pattern'
    assert pattern.depth > 0
    assert pattern.per_tp_increments is not None
    assert set(pattern.per_tp_increments) == {p.tp_number for p in design_patterns}
    # each design pattern's own tp_number should have a distinct preburst shape sourced
    # from the same tp_number in the point TP table, at the closest available duration
    # to the (proportional/absolute) requested preburst duration.
    band = 'rare'
    available = sorted(tp_set.point_tp.loc[tp_set.point_tp['aep_band'] == band, 'duration'].unique())
    pb_duration = min(available, key=lambda d: abs(d - 60.0))  # 1.0 hour -> 60 min target
    for p in design_patterns:
        expected_row = tp_set.point_tp[
            (tp_set.point_tp['duration'] == pb_duration)
            & (tp_set.point_tp['aep_band'] == band)
            & (tp_set.point_tp['tp_number'] == p.tp_number)
        ].iloc[0]
        assert pattern.per_tp_increments[p.tp_number] == list(expected_row.increments)


def test_temporal_pattern_preburst_design_burst_requires_design_patterns(api_response_1990, tp_set):
    config = make_config(
        events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
        preburst={'percentile': '50%', 'pattern_method': 'temporal_pattern', 'pattern_duration': 1.0,
                  'pattern_tp': 'design_burst'},
    )
    with pytest.raises(ArrError, match='design burst temporal patterns'):
        temporal_pattern_preburst(api_response_1990, config, tp_set, 1440, '1%', 1.0, 74.5)


def test_build_preburst_unrecognised_method(api_response_1990):
    with pytest.raises(ArrError, match='pattern_method'):
        make_config(
            events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
            preburst={'pattern_method': 'bogus'},
        )


def test_constant_preburst_recommended_percentile_uses_rec_preburst_layer(api_response_1990):
    from pytuflow.arr.complete_storm import _preburst_ratio
    ratio_recommended = _preburst_ratio(api_response_1990, 'recommended', 1440, 1.0)
    assert ratio_recommended > 0

    config = make_config(
        events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
        preburst={'percentile': 'recommended', 'pattern_method': 'constant', 'pattern_duration': 2.0},
    )
    pattern = constant_preburst(api_response_1990, config, 1440, '1%', 1.0, 74.5)
    assert pattern.depth == pytest.approx(ratio_recommended * 74.5)
