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


def test_engine_drops_negligible_preburst_and_falls_back_to_burst(api_response_1990):
    # force the recommended preburst depth for 50%/1440min to a negligible value
    # (implied ratio << 0.01 of the point design burst depth) - the engine should drop
    # the preburst period and fall back to a standard burst-only event.
    layer = api_response_1990.layer('RecPreburstTP')
    for row in layer['selected_patterns']:
        if row['Duration'] == 1440 and row['AEP'] == 50.0:
            row['Preburst Depth'] = 0.001
    config = make_config(complete_storm=True,
                          events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is None
    burst_il = engine._initial_loss(1440, '50%', [1440])
    assert r.initial_loss == pytest.approx(burst_il)


def test_engine_drops_negligible_preburst_for_placeholder_cell_uses_storm_il(api_response_1990):
    # 20%/1440min is a 'Use PB TP' placeholder cell (no fixed burst initial loss) - if
    # its preburst depth is also negligible, the engine should fall back to the full
    # storm initial loss (since no burst initial loss is available to fall back to).
    layer = api_response_1990.layer('RecPreburstTP')
    for row in layer['selected_patterns']:
        if row['Duration'] == 1440 and row['AEP'] == 20.0:
            row['Preburst Depth'] = 0.001
    config = make_config(events={'aep': ['20%'], 'duration': [1440], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is None
    assert r.initial_loss == pytest.approx(engine._storm_initial_loss('20%'))


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


def test_engine_records_extrapolated_losses(api_response_1990):
    config = make_config(
        events={'aep': ['50%'], 'duration': [15, 30], 'output_notation': 'ari'},
        losses={'extrapolation_method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = {r.duration: r for r in engine.run()}
    # only duration=15 (shorter than the shortest datahub duration) should be recorded
    table = engine.extrapolated_loss_table[None]
    assert list(table.index) == [15.0]
    assert 50.0 in table.columns
    assert table.loc[15.0, 50.0] == pytest.approx(results[15.0].initial_loss)


def test_engine_no_extrapolated_losses_when_not_needed(api_response_1990):
    config = make_config(
        events={'aep': ['50%'], 'duration': [30], 'output_notation': 'ari'},
        losses={'extrapolation_method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    engine.run()
    assert engine.extrapolated_loss_table[None].empty


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


def test_engine_climate_change_storm_loss_method(api_response_1990):
    """When losses.climate_change_method == 'storm', the climate-change initial loss
    should be derived from the climate-change-scaled *storm* initial loss minus a
    climate-change preburst depth (climate-change rainfall x preburst ratio), rather
    than simply scaling the (baseline) burst initial loss by the climate change
    factor."""
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
        losses={'climate_change_method': 'storm'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    cc = next(r for r in results if r.cc_scenario == '2090_SSP2')

    from pytuflow.arr.complete_storm import _preburst_ratio
    from pytuflow.arr.engine import _interp_table

    il_factor, _ = engine._cc_loss_factors(2090, 'SSP2')
    storm_il_cc = engine._storm_initial_loss_pct(50.0) * il_factor
    cc_ifd = engine._ifd_frame(2090, 'SSP2')
    cc_depth = float(_interp_table(cc_ifd, [1440], [50.0]).iloc[0, 0])
    ratio = _preburst_ratio(api_response_1990, '50%', 1440, 50.0)
    expected_il = storm_il_cc - cc_depth * ratio

    assert cc.initial_loss == pytest.approx(expected_il)
    # sanity check it differs from the simple burst-scaling approach
    base = next(r for r in results if r.cc_scenario is None)
    burst_scaled_il = base.initial_loss * il_factor
    assert cc.initial_loss != pytest.approx(burst_scaled_il)


def test_engine_climate_change_burst_is_default(api_response_1990):
    """losses.climate_change_method defaults to 'burst' - unaffected by this change."""
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
    )
    assert config.losses.climate_change_method == 'burst'


def _patch_burst_losses_new(api_response_1990, columns, index, data):
    api_response_1990.layers['BurstLossesNew'] = {'columns': columns, 'index': index, 'data': data}


def test_engine_placeholder_adjacent_gap_positive_uses_derived_burst_loss(api_response_1990):
    # duration=120 falls between a numeric cell (60min) and a 'Use PB TP' placeholder
    # (180min) for AEP 50% - the implied burst initial loss (storm initial loss minus
    # the interpolated preburst depth) is positive with the real fixture data, so it
    # should be used directly rather than triggering complete storm.
    _patch_burst_losses_new(api_response_1990, [50.0], [60, 180], [[10.0], ['Use PB TP']])
    config = make_config(events={'aep': ['50%'], 'duration': [120], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is None

    from pytuflow.arr.complete_storm import _preburst_ratio
    from pytuflow.arr.engine import _interp_table, _table_to_frame
    rec_ifd = api_response_1990.layer('RecIFD')
    ifd_df = _table_to_frame(rec_ifd['Recommended Historical (1961-1990) Baseline'])
    point_depth = float(_interp_table(ifd_df, [120], [50.0]).iloc[0, 0])
    ratio = _preburst_ratio(api_response_1990, '50%', 120, 50.0)
    expected = 20.0 - ratio * point_depth
    assert expected > 0
    assert r.initial_loss == pytest.approx(expected)


def test_engine_placeholder_adjacent_gap_negative_triggers_complete_storm(api_response_1990, monkeypatch):
    # gap at duration=180 (bracketed by 60min numeric / 1440min placeholder), with the
    # storm initial loss reduced so far that the implied burst initial loss (storm
    # initial loss minus preburst depth) would be negative - the cell should be treated
    # as 'Use PB TP' too, forcing complete storm. duration=180/AEP 50% has real
    # 'RecPreburstTP' data available, so complete storm assembly can actually proceed.
    _patch_burst_losses_new(api_response_1990, [50.0], [60, 1440], [[10.0], ['Use PB TP']])
    new_losses = api_response_1990.layer('NewStormLosses')
    for row in new_losses['losses']:
        if row['AEP'] == '50%':
            row['Storm Initial Loss (mm)'] = 0.05
    config = make_config(events={'aep': ['50%'], 'duration': [180], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is not None
    assert r.initial_loss == pytest.approx(0.05)


def test_engine_placeholder_adjacent_gap_both_placeholders_triggers_complete_storm(api_response_1990):
    # duration=180 bracketed by two 'Use PB TP' cells (60min and 1440min) - no numeric
    # neighbour to derive anything from, so it should also be 'Use PB TP'.
    _patch_burst_losses_new(api_response_1990, [50.0], [60, 1440], [['Use PB TP'], ['Use PB TP']])
    config = make_config(events={'aep': ['50%'], 'duration': [180], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is not None


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


def test_engine_add_areal_tp_adds_extra_patterns(api_response_1990):
    # catchment_area=150 -> areal TP area bucket 200km2 is used; duration 720min has
    # areal temporal patterns available in both the 200km2 and 500km2 (next closest)
    # buckets in the fixture data.
    config = make_config(
        site={'name': '1', 'latitude': -33.9347, 'longitude': 150.8372, 'catchment_area': 150},
        events={'aep': ['1%'], 'duration': [720], 'output_notation': 'ari'},
        temporal_patterns={'add_areal_tp': 1},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    assert len(results[0].patterns) == 20
    assert {p.group for p in results[0].patterns} == {0, 1}


def test_engine_additional_tp_merges_other_region_patterns(api_response_1990, monkeypatch, point_tp_csv):
    from pytuflow.arr import api_client as api_client_module

    def fake_fetch_point_tp_for_coords(self, lat, lon):
        return {'url': 'https://example.invalid/wet_tropics_point_tp.zip'}, {'title': 'fake wet tropics response'}
    monkeypatch.setattr(api_client_module.ArrApiClient, 'fetch_point_tp_for_coords', fake_fetch_point_tp_for_coords)

    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        temporal_patterns={'additional_tp': ['Wet Tropics']},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    assert len(results[0].patterns) == 20
    regions = {p.region for p in results[0].patterns}
    assert 'Wet Tropics' in regions


def test_engine_user_initial_loss_scales_burst_losses(api_response_1990):
    # Data Hub burst initial loss for 50%/1440min is 14.8mm; Data Hub storm initial
    # loss for 50% is 20mm - user_initial_loss=10 halves the storm loss, so the burst
    # loss should also be halved (7.4mm), preserving the relative reduction shape.
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        losses={'user_initial_loss': 10.0},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    assert results[0].initial_loss == pytest.approx(7.4)


def test_engine_user_initial_loss_used_directly_for_complete_storm(api_response_1990):
    # 20%/1440min is a 'Use PB TP' placeholder cell (auto-triggers complete storm),
    # which uses the full (unreduced) storm initial loss - with user_initial_loss set,
    # that should be the user value directly, not a Data Hub value.
    config = make_config(
        events={'aep': ['20%'], 'duration': [1440], 'output_notation': 'ari'},
        losses={'user_initial_loss': 99.0},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    assert results[0].initial_loss == pytest.approx(99.0)


def test_engine_user_continuing_loss_overrides_storm_continuing_loss(api_response_1990):
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        losses={'user_continuing_loss': 5.0},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    assert results[0].continuing_loss == pytest.approx(5.0)


def test_engine_uses_local_point_tp_csv(tmp_path, api_response_1990, point_tp_csv):
    point_path = tmp_path / 'point.csv'
    point_path.write_text(point_tp_csv, encoding='utf-8')
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        temporal_patterns={'point_tp_csv': str(point_path)},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    assert results[0].patterns
    tp_set = engine._tp_set_for_config()
    assert tp_set.point_tp_csv == point_tp_csv.replace('\r\n', '\n')


def test_engine_uses_local_point_and_areal_tp_csv(tmp_path, api_response_1990, point_tp_csv, areal_tp_csv):
    point_path = tmp_path / 'point.csv'
    point_path.write_text(point_tp_csv, encoding='utf-8')
    areal_path = tmp_path / 'areal.csv'
    areal_path.write_text(areal_tp_csv, encoding='utf-8')
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        temporal_patterns={'point_tp_csv': str(point_path), 'areal_tp_csv': str(areal_path)},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    tp_set = engine._tp_set_for_config()
    assert tp_set.areal_tp_csv == areal_tp_csv.replace('\r\n', '\n')


def test_engine_additional_tp_accepts_local_csv_file(tmp_path, api_response_1990, point_tp_csv):
    prior_output = tmp_path / 'previous_PointTP_Increments.csv'
    prior_output.write_text(point_tp_csv, encoding='utf-8')
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        temporal_patterns={'additional_tp': [str(prior_output)]},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    # both the native region and the file-loaded 'additional' region's patterns should
    # be present (10 native + 10 from the additional file = 20).
    assert len(results[0].patterns) == 20
    assert engine.additional_tp_responses
    region_name, info = next(iter(engine.additional_tp_responses.items()))
    assert info['raw'] is None
    assert info['csv'] == point_tp_csv.replace('\r\n', '\n')


def test_engine_ifd_frame_uses_limb_table_when_source_is_limb(api_response_1990):
    from pytuflow.arr.api_client import ArrApiResponse
    # inject a synthetic 'AllIFDDatasets' layer alongside the cached NSW response's
    # other layers, so only the IFD source dispatch is under test.
    limb_table = {
        'index': [30, 60],
        'columns': [50.0, 20.0, 10.0],
        'data': [[10.0, 20.0, 30.0], [15.0, 25.0, 35.0]],
    }
    data = dict(api_response_1990.raw)
    data['layers'] = dict(data['layers'])
    data['layers']['AllIFDDatasets'] = {'LIMB 2020 IFD Depths - High Resolution': limb_table}
    response = ArrApiResponse(data)

    config = make_config(
        ifd={'source': 'limb', 'year': 2020},
        events={'aep': ['50%'], 'duration': [60], 'output_notation': 'ari'},
    )
    engine = ArrEngine(config, response)
    frame = engine._ifd_frame(2020, None)
    assert frame.loc[60.0, 50.0] == 15.0


def test_engine_ifd_frame_limb_missing_raises(api_response_1990):
    config = make_config(
        ifd={'source': 'limb', 'year': 2020},
        events={'aep': ['50%'], 'duration': [60], 'output_notation': 'ari'},
    )
    engine = ArrEngine(config, api_response_1990)
    with pytest.raises(ArrError, match='AllIFDDatasets'):
        engine._ifd_frame(2020, None)
