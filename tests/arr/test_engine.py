"""Tests for :mod:`pytuflow.arr.engine`, using a cached real Data Hub API response and
cached temporal pattern zip downloads (no live network access required).
"""

from __future__ import annotations

import pytest

from pytuflow.arr import temporal_patterns as tp_module
from pytuflow.arr.config import ArrConfig
from pytuflow.arr.engine import ArrEngine
from pytuflow.arr.exceptions import ArrError

SITE_CONFIG = {
    'site': {'name': '1', 'latitude': -33.9347, 'longitude': 150.8372, 'catchment_area': 11.4},
    'ifd': {'source': 'bom', 'year': 1990},
    'output': {'path': '/tmp/unused', 'format': 'csv'},
}


@pytest.fixture(autouse=True)
def mock_tp_downloads(monkeypatch, point_tp_csv, areal_tp_csv):
    """Redirects temporal pattern zip downloads to the cached fixture CSVs so engine
    tests do not require live network access."""
    def fake_download(url: str) -> str:
        if 'Areal' in url:
            return areal_tp_csv
        return point_tp_csv
    monkeypatch.setattr(tp_module, '_download_increments_csv', fake_download)


def make_config(**overrides) -> ArrConfig:
    data = {**SITE_CONFIG, **overrides}
    return ArrConfig.from_dict(data)


def test_engine_complete_storm_prepends_preburst(api_response_1990):
    config = make_config(complete_storm=True,
                          events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is not None
    assert r.preburst.depth > 0
    assert r.initial_loss > 0  # full storm initial loss, not the reduced burst il


def test_engine_assembles_single_event(api_response_1990):
    # 50%/1440min has a fixed (non-placeholder) burst initial loss in the fixture data.
    config = make_config(events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.aep_name == '50%'
    assert r.duration == 1440.0
    assert r.depth_point > 0
    assert 0 < r.arf <= 1.0
    assert r.depth_areal == pytest.approx(r.depth_point * r.arf)
    assert r.initial_loss > 0
    assert r.continuing_loss > 0
    assert r.aep_band == 'frequent'
    assert len(r.patterns) == 10
    assert r.cc_scenario is None


def test_engine_multiple_durations_and_aeps(api_response_1990):
    config = make_config(events={'aep': ['50%'], 'duration': [60, 1440], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 2
    durations = {r.duration for r in results}
    assert durations == {60.0, 1440.0}


def test_engine_auto_triggers_complete_storm_for_use_pb_tp_placeholder(api_response_1990):
    # 20%/1440min is a 'Use PB TP' cell in the cached fixture data - the engine should
    # automatically switch to complete storm assembly for just this event, even though
    # complete_storm was not requested.
    config = make_config(events={'aep': ['20%'], 'duration': [1440], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is not None
    assert r.initial_loss > 0


def test_engine_short_duration_requires_extrapolation_method(api_response_1990):
    # duration shorter than the shortest datahub-provided duration, with
    # extrapolation_method='none' (the default) should raise rather than silently
    # produce a bad il.
    config = make_config(
        events={'aep': ['50%'], 'duration': [15], 'output_notation': 'ari'},
        losses={'extrapolation_method': 'none'},
    )
    engine = ArrEngine(config, api_response_1990)
    with pytest.raises(ArrError):
        engine.run()


def test_engine_short_duration_extrapolation_produces_smaller_loss(api_response_1990):
    config = make_config(
        events={'aep': ['50%'], 'duration': [15, 30], 'output_notation': 'ari'},
        losses={'extrapolation_method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = {r.duration: r for r in engine.run()}
    assert results[15.0].initial_loss < results[30.0].initial_loss


def test_engine_applies_climate_change_loss_factors(api_response_1990, monkeypatch):
    """Climate change scenario events should have their initial/continuing loss scaled
    by the Data Hub's 'ClimateChange' loss adjustment factors, relative to the base
    (no climate change) event."""
    rec_ifd = api_response_1990.layer('RecIFD')
    base_table = rec_ifd['Recommended Historical (1961-1990) Baseline']
    api_response_1990.layers['CCAdjIFDDatasets'] = {
        'BoM IFD Depths (2090 Baseline - SSP2)': base_table,
    }
    api_response_1990.layers['ClimateChange'] = {
        'label': 'Climate Change Factors',
        'loss_factors': {
            'Initial_Loss': {
                'columns': ['Losses SSP1-2.6', 'Losses SSP2-4.5', 'Losses SSP3-7.0', 'Losses SSP5-8.5'],
                'index': [2090],
                'data': [[1.03, 1.05, 1.07, 1.08]],
            },
            'Continuing_Loss': {
                'columns': ['Losses SSP1-2.6', 'Losses SSP2-4.5', 'Losses SSP3-7.0', 'Losses SSP5-8.5'],
                'index': [2090],
                'data': [[1.06, 1.09, 1.13, 1.16]],
            },
        },
    }
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        climate_change={'enabled': True, 'scenarios': [{'baseline_year': 2090, 'ssp': 'SSP2'}]},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 2
    base = next(r for r in results if r.cc_scenario is None)
    cc = next(r for r in results if r.cc_scenario == '2090_SSP2')
    assert cc.initial_loss == pytest.approx(base.initial_loss * 1.05)
    assert cc.continuing_loss == pytest.approx(base.continuing_loss * 1.09)


def test_engine_probability_neutral_method_uses_burst_il_layer(api_response_1990):
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        losses={'method': 'probability_neutral'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    expected = api_response_1990.layer('BurstIL')['data'][7][0]  # duration 1440, aep '50.0'
    assert results[0].initial_loss == pytest.approx(expected)


def test_engine_probability_neutral_method_raises_when_unavailable(api_response_1990, monkeypatch):
    monkeypatch.setitem(api_response_1990.layers, 'BurstIL', None)
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        losses={'method': 'probability_neutral'},
    )
    engine = ArrEngine(config, api_response_1990)
    with pytest.raises(ArrError, match='probability_neutral'):
        engine.run()
