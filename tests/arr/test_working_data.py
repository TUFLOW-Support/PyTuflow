"""Tests for :mod:`pytuflow.arr.working_data`."""

from __future__ import annotations

import json

import pytest

from pytuflow.arr import temporal_patterns as tp_module
from pytuflow.arr.config import ArrConfig
from pytuflow.arr.engine import ArrEngine
from pytuflow.arr.working_data import write_working_data


@pytest.fixture(autouse=True)
def mock_tp_downloads(monkeypatch, point_tp_csv, areal_tp_csv):
    def fake_download(url: str) -> str:
        if 'Areal' in url:
            return areal_tp_csv
        return point_tp_csv
    monkeypatch.setattr(tp_module, '_download_increments_csv', fake_download)


def make_config(tmp_path, verbose=False, **overrides):
    data = {
        'site': {'name': '1', 'latitude': -33.9347, 'longitude': 150.8372, 'catchment_area': 11.4},
        'ifd': {'source': 'bom', 'year': 1990},
        'output': {'path': str(tmp_path), 'format': 'csv', 'verbose': verbose},
    }
    data.update(overrides)
    return ArrConfig.from_dict(data)


def test_json_always_saved_even_when_not_verbose(tmp_path, api_response_1990):
    config = make_config(
        tmp_path, verbose=False,
        events={'aep': ['50%'], 'duration': [60], 'output_notation': 'ari'},
        losses={'extrapolation_method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    engine.run()
    write_working_data(config, api_response_1990, engine)

    working = tmp_path / 'working_data'
    json_path = working / '1_ARR_response.json'
    assert json_path.exists()
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)
    assert data == api_response_1990.raw

    # verbose-only files must not be written
    assert not (working / '1_ARF.csv').exists()
    assert not (working / '1_IFD_after_ARF.csv').exists()
    assert not (working / '1_burst_initial_loss.csv').exists()
    assert not (working / '1_PointTP_Increments.csv').exists()
    assert not (working / '1_extrapolated_losses.csv').exists()


def test_verbose_writes_all_working_data_files(tmp_path, api_response_1990):
    config = make_config(
        tmp_path, verbose=True,
        events={'aep': ['50%'], 'duration': [60, 1440], 'output_notation': 'ari'},
        losses={'extrapolation_method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    engine.run()
    write_working_data(config, api_response_1990, engine)

    working = tmp_path / 'working_data'
    assert (working / '1_ARR_response.json').exists()
    assert (working / '1_ARF.csv').exists()
    assert (working / '1_IFD_after_ARF.csv').exists()
    assert (working / '1_burst_initial_loss.csv').exists()
    assert (working / '1_PointTP_Increments.csv').exists()

    arf_csv = (working / '1_ARF.csv').read_text(encoding='utf-8')
    assert 'Duration (min)' in arf_csv
    assert '50%' in arf_csv


def test_verbose_writes_extrapolated_losses_csv_when_extrapolation_occurs(tmp_path, api_response_1990):
    config = make_config(
        tmp_path, verbose=True,
        events={'aep': ['50%'], 'duration': [15, 30], 'output_notation': 'ari'},
        losses={'extrapolation_method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    engine.run()
    write_working_data(config, api_response_1990, engine)

    working = tmp_path / 'working_data'
    path = working / '1_extrapolated_losses.csv'
    assert path.exists()
    content = path.read_text(encoding='utf-8')
    lines = content.strip().splitlines()
    assert lines[0].startswith('Duration (min),')
    assert '50.0' in lines[0]
    assert len(lines) == 2  # header + one extrapolated (duration=15) row
    assert lines[1].startswith('15.0,')


def test_no_extrapolated_losses_csv_when_no_extrapolation_needed(tmp_path, api_response_1990):
    config = make_config(
        tmp_path, verbose=True,
        events={'aep': ['50%'], 'duration': [60], 'output_notation': 'ari'},
        losses={'extrapolation_method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    engine.run()
    write_working_data(config, api_response_1990, engine)

    working = tmp_path / 'working_data'
    assert not (working / '1_extrapolated_losses.csv').exists()


def test_verbose_writes_files_for_multiple_durations_and_aeps(tmp_path, api_response_1990):
    config = make_config(
        tmp_path, verbose=True,
        events={'aep': ['50%', '20%'], 'duration': [60, 1440], 'output_notation': 'ari'},
        losses={'extrapolation_method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    engine.run()
    write_working_data(config, api_response_1990, engine)

    working = tmp_path / 'working_data'
    arf_csv = (working / '1_ARF.csv').read_text(encoding='utf-8')
    ifd_csv = (working / '1_IFD_after_ARF.csv').read_text(encoding='utf-8')
    for aep in ('50%', '20%'):
        assert aep in arf_csv
        assert aep in ifd_csv
