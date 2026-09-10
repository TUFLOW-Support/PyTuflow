"""Tests for :mod:`pytuflow.arr.config`."""

from __future__ import annotations

import json

import pytest

from pytuflow.arr.config import ArrConfig
from pytuflow.arr.exceptions import ArrConfigError

VALID_CONFIG = {
    'site': {'name': '1', 'latitude': -33.9347, 'longitude': 150.8372, 'catchment_area': 11.4},
    'ifd': {'source': 'bom', 'year': 1990},
    'events': {'aep': ['1%', '5%'], 'duration': [60, 1440], 'output_notation': 'ari'},
    'output': {'path': '/tmp/out', 'format': 'csv'},
}


def test_valid_config_parses():
    config = ArrConfig.from_dict(VALID_CONFIG)
    assert config.site.name == '1'
    assert config.site.latitude == -33.9347
    assert config.events.aep == ['1%', '5%']
    assert config.events.duration == [60, 1440]
    assert config.ifd.year == 1990
    assert config.output.path == '/tmp/out'


def test_defaults_applied():
    config = ArrConfig.from_dict(VALID_CONFIG)
    assert config.losses.method == 'recommended'
    assert config.arf.min_arf == 0.2
    assert config.complete_storm is False
    assert config.climate_change.enabled is False


def test_missing_required_site_fields_raises():
    bad = json.loads(json.dumps(VALID_CONFIG))
    del bad['site']['latitude']
    with pytest.raises(ArrConfigError, match='latitude'):
        ArrConfig.from_dict(bad)


def test_missing_events_raises():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['events']['aep'] = []
    with pytest.raises(ArrConfigError, match='events.aep'):
        ArrConfig.from_dict(bad)


def test_unknown_top_level_key_raises():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['not_a_real_key'] = 123
    with pytest.raises(ArrConfigError, match='not_a_real_key'):
        ArrConfig.from_dict(bad)


def test_unknown_nested_key_raises():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['site']['not_a_real_key'] = 123
    with pytest.raises(ArrConfigError, match='not_a_real_key'):
        ArrConfig.from_dict(bad)


def test_bad_ifd_year_raises():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['ifd']['year'] = 2050
    with pytest.raises(ArrConfigError, match='ifd.year'):
        ArrConfig.from_dict(bad)


def test_rahman_does_not_require_mar():
    data = json.loads(json.dumps(VALID_CONFIG))
    data['losses'] = {'extrapolation_method': 'rahman'}
    config = ArrConfig.from_dict(data)
    assert config.losses.extrapolation_method == 'rahman'


def test_hill_requires_mar():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['losses'] = {'extrapolation_method': 'hill'}
    with pytest.raises(ArrConfigError, match='losses.mar'):
        ArrConfig.from_dict(bad)


def test_climate_change_method_defaults_to_burst():
    data = json.loads(json.dumps(VALID_CONFIG))
    config = ArrConfig.from_dict(data)
    assert config.losses.climate_change_method == 'burst'


def test_climate_change_method_storm_accepted():
    data = json.loads(json.dumps(VALID_CONFIG))
    data['losses'] = {'climate_change_method': 'storm'}
    config = ArrConfig.from_dict(data)
    assert config.losses.climate_change_method == 'storm'


def test_climate_change_method_invalid_raises():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['losses'] = {'climate_change_method': 'bogus'}
    with pytest.raises(ArrConfigError, match='losses.climate_change_method'):
        ArrConfig.from_dict(bad)


def test_probability_neutral_method_accepted():
    data = json.loads(json.dumps(VALID_CONFIG))
    data['losses'] = {'method': 'probability_neutral'}
    config = ArrConfig.from_dict(data)
    assert config.losses.method == 'probability_neutral'


def test_bad_losses_method_raises():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['losses'] = {'method': 'datahub'}
    with pytest.raises(ArrConfigError, match='losses.method'):
        ArrConfig.from_dict(bad)


def test_climate_change_scenario_validation():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['climate_change'] = {'enabled': True, 'scenarios': [{'baseline_year': 2090, 'ssp': 'SSP2'}]}
    config = ArrConfig.from_dict(bad)
    assert config.climate_change.scenarios[0].baseline_year == 2090
    assert config.climate_change.scenarios[0].ssp == 'SSP2'

    bad['climate_change']['scenarios'][0]['ssp'] = 'RCP4.5'
    with pytest.raises(ArrConfigError, match='ssp'):
        ArrConfig.from_dict(bad)


