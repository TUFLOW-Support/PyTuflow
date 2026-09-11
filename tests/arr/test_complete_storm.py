"""Tests for :mod:`pytuflow.arr.complete_storm`, using a cached real Data Hub API
response and cached temporal pattern zip downloads (no live network access required).
"""

from __future__ import annotations

import pytest

from pytuflow.arr import temporal_patterns as tp_module
from pytuflow.arr.complete_storm import (
    build_preburst, constant_preburst, temporal_pattern_preburst, recommended_preburst, _preburst_ratio,
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
    pattern = recommended_preburst(api_response_1990, 30, '1%', 1.0, point_depth=100.0)
    assert pattern is not None
    assert pattern.method == 'recommended'
    # depth now comes from the Preburst50 (default percentile) ratio table at
    # duration=30/aep=1.0 (0.037), multiplied by point_depth, not RecPreburstTP's own
    # (mislabelled) 'Preburst Depth'/'Preburst Ratio' fields.
    assert pattern.depth == pytest.approx(0.037 * 100.0)
    assert sum(pattern.increments) == pytest.approx(100.0)
    assert pattern.timestep == pytest.approx(5.0)
    assert pattern.event_id == 3743


def test_recommended_preburst_different_aep_same_duration(api_response_1990):
    pattern = recommended_preburst(api_response_1990, 30, '50%', 50.0, point_depth=100.0)
    assert pattern is not None
    assert pattern.depth == pytest.approx(0.1 * 100.0)
    assert sum(pattern.increments) == pytest.approx(100.0)


def test_recommended_preburst_uses_configured_percentile(api_response_1990):
    # switching percentile changes which ratio table is used for the depth, even
    # though the same historical event (shape) is matched.
    default_pattern = recommended_preburst(api_response_1990, 30, '1%', 1.0, point_depth=100.0)
    ratio_90 = recommended_preburst(api_response_1990, 30, '1%', 1.0, point_depth=100.0, percentile='90%')
    assert ratio_90.depth != default_pattern.depth
    assert ratio_90.event_id == default_pattern.event_id  # same shape/event


def test_recommended_preburst_requires_point_depth(api_response_1990):
    with pytest.raises(ArrError, match='point_depth'):
        recommended_preburst(api_response_1990, 30, '1%', 1.0)


def test_build_preburst_recommended_uses_percentile_setting(api_response_1990):
    config = make_config(
        events={'aep': ['1%'], 'duration': [30], 'output_notation': 'ari'},
        preburst={'percentile': '90%'},
    )
    pattern = build_preburst(api_response_1990, config, None, 30, '1%', 1.0, 100.0)
    assert pattern.method == 'recommended'
    default_pattern = recommended_preburst(api_response_1990, 30, '1%', 1.0, point_depth=100.0)
    assert pattern.depth != default_pattern.depth


def test_recommended_preburst_falls_back_to_same_duration_and_band(api_response_1990, monkeypatch):
    # remove the exact 1% AEP/30min row, leaving the 2% row (also 'rare' band, per
    # aep_band) at the same duration - the fallback should pick it up for the *shape*,
    # but the depth still uses the originally requested duration/AEP (30min/1%) against
    # the ratio table, not the fallback row's own duration/AEP.
    layer = api_response_1990.layer('RecPreburstTP')
    rows = [r for r in layer['selected_patterns'] if not (r['Duration'] == 30 and r['AEP'] == 1.0)]
    monkeypatch.setitem(api_response_1990.layers['RecPreburstTP'], 'selected_patterns', rows)
    pattern = recommended_preburst(api_response_1990, 30, '1%', 1.0, point_depth=100.0)
    assert pattern is not None
    assert pattern.depth == pytest.approx(0.037 * 100.0)


def test_recommended_preburst_for_aep_rarer_than_1pct_uses_1pct_pattern(api_response_1990):
    # 0.5% AEP has no exact (Duration, AEP) row in RecPreburstTP (the layer's rarest
    # AEP is 1%) - among the same-duration 'rare' band candidates (2%, 1%), the
    # fallback should pick the one *closest* to 0.5% (i.e. 1%), not simply the first
    # one found in the Data Hub's response ordering (which happens to be 2%).
    pattern = recommended_preburst(api_response_1990, 1440, '0.5%', 0.5, point_depth=100.0)
    assert pattern is not None
    layer = api_response_1990.layer('RecPreburstTP')
    expected_row = next(r for r in layer['selected_patterns'] if r['Duration'] == 1440 and r['AEP'] == 1.0)
    assert pattern.event_id == expected_row['Event ID']


def test_recommended_preburst_falls_back_to_closest_duration_same_band(api_response_1990):
    # duration=120min has no 'frequent' band (50%/20%) rows in RecPreburstTP at all -
    # falls back to the closest available duration with a 'frequent' band row (90min,
    # 30min away, vs 180min which is 60min away). The shape (event_id/increments/
    # timestep) comes from that 90min row, but the depth/ratio still uses the
    # *originally requested* duration/AEP (120min/50%), not the fallback row's own.
    pattern = recommended_preburst(api_response_1990, 120, '50%', 50.0, point_depth=100.0)
    assert pattern is not None
    assert pattern.method == 'recommended'
    layer = api_response_1990.layer('RecPreburstTP')
    expected_row = next(r for r in layer['selected_patterns'] if r['Duration'] == 90 and r['AEP'] == 50.0)
    assert pattern.event_id == expected_row['Event ID']
    expected_ratio = _preburst_ratio(api_response_1990, '50%', 120, 50.0)
    assert pattern.depth == pytest.approx(expected_ratio * 100.0)


def test_recommended_preburst_returns_none_when_band_has_no_data_at_all(api_response_1990, monkeypatch):
    # simulate a Data Hub response with no RecPreburstTP rows at all for the 'frequent'
    # event rarity band (across every duration) - neither an exact match, a
    # same-duration/band fallback, nor a closest-duration/band fallback exists.
    from pytuflow.arr.temporal_patterns import aep_band
    layer = api_response_1990.layer('RecPreburstTP')
    rows = [r for r in layer['selected_patterns'] if aep_band(f"{float(r['AEP'])}%", 'ari') != 'frequent']
    monkeypatch.setitem(api_response_1990.layers['RecPreburstTP'], 'selected_patterns', rows)
    assert recommended_preburst(api_response_1990, 120, '50%', 50.0, point_depth=100.0) is None


def test_build_preburst_recommended_default(api_response_1990):
    config = make_config(events={'aep': ['1%'], 'duration': [30], 'output_notation': 'ari'})
    pattern = build_preburst(api_response_1990, config, None, 30, '1%', 1.0, 58.7)
    assert pattern.method == 'recommended'
    assert pattern.depth == pytest.approx(0.037 * 58.7)


def test_build_preburst_recommended_missing_raises(api_response_1990, monkeypatch):
    # same 'frequent' band removed entirely (see
    # test_recommended_preburst_returns_none_when_band_has_no_data_at_all) and no
    # tp_set available either - build_preburst should raise rather than silently
    # returning nothing.
    from pytuflow.arr.temporal_patterns import aep_band
    layer = api_response_1990.layer('RecPreburstTP')
    rows = [r for r in layer['selected_patterns'] if aep_band(f"{float(r['AEP'])}%", 'ari') != 'frequent']
    monkeypatch.setitem(api_response_1990.layers['RecPreburstTP'], 'selected_patterns', rows)
    config = make_config(events={'aep': ['50%'], 'duration': [120], 'output_notation': 'ari'})
    with pytest.raises(ArrError, match='No recommended preburst'):
        build_preburst(api_response_1990, config, None, 120, '50%', 50.0, 58.7)


def test_recommended_preburst_falls_back_to_closest_duration_below_min(api_response_1990):
    # RecPreburstTP's shortest duration is 30min - duration=10 has no row at all (of
    # any AEP/band), so falls back to the closest available duration (30min) sharing
    # the same event rarity band ('rare', for 1% AEP) rather than returning None.
    pattern = recommended_preburst(api_response_1990, 10, '1%', 1.0, point_depth=100.0)
    assert pattern is not None
    assert pattern.method == 'recommended'
    layer = api_response_1990.layer('RecPreburstTP')
    assert next(r for r in layer['selected_patterns'] if r['Event ID'] == pattern.event_id)['Duration'] == 30


def test_build_preburst_recommended_falls_back_to_first_point_tp_when_band_has_no_data(
        api_response_1990, tp_set, monkeypatch):
    # simulate a Data Hub response with no RecPreburstTP rows at all for the 'rare'
    # event rarity band (across every duration, so even the closest-duration fallback
    # finds nothing) - build_preburst should fall back further still, to the first
    # available point/design temporal pattern (same duration/AEP band) as the preburst
    # shape, rather than raising.
    from pytuflow.arr.temporal_patterns import aep_band
    layer = api_response_1990.layer('RecPreburstTP')
    rows = [r for r in layer['selected_patterns'] if aep_band(f"{float(r['AEP'])}%", 'ari') != 'rare']
    monkeypatch.setitem(api_response_1990.layers['RecPreburstTP'], 'selected_patterns', rows)
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
