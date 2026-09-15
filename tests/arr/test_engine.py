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
    'ifd': {'baseline_year': 1990},
    'output': {'path': '/tmp/unused', 'format': 'csv'},
}

#: A non-NSW (South East Queensland) site - its cached ARR Data Hub response
#: (`api_response_seq`) has no `BurstLossesNew`/`NewStormLosses`/`RecPreburstTP`/
#: `RecPreburst` layers at all (all NSW-only), unlike `SITE_CONFIG`'s NSW site.
SITE_CONFIG_SEQ = {
    'site': {'name': 'seq', 'latitude': -27.389, 'longitude': 152.858, 'catchment_area': 5.0},
    'ifd': {'baseline_year': 2030},
    'output': {'path': '/tmp/unused', 'format': 'csv'},
}


def make_config_seq(**overrides) -> ArrConfig:
    data = {**SITE_CONFIG_SEQ, **overrides}
    return ArrConfig.from_dict(data)


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
    # force the preburst ratio (from the Preburst50 table) for 50%/1440min to a
    # negligible value - the engine should drop the preburst period and fall back to a
    # standard burst-only event. preburst.percentile is pinned to '50%' here (rather
    # than relying on the 'recommended' default) so the Preburst50 monkeypatch below is
    # actually used to derive the ratio.
    layer = api_response_1990.layer('Preburst50')
    idx = layer['index'].index(1440)
    col = layer['columns'].index(50.0)
    layer['data'][idx][col] = 0.00001
    config = make_config(complete_storm=True,
                          events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
                          preburst={'percentile': '50%'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is None
    burst_il = engine._initial_loss(1440, '50%', [1440])
    assert r.initial_loss == pytest.approx(burst_il)


def test_engine_drops_negligible_preburst_for_placeholder_cell_uses_storm_il(api_response_1990):
    # 20%/1440min is a 'Use PB TP' placeholder cell (no fixed burst initial loss) - if
    # its preburst ratio (from the Preburst50 table) is also negligible, the burst
    # initial loss recalculated from the preburst ratio (storm_il - ratio * point_depth)
    # should be very close to (but not necessarily bit-for-bit equal to) the full storm
    # initial loss. preburst.percentile is pinned to '50%' here (rather than relying on
    # the 'recommended' default) so the Preburst50 monkeypatch below is actually used to
    # derive the ratio.
    from pytuflow.arr.complete_storm import _preburst_ratio
    from pytuflow.arr.engine import _interp_table, _table_to_frame

    layer = api_response_1990.layer('Preburst50')
    idx = layer['index'].index(1440)
    col = layer['columns'].index(20.0)
    layer['data'][idx][col] = 0.00001
    config = make_config(events={'aep': ['20%'], 'duration': [1440], 'output_notation': 'ari'},
                          preburst={'percentile': '50%'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is None

    baseline_ifd = engine._ifd_frame(1990, None)
    point_depth = float(_interp_table(baseline_ifd, [1440.0], [20.0]).iloc[0, 0])
    ratio = _preburst_ratio(api_response_1990, '50%', 1440.0, 20.0)
    storm_il = engine._storm_initial_loss('20%')
    expected = storm_il - ratio * point_depth
    assert expected == pytest.approx(storm_il, abs=5e-3)  # negligible ratio -> nearly the full storm IL
    assert r.initial_loss == pytest.approx(expected)


def test_initial_loss_extrapolates_for_aep_rarer_than_table(api_response_1990):
    # BurstLossesNew/NewStormLosses are both limited to 50%-1% AEP - 0.5% AEP has no
    # burst/storm initial loss data in the Data Hub at all. The burst initial loss
    # should be derived by holding the preburst ratio constant at the 1% AEP edge
    # (the RecPreburst layer's rarest column - preburst.percentile defaults to
    # 'recommended') and applying it against the *actual* (not clamped) point design
    # depth at 0.5% AEP - holding NewStormLosses' own rarest (1%) row's storm initial
    # loss constant too, rather than falling back to the non-AEP-specific
    # 'StormLosses' scalar.
    engine = ArrEngine(
        make_config(events={'aep': ['0.5%'], 'duration': [1440], 'output_notation': 'ari'}),
        api_response_1990,
    )
    value = engine._initial_loss(1440, '0.5%', [1440])
    # RecPreburst ratio at (1440min, 1% AEP, the rarest available column) == 0.359;
    # point depth at (1440min, 0.5% AEP) from the 1990 baseline IFD table == 325.0;
    # storm initial loss holds NewStormLosses' own 1% AEP row constant == 20.0.
    assert value == pytest.approx(20.0 - 0.359 * 325.0)


def test_initial_loss_does_not_extrapolate_for_aep_within_table(api_response_1990):
    # sanity check - 2% AEP (well within the table's 50%-1% range) should NOT trigger
    # the new rare-AEP extrapolation path, and should still return the Data Hub's own
    # value.
    engine = ArrEngine(
        make_config(events={'aep': ['2%'], 'duration': [30], 'output_notation': 'ari'}),
        api_response_1990,
    )
    burst_losses = engine._burst_loss_frame()
    expected = float(burst_losses.loc[30, 2.0])
    value = engine._initial_loss(30, '2%', [30])
    assert value == pytest.approx(expected)


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


def test_engine_constant_preburst_ratio_is_default(api_response_1990):
    # extrapolation_method defaults to 'constant_preburst_ratio' - a duration shorter
    # than the Data Hub's shortest provided duration should extrapolate automatically
    # without needing to set losses.extrapolation_method explicitly.
    config = make_config(events={'aep': ['50%'], 'duration': [15, 30], 'output_notation': 'ari'})
    assert config.losses.extrapolation_method == 'constant_preburst_ratio'
    engine = ArrEngine(config, api_response_1990)
    results = {r.duration: r for r in engine.run()}
    assert results[15.0].initial_loss > 0
    assert results[15.0].initial_loss != results[30.0].initial_loss


def test_engine_constant_preburst_ratio_matches_implied_ratio(api_response_1990):
    # verify the extrapolated 15min loss reproduces the ratio implied at the reference
    # (threshold) duration, applied to the 15min point design burst depth.
    config = make_config(
        events={'aep': ['50%'], 'duration': [15, 30], 'output_notation': 'ari'},
        losses={'extrapolation_method': 'constant_preburst_ratio'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = {r.duration: r for r in engine.run()}

    storm_il = engine._storm_initial_loss_pct_datahub(50.0)
    threshold_loss = engine._initial_loss(30, '50%', [15, 30])
    point_depths = engine._point_depths_for_preburst_ratio([15, 30], 30.0, [50.0])
    ratio = (storm_il - threshold_loss) / float(point_depths.loc[30.0, 50.0])
    expected_15min_loss = storm_il - ratio * float(point_depths.loc[15.0, 50.0])
    assert results[15.0].initial_loss == pytest.approx(expected_15min_loss)


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


def test_engine_run_extrapolates_rare_aep_and_records_it(api_response_1990):
    # 0.5% AEP is rarer than the burst/storm loss tables' rarest (1%) column - the
    # engine should still assemble the event (rather than raising or silently reusing
    # the 1% column's raw value), and record it in extrapolated_loss_table alongside
    # any short-duration extrapolations. The storm initial loss holds NewStormLosses'
    # own rarest (1%) row constant (20.0), rather than falling back to the
    # non-AEP-specific 'StormLosses' scalar.
    config = make_config(events={'aep': ['0.5%'], 'duration': [1440], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.initial_loss == pytest.approx(20.0 - 0.359 * 325.0)
    table = engine.extrapolated_loss_table[None]
    assert list(table.index) == [1440.0]
    assert 0.5 in table.columns
    assert table.loc[1440.0, 0.5] == pytest.approx(r.initial_loss)


def test_engine_run_extrapolates_frequent_aep_and_records_it(api_response_1990):
    # 63.2% AEP (1 EY) is more frequent than the burst/storm loss tables' most frequent
    # (50%) column - mirroring the rare-AEP side, the engine should still assemble the
    # event via the preburst-ratio formula (rather than silently reusing the 50%
    # column's raw value unchanged), and record it in extrapolated_loss_table. The
    # storm initial loss holds NewStormLosses' own most frequent (50%) row constant
    # (20.0), rather than falling back to the non-AEP-specific 'StormLosses' scalar.
    config = make_config(events={'aep': ['1EY'], 'duration': [1440], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.initial_loss == pytest.approx(20.0 - 0.048 * 85.2)
    table = engine.extrapolated_loss_table[None]
    assert list(table.index) == [1440.0]
    assert 63.21 in table.columns
    assert table.loc[1440.0, 63.21] == pytest.approx(r.initial_loss)


def test_storm_initial_loss_datahub_holds_edge_row_constant_not_generic_fallback(api_response_1990):
    # give NewStormLosses' rows distinct (non-flat) values so the edge-row-held-
    # constant behaviour is unambiguously distinguishable from the generic
    # 'StormLosses' scalar fallback.
    new_losses = api_response_1990.layer('NewStormLosses')
    values = {'1%': 15.0, '2%': 16.0, '5%': 17.0, '10%': 18.0, '20%': 19.0, '50%': 20.0}
    for row in new_losses['losses']:
        row['Storm Initial Loss (mm)'] = values[row['AEP']]
    engine = ArrEngine(
        make_config(events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'}),
        api_response_1990,
    )
    # rarer than NewStormLosses' rarest (1%) row -> holds the 1% row (15.0) constant
    assert engine._storm_initial_loss_pct_datahub(0.5) == pytest.approx(15.0)
    # more frequent than NewStormLosses' most frequent (50%) row -> holds the 50% row
    # (20.0) constant
    assert engine._storm_initial_loss_pct_datahub(63.21) == pytest.approx(20.0)
    # an exact match is still used directly, regardless of the edge logic
    assert engine._storm_initial_loss_pct_datahub(5.0) == pytest.approx(17.0)
    # an AEP strictly within NewStormLosses' own range but not one of its rows (an
    # interior gap, not an edge) still falls back to the generic 'StormLosses' scalar
    assert engine._storm_initial_loss_pct_datahub(3.0) == pytest.approx(66.0)


def test_engine_applies_climate_change_loss_factors(api_response_1990, monkeypatch):
    """Climate change scenario events should have their initial/continuing loss scaled
    by the Data Hub's 'ClimateChange' loss adjustment factors, relative to the base
    (no climate change) event, when losses.climate_change_method == 'burst' (the
    'storm' method - now the default - is covered separately by
    test_engine_climate_change_storm_loss_method)."""
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
        losses={'climate_change_method': 'burst'},
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


def test_engine_climate_change_storm_is_default(api_response_1990):
    """losses.climate_change_method defaults to 'storm'."""
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
    )
    assert config.losses.climate_change_method == 'storm'


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


def test_engine_placeholder_adjacent_gap_both_placeholders_derives_burst_loss(api_response_1990):
    # duration=180 bracketed by two 'Use PB TP' cells (60min and 1440min) - unlike the
    # old neighbour-interpolation approach (which had no numeric neighbour to derive
    # anything from here), the burst initial loss is now always derived directly from
    # the storm initial loss and the (log-log interpolated) preburst depth at the
    # requested duration, regardless of the neighbouring cells' placeholder status - so
    # this should resolve to a positive derived value rather than 'Use PB TP'.
    _patch_burst_losses_new(api_response_1990, [50.0], [60, 1440], [['Use PB TP'], ['Use PB TP']])
    config = make_config(events={'aep': ['50%'], 'duration': [180], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is None
    assert r.initial_loss == pytest.approx(19.5171, abs=1e-3)


def test_engine_probability_neutral_method_uses_burst_il_layer(api_response_1990):
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        ifd={'baseline_year': 2030},  # avoid the ifd.baseline_year != 2030 burst loss recalculation
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


def test_engine_probability_neutral_does_not_recompute_for_non_2030_ifd_year(api_response_1990):
    # unlike BurstLossesNew ('recommended'), BurstIL ('probability_neutral') is an
    # independently-calibrated NSW table with no relationship to preburst ratios or
    # any specific IFD baseline year - the raw table value should be used as-is even
    # when ifd.baseline_year != 2030 (no preburst-ratio-based recalculation should occur).
    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        ifd={'baseline_year': 1990},
        losses={'method': 'probability_neutral'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    expected = api_response_1990.layer('BurstIL')['data'][7][0]  # duration 1440, aep '50.0'
    assert results[0].initial_loss == pytest.approx(expected)


def test_engine_probability_neutral_uses_plain_linear_interpolation_for_missing_duration(api_response_1990):
    # unlike BurstLossesNew's preburst-ratio-based gap-fill, BurstIL interior duration
    # gaps should use plain linear interpolation on the raw table values (matching the
    # legacy script), since BurstIL is not preburst-derived.
    burst_il = api_response_1990.layer('BurstIL')
    burst_il['index'] = [60, 1440]
    burst_il['data'] = [[31.6], [47.9]]
    burst_il['columns'] = [50.0]
    config = make_config(
        events={'aep': ['50%'], 'duration': [120], 'output_notation': 'ari'},
        ifd={'baseline_year': 2030},
        losses={'method': 'probability_neutral'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    # plain linear interpolation between (60, 31.6) and (1440, 47.9) at duration=120
    expected = 31.6 + (47.9 - 31.6) * (120 - 60) / (1440 - 60)
    assert results[0].initial_loss == pytest.approx(expected)


def test_engine_probability_neutral_extrapolation_holds_nearest_aep_column_constant(api_response_1990):
    # AEPs rarer than BurstIL's rarest (1%) column should hold that column's raw loss
    # value constant, rather than extrapolating via preburst ratio (which is
    # meaningless for BurstIL - see _burst_loss_frame/_extrapolate_edge_aep_loss).
    config = make_config(
        events={'aep': ['0.5%'], 'duration': [1440], 'output_notation': 'ari'},
        ifd={'baseline_year': 2030},
        losses={'method': 'probability_neutral'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    expected = api_response_1990.layer('BurstIL')['data'][7][-1]  # duration 1440, aep '1.0'
    assert results[0].initial_loss == pytest.approx(expected)


def test_engine_probability_neutral_extrapolation_holds_most_frequent_aep_column_constant(api_response_1990):
    # mirroring the rare-AEP side, an AEP more frequent than BurstIL's most frequent
    # (50%) column should hold that column's raw loss value constant.
    config = make_config(
        events={'aep': ['1EY'], 'duration': [1440], 'output_notation': 'ari'},
        ifd={'baseline_year': 2030},
        losses={'method': 'probability_neutral'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1
    expected = api_response_1990.layer('BurstIL')['data'][7][0]  # duration 1440, aep '50.0'
    assert results[0].initial_loss == pytest.approx(expected)


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
    # Burst initial loss for 50%/1440min is always recalculated from the preburst
    # ratio (storm_il - preburst_ratio * point_depth), regardless of baseline year -
    # Data Hub storm initial loss for 50% is 20mm - user_initial_loss=10 halves the
    # storm loss, so the (recalculated) burst loss should also be halved, preserving
    # the relative reduction shape.
    from pytuflow.arr.complete_storm import _preburst_ratio
    from pytuflow.arr.engine import _interp_table, _table_to_frame

    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        ifd={'baseline_year': 2030},
        losses={'user_initial_loss': 10.0},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1

    baseline_ifd = _table_to_frame(api_response_1990.ifd_table(2030))
    point_depth = float(_interp_table(baseline_ifd, [1440.0], [50.0]).iloc[0, 0])
    ratio = _preburst_ratio(api_response_1990, '50%', 1440.0, 50.0)
    storm_il = 20.0  # Data Hub storm initial loss for 50% AEP
    expected_full_burst_il = storm_il - ratio * point_depth
    assert results[0].initial_loss == pytest.approx(expected_full_burst_il / 2)


def test_engine_recalculates_burst_losses_for_non_2030_ifd_year(api_response_1990):
    # BurstLossesNew/BurstIL are only ever computed by the Data Hub against its own
    # recommended preburst percentile and the 2030 ("current") baseline - every numeric
    # burst initial loss cell is always recalculated as
    # storm_il - preburst_ratio(percentile, duration, aep) * point_depth(ifd.baseline_year),
    # using the configured percentile/baseline year, rather than the Data Hub's raw
    # value being used unmodified. This test exercises a non-2030 baseline year.
    from pytuflow.arr.complete_storm import _preburst_ratio
    from pytuflow.arr.engine import _interp_table, _table_to_frame

    config = make_config(
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        ifd={'baseline_year': 1990},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert len(results) == 1

    baseline_ifd = _table_to_frame(api_response_1990.ifd_table(1990))
    point_depth = float(_interp_table(baseline_ifd, [1440.0], [50.0]).iloc[0, 0])
    ratio = _preburst_ratio(api_response_1990, '50%', 1440.0, 50.0)
    storm_il = 20.0  # Data Hub storm initial loss for 50% AEP
    expected = storm_il - ratio * point_depth
    # sanity check: differs from the raw (2030-based) BurstLossesNew value of 14.8mm
    assert expected != pytest.approx(14.8)
    assert results[0].initial_loss == pytest.approx(expected)


def test_engine_burst_loss_recalculated_at_2030_baseline_for_configured_percentile(api_response_1990):
    # Even at the default `ifd.baseline_year=2030`, `BurstLossesNew`'s raw numeric
    # value (14.8mm for 50%/1440min) is only ever consistent with the Data Hub's own
    # *recommended* preburst percentile - it must always be recalculated against the
    # *configured* `preburst.percentile`, so different percentiles give different
    # results (and neither necessarily matches the raw 14.8mm value), and the
    # complete-storm trigger stays consistent with whichever percentile is chosen.
    from pytuflow.arr.complete_storm import _preburst_ratio
    from pytuflow.arr.engine import _interp_table, _table_to_frame

    baseline_ifd = _table_to_frame(api_response_1990.ifd_table(2030))
    point_depth = float(_interp_table(baseline_ifd, [1440.0], [50.0]).iloc[0, 0])
    storm_il = 20.0  # Data Hub storm initial loss for 50% AEP

    results_by_percentile = {}
    for percentile in ('10%', '50%', '90%'):
        config = make_config(
            events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
            ifd={'baseline_year': 2030},
            preburst={'percentile': percentile},
        )
        engine = ArrEngine(config, api_response_1990)
        results = engine.run()
        assert len(results) == 1
        ratio = _preburst_ratio(api_response_1990, percentile, 1440.0, 50.0)
        expected = storm_il - ratio * point_depth
        if expected < 0:
            # negative recalculated burst loss -> 'Use PB TP' placeholder -> complete
            # storm assembly triggered -> full (unreduced) storm initial loss used
            expected = storm_il
        assert results[0].initial_loss == pytest.approx(expected)
        results_by_percentile[percentile] = results[0].initial_loss

    # different percentiles must give different results here: 50% recalculates to a
    # positive numeric burst loss, while 90% (a much larger preburst ratio) pushes the
    # recalculated value negative, triggering complete storm assembly (full storm IL)
    assert results_by_percentile['50%'] != pytest.approx(results_by_percentile['90%'])
    assert results_by_percentile['50%'] != pytest.approx(14.8)  # raw BurstLossesNew value


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
    # newline='' - point_tp_csv already contains literal '\r\n' line endings (from the
    # cached zip fixture); without this, write_text()'s universal-newline translation
    # would double them up on Windows (os.linesep == '\r\n'), producing spurious blank
    # lines when the file is read back.
    point_path.write_text(point_tp_csv, encoding='utf-8', newline='')
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
    point_path.write_text(point_tp_csv, encoding='utf-8', newline='')
    areal_path = tmp_path / 'areal.csv'
    areal_path.write_text(areal_tp_csv, encoding='utf-8', newline='')
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
    prior_output.write_text(point_tp_csv, encoding='utf-8', newline='')
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


# --- South East Queensland (non-NSW) tests -----------------------------------------
# These use `api_response_seq`, a cached real Data Hub response for a location with no
# BurstLossesNew/NewStormLosses/RecPreburstTP/RecPreburst layers at all (all NSW-only).

def test_engine_seq_storm_losses_fall_back_to_non_nsw_layer(api_response_seq):
    config = make_config_seq(events={'aep': ['1%'], 'duration': [60], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_seq)
    assert engine._storm_continuing_loss('1%') == pytest.approx(2.1)
    assert engine._storm_initial_loss_pct_datahub(1.0) == pytest.approx(14.0)


def test_engine_seq_missing_burst_loss_table_does_not_crash(api_response_seq):
    # no 'BurstLossesNew' layer at all for this location - the engine should not raise,
    # and should automatically fall back to complete storm assembly (using the
    # pattern_duration/pattern_tp defaults, since 'RecPreburstTP' is also absent) rather
    # than crashing.
    config = make_config_seq(events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_seq)
    results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is not None
    assert r.preburst.method == 'temporal_pattern'
    assert r.initial_loss > 0


def test_engine_seq_pattern_method_none_zeroes_burst_loss_instead_of_crashing(api_response_seq, caplog):
    config = make_config_seq(
        events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
        preburst={'pattern_method': 'none'},
    )
    engine = ArrEngine(config, api_response_seq)
    with caplog.at_level('WARNING'):
        results = engine.run()
    assert len(results) == 1
    r = results[0]
    assert r.preburst is None
    assert r.initial_loss == 0.0
    assert any("pattern_method == 'none'" in rec.message for rec in caplog.records)


def test_engine_seq_recommended_fallback_uses_pattern_duration_defaults(api_response_seq):
    # 'RecPreburstTP' is absent entirely (NSW-only) - build_preburst should fall back to
    # the (defaulted) pattern_duration=2/pattern_tp='TP01'/duration_proportional=True
    # temporal_pattern_preburst method.
    from pytuflow.arr.complete_storm import build_preburst, temporal_pattern_preburst
    config = make_config_seq(events={'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'})
    engine = ArrEngine(config, api_response_seq)
    tp_set = engine._tp_set_for_config()
    pattern = build_preburst(api_response_seq, config, tp_set, 1440, '1%', 1.0, 200.0)
    assert pattern.method == 'temporal_pattern'
    expected = temporal_pattern_preburst(api_response_seq, config, tp_set, 1440, '1%', 1.0, 200.0)
    assert pattern.increments == expected.increments
    assert pattern.timestep == pytest.approx(expected.timestep)


def test_engine_seq_percentile_recommended_falls_back_to_50_percent(api_response_seq, caplog):
    # 'RecPreburst' is absent entirely (NSW-only) - preburst.percentile == 'recommended'
    # should automatically fall back to the 'Preburst50' layer instead of raising.
    from pytuflow.arr.complete_storm import _preburst_ratio
    with caplog.at_level('WARNING'):
        ratio = _preburst_ratio(api_response_seq, 'recommended', 60, 1.0)
    expected = _preburst_ratio(api_response_seq, '50%', 60, 1.0)
    assert ratio == pytest.approx(expected)
    assert any('RecPreburst' in rec.message for rec in caplog.records)


def test_interp_table_uses_true_log_log_interpolation():
    # a synthetic table with values that are an exact power-law function of duration
    # and AEP (i.e. linear in log10(duration)/log10(aep)/log10(value) space) should be
    # interpolated exactly by true log-log interpolation - a plain log-x/linear-y
    # (semi-log) interpolation of the same table would NOT reproduce these values
    # exactly, so this also guards against regressing to the old semi-log behaviour.
    import pandas as pd

    from pytuflow.arr.engine import _interp_table

    durations = [60.0, 180.0, 360.0]
    aeps = [1.0, 10.0]
    # value = duration ** -0.3 * aep ** 0.5 (a pure power-law surface)
    data = [[d ** -0.3 * a ** 0.5 for a in aeps] for d in durations]
    df = pd.DataFrame(data, index=durations, columns=aeps)

    # interpolate at a duration/AEP not on the grid, in the interior of both axes
    out = _interp_table(df, [120.0], [3.0])
    expected = 120.0 ** -0.3 * 3.0 ** 0.5
    assert float(out.iloc[0, 0]) == pytest.approx(expected, rel=1e-9)

    # an exact grid match should return the literal table value, bypassing interpolation
    out_exact = _interp_table(df, [180.0], [10.0])
    assert float(out_exact.iloc[0, 0]) == pytest.approx(df.loc[180.0, 10.0], rel=1e-12)


def test_interp_table_handles_zero_values_without_error():
    # a table containing a literal 0.0 (e.g. a preburst ratio table's long-duration
    # entries) must not raise/produce nan/inf, and an exact match on the zero cell
    # itself must return exactly 0.0 (not the internal log-floor value).
    import numpy as np
    import pandas as pd

    from pytuflow.arr.engine import _interp_table

    durations = [60.0, 180.0, 360.0]
    aeps = [1.0, 10.0]
    df = pd.DataFrame(
        [[0.9, 0.5], [0.6, 0.3], [0.0, 0.1]], index=durations, columns=aeps
    )

    # exact match on the zero cell
    out_exact = _interp_table(df, [360.0], [1.0])
    assert float(out_exact.iloc[0, 0]) == 0.0

    # interpolating near the zero cell should be finite and small, not nan/inf
    out_interp = _interp_table(df, [270.0], [1.0])
    value = float(out_interp.iloc[0, 0])
    assert np.isfinite(value)
    assert 0 <= value < 0.6