def test_climate_change_enabled_requires_scenarios():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['climate_change'] = {'enabled': True, 'scenarios': []}
    with pytest.raises(ArrConfigError, match='scenarios'):
        ArrConfig.from_dict(bad)


def test_from_file(tmp_path):
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps(VALID_CONFIG))
    config = ArrConfig.from_file(config_path)
    assert config.site.name == '1'
    assert config.source_path == config_path


def test_from_file_missing_raises(tmp_path):
    with pytest.raises(ArrConfigError, match='not found'):
        ArrConfig.from_file(tmp_path / 'does_not_exist.json')


def test_from_file_bad_json_raises(tmp_path):
    config_path = tmp_path / 'bad.json'
    config_path.write_text('{not valid json')
    with pytest.raises(ArrConfigError, match='Invalid JSON'):
        ArrConfig.from_file(config_path)


def test_urban_losses_must_be_set_together():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['losses'] = {'urban_initial_loss': 10.0}
    with pytest.raises(ArrConfigError, match='urban_initial_loss'):
        ArrConfig.from_dict(bad)


def test_urban_losses_requires_infiltration_method():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['losses'] = {'urban_initial_loss': 10.0, 'urban_continuing_loss': 2.5, 'tuflow_loss_method': 'excess'}
    with pytest.raises(ArrConfigError, match='urban_initial_loss'):
        ArrConfig.from_dict(bad)


def test_urban_losses_valid_when_set_together_with_infiltration():
    data = json.loads(json.dumps(VALID_CONFIG))
    data['losses'] = {'urban_initial_loss': 10.0, 'urban_continuing_loss': 2.5}
    config = ArrConfig.from_dict(data)
    assert config.losses.urban_initial_loss == 10.0
    assert config.losses.urban_continuing_loss == 2.5


def test_use_global_continuing_loss_no_longer_a_field():
    config = ArrConfig.from_dict(VALID_CONFIG)
    assert not hasattr(config.losses, 'use_global_continuing_loss')


def test_point_tp_csv_missing_file_raises():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['temporal_patterns'] = {'point_tp_csv': '/no/such/point.csv'}
    with pytest.raises(ArrConfigError, match='point_tp_csv'):
        ArrConfig.from_dict(bad)


def test_areal_tp_csv_requires_point_tp_csv(tmp_path):
    areal = tmp_path / 'areal.csv'
    areal.write_text('data', encoding='utf-8')
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['temporal_patterns'] = {'areal_tp_csv': str(areal)}
    with pytest.raises(ArrConfigError, match='areal_tp_csv requires'):
        ArrConfig.from_dict(bad)


def test_point_tp_csv_valid_file_accepted(tmp_path):
    point = tmp_path / 'point.csv'
    point.write_text('data', encoding='utf-8')
    data = json.loads(json.dumps(VALID_CONFIG))
    data['temporal_patterns'] = {'point_tp_csv': str(point)}
    config = ArrConfig.from_dict(data)
    assert config.temporal_patterns.point_tp_csv == str(point)


def test_additional_tp_accepts_csv_file_path(tmp_path):
    csv_path = tmp_path / 'previous_PointTP_Increments.csv'
    csv_path.write_text('data', encoding='utf-8')
    data = json.loads(json.dumps(VALID_CONFIG))
    data['temporal_patterns'] = {'additional_tp': [str(csv_path)]}
    config = ArrConfig.from_dict(data)
    assert config.temporal_patterns.additional_tp == [str(csv_path)]


def test_additional_tp_missing_csv_file_raises():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['temporal_patterns'] = {'additional_tp': ['/no/such/file.csv']}
    with pytest.raises(ArrConfigError, match='additional_tp CSV file not found'):
        ArrConfig.from_dict(bad)


def test_additional_tp_bad_entry_raises():
    bad = json.loads(json.dumps(VALID_CONFIG))
    bad['temporal_patterns'] = {'additional_tp': ['nowhere']}
    with pytest.raises(ArrConfigError, match='not a recognised region name'):
        ArrConfig.from_dict(bad)
