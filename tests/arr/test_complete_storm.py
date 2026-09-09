"""Tests for :mod:`pytuflow.arr.complete_storm`, using a cached real Data Hub API
response and cached temporal pattern zip downloads (no live network access required).
"""

from __future__ import annotations

import pytest

from pytuflow.arr import temporal_patterns as tp_module
from pytuflow.arr.complete_storm import (
    build_preburst, constant_preburst, pattern_preburst, recommended_preburst,
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
    pattern = recommended_preburst(api_response_1990, 30, 1.0)
    assert pattern is not None
    assert pattern.method == 'recommended'
    assert pattern.depth == pytest.approx(69.6)
    assert sum(pattern.increments) == pytest.approx(100.0)
    assert pattern.timestep == pytest.approx(5.0)
    assert pattern.event_id == 3743


def test_recommended_preburst_different_aep_same_duration(api_response_1990):
    pattern = recommended_preburst(api_response_1990, 30, 50.0)
    assert pattern is not None
    assert pattern.depth == pytest.approx(29.5)
    assert sum(pattern.increments) == pytest.approx(100.0)


def test_recommended_preburst_returns_none_for_unmatched_cell(api_response_1990):
    assert recommended_preburst(api_response_1990, 30, 99.0) is None


def test_build_preburst_recommended_default(api_response_1990):
    config = make_config(events={'aep': ['1%'], 'duration': [30], 'output_notation': 'ari'})
    pattern = build_preburst(api_response_1990, config, None, 30, '1%', 1.0, 58.7)
    assert pattern.method == 'recommended'
    assert pattern.depth == pytest.approx(69.6)


def test_build_preburst_recommended_missing_raises(api_response_1990):
    config = make_config(events={'aep': ['1%'], 'duration': [30], 'output_notation': 'ari'})
    with pytest.raises(ArrError, match='No recommended preburst'):
        build_preburst(api_response_1990, config, None, 30, '1%', 99.0, 58.7)


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


def test_pattern_preburst_uses_specific_tp(api_response_1990, tp_set):
    config = make_config(
        events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
        preburst={'percentile': '50%', 'pattern_method': 'pattern', 'pattern_duration': 1.0,
                  'pattern_tp': 'TP03'},
    )
    pattern = pattern_preburst(api_response_1990, config, tp_set, 1440, '1%', 1.0, 74.5)
    assert pattern.method == 'pattern'
    assert pattern.depth > 0
    assert sum(pattern.increments) > 0


def test_pattern_preburst_rejects_design_burst(api_response_1990, tp_set):
    config = make_config(
        events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
        preburst={'percentile': '50%', 'pattern_method': 'pattern', 'pattern_duration': 1.0,
                  'pattern_tp': 'design_burst'},
    )
    with pytest.raises(ArrError, match='specific temporal pattern'):
        pattern_preburst(api_response_1990, config, tp_set, 1440, '1%', 1.0, 74.5)


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
