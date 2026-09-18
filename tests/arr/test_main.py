"""Tests for :mod:`pytuflow.arr.__main__` (CLI entry point)."""

from __future__ import annotations

import json

import pytest

from pytuflow.arr import temporal_patterns as tp_module
from pytuflow.arr.__main__ import _load_response, run
from pytuflow.arr.api_client import ArrApiClient
from pytuflow.arr.config import ArrConfig
from pytuflow.arr.exceptions import ArrError


@pytest.fixture(autouse=True)
def mock_tp_downloads(monkeypatch, point_tp_csv, areal_tp_csv):
    def fake_download(url: str) -> str:
        if 'Areal' in url:
            return areal_tp_csv
        return point_tp_csv
    monkeypatch.setattr(tp_module, '_download_increments_csv', fake_download)


def make_config_dict(tmp_path, response_json_path=None):
    data = {
        'site': {'name': '1', 'latitude': -33.9347, 'longitude': 150.8372, 'catchment_area': 11.4},
        'ifd': {'baseline_year': 1990},
        'events': {'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        'output': {'path': str(tmp_path), 'format': 'csv'},
    }
    if response_json_path is not None:
        data['response_json'] = str(response_json_path)
    return data


def test_load_response_uses_local_file_when_set(tmp_path, api_response_1990, monkeypatch):
    response_path = tmp_path / 'response.json'
    with open(response_path, 'w', encoding='utf-8') as f:
        json.dump(api_response_1990.raw, f)
    config = ArrConfig.from_dict(make_config_dict(tmp_path, response_path))

    def fail_fetch(self, config):
        raise AssertionError('client.fetch should not be called when response_json is set')
    monkeypatch.setattr(ArrApiClient, 'fetch', fail_fetch)

    client = ArrApiClient()
    response = _load_response(client, config)
    assert response.title == api_response_1990.title


def test_load_response_bad_json_raises(tmp_path):
    response_path = tmp_path / 'response.json'
    response_path.write_text('not valid json', encoding='utf-8')
    config = ArrConfig.from_dict(make_config_dict(tmp_path, response_path))
    client = ArrApiClient()
    with pytest.raises(ArrError, match='not valid JSON'):
        _load_response(client, config)


def test_run_end_to_end_with_local_response_json(tmp_path, api_response_1990, monkeypatch):
    response_path = tmp_path / 'response.json'
    with open(response_path, 'w', encoding='utf-8') as f:
        json.dump(api_response_1990.raw, f)
    config_path = tmp_path / 'config.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(make_config_dict(tmp_path, response_path), f)

    def fail_fetch(self, config):
        raise AssertionError('client.fetch should not be called when response_json is set')
    monkeypatch.setattr(ArrApiClient, 'fetch', fail_fetch)

    exit_code = run([str(config_path)])
    assert exit_code == 0
    assert (tmp_path / 'Event_File.tef').exists()
    assert (tmp_path / 'bc_dbase.csv').exists()


def test_run_multiple_configs_only_site_overridden(tmp_path, api_response_1990, monkeypatch, caplog):
    """When multiple config files are given, only 'site' may differ between them -
    every other setting (including response_json) comes from the first config file,
    regardless of what a later file specifies for those keys."""
    response_path = tmp_path / 'response.json'
    with open(response_path, 'w', encoding='utf-8') as f:
        json.dump(api_response_1990.raw, f)

    config_a = make_config_dict(tmp_path, response_path)
    path_a = tmp_path / 'a.json'
    with open(path_a, 'w', encoding='utf-8') as f:
        json.dump(config_a, f)

    # 'site' differs (a second catchment); 'losses' is also set here but should be
    # ignored (with a warning) since only 'site' can differ between config files.
    config_b = {
        'site': {'name': '2', 'latitude': -27.389, 'longitude': 152.858, 'catchment_area': 5.0},
        'losses': {'method': 'probability_neutral'},
    }
    path_b = tmp_path / 'b.json'
    with open(path_b, 'w', encoding='utf-8') as f:
        json.dump(config_b, f)

    def fail_fetch(self, config):
        raise AssertionError('client.fetch should not be called when response_json is set')
    monkeypatch.setattr(ArrApiClient, 'fetch', fail_fetch)

    with caplog.at_level('WARNING'):
        exit_code = run([str(path_a), str(path_b)])
    assert exit_code == 0
    assert (tmp_path / 'Event_File.tef').exists()
    assert (tmp_path / 'bc_dbase.csv').exists()
    # config b's 'losses' override was ignored - a warning was logged about it
    assert any('losses' in r.message for r in caplog.records)
