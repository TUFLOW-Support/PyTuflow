"""Tests for :mod:`pytuflow.arr.temporal_patterns`, using cached real Data Hub zip
downloads (``tests/arr/fixtures/point_tp.zip``/``areal_tp.zip``) rather than live
network access.
"""

from __future__ import annotations

import pytest

from pytuflow.arr.temporal_patterns import (
    TemporalPatternSet,
    aep_band,
    nearest_areal_tp_area,
    parse_areal_tp_csv,
    parse_point_tp_csv,
)


@pytest.mark.parametrize('aep_name, expected', [
    ('0.5EY', 'frequent'),
    ('20%', 'frequent'),
    ('50%', 'frequent'),
    ('14.4%', 'intermediate'),
    ('10%', 'intermediate'),
    ('3.2%', 'rare'),
    ('1%', 'rare'),
    ('0.5%', 'rare'),
    ('1 in 200', 'rare'),
    ('1 in 2000', 'rare'),
])
def test_aep_band(aep_name, expected):
    assert aep_band(aep_name) == expected


def test_aep_band_very_rare_warns(caplog):
    import logging
    with caplog.at_level(logging.WARNING):
        band = aep_band('1 in 5000')
    assert band == 'rare'
    assert 'Very Rare' in caplog.text


@pytest.mark.parametrize('area, expected', [
    (10, None), (50, None), (75, 100), (150, 200), (500, 500), (600, 1000),
    (40000, 40000), (100000, 40000),
])
def test_nearest_areal_tp_area(area, expected):
    assert nearest_areal_tp_area(area) == expected


def test_nearest_areal_tp_area_below_minimum_is_none():
    assert nearest_areal_tp_area(50) is None


def test_parse_point_tp_csv(point_tp_csv):
    df = parse_point_tp_csv(point_tp_csv)
    assert set(df.columns) >= {'event_id', 'duration', 'timestep', 'region', 'aep_band', 'tp_number', 'increments'}
    assert len(df) > 0
    # every group of (duration, aep_band) should have exactly 10 realizations, numbered 1-10
    counts = df.groupby(['duration', 'aep_band'])['tp_number'].apply(list)
    for tp_numbers in counts:
        assert sorted(tp_numbers) == list(range(1, 11))
    # increments for a pattern should sum to ~100%
    for incr in df['increments'].head(20):
        assert sum(incr) == pytest.approx(100.0, abs=0.5)


def test_parse_areal_tp_csv(areal_tp_csv):
    df = parse_areal_tp_csv(areal_tp_csv)
    assert set(df.columns) >= {'event_id', 'duration', 'timestep', 'region', 'area', 'tp_number', 'increments'}
    assert len(df) > 0
    assert set(df['area'].unique()) <= {100, 200, 500, 1000, 2500, 5000, 10000, 20000, 40000}
    for incr in df['increments'].head(20):
        assert sum(incr) == pytest.approx(100.0, abs=0.5)


def test_temporal_pattern_set_areal_preferred_within_area(point_tp_csv, areal_tp_csv):
    point_df = parse_point_tp_csv(point_tp_csv)
    areal_df = parse_areal_tp_csv(areal_tp_csv)
    tps = TemporalPatternSet(point_df, areal_df, catchment_area=150)
    assert tps.tp_area == 200
    patterns = tps.patterns(720, '1%')
    assert len(patterns) == 10
    assert patterns[0].source == 'areal'


def test_temporal_pattern_set_falls_back_to_point_below_areal_min_duration(point_tp_csv, areal_tp_csv):
    point_df = parse_point_tp_csv(point_tp_csv)
    areal_df = parse_areal_tp_csv(areal_tp_csv)
    tps = TemporalPatternSet(point_df, areal_df, catchment_area=150)
    short_duration = int(point_df['duration'].min())
    patterns = tps.patterns(short_duration, '50%')
    assert all(p.source == 'point' for p in patterns)


def test_temporal_pattern_set_no_areal_data_uses_point_only(point_tp_csv):
    point_df = parse_point_tp_csv(point_tp_csv)
    tps = TemporalPatternSet(point_df, areal_tp=None, catchment_area=150)
    patterns = tps.patterns(720, '1%')
    assert all(p.source == 'point' for p in patterns)


def test_temporal_pattern_set_no_catchment_area_uses_point_only(point_tp_csv, areal_tp_csv):
    point_df = parse_point_tp_csv(point_tp_csv)
    areal_df = parse_areal_tp_csv(areal_tp_csv)
    tps = TemporalPatternSet(point_df, areal_df, catchment_area=None)
    patterns = tps.patterns(720, '1%')
    assert all(p.source == 'point' for p in patterns)
