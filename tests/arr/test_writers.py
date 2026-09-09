"""Tests for :mod:`pytuflow.arr.writers`."""

from __future__ import annotations

import pytest

from pytuflow.arr import temporal_patterns as tp_module
from pytuflow.arr.config import ArrConfig
from pytuflow.arr.engine import ArrEngine
from pytuflow.arr.writers import (
    format_aep,
    format_duration,
    write_outputs,
)


@pytest.fixture(autouse=True)
def mock_tp_downloads(monkeypatch, point_tp_csv, areal_tp_csv):
    def fake_download(url: str) -> str:
        if 'Areal' in url:
            return areal_tp_csv
        return point_tp_csv
    monkeypatch.setattr(tp_module, '_download_increments_csv', fake_download)


@pytest.mark.parametrize('aep_name, expected', [
    ('1%', '01p'), ('0.5%', '0.50p'), ('50%', '50p'), ('0.5EY', '0.5e'), ('1 in 200', '200y'),
])
def test_format_aep(aep_name, expected):
    assert format_aep(aep_name, 'ari') == expected


def test_format_aep_unrecognised_raises():
    from pytuflow.arr.exceptions import ArrError
    with pytest.raises(ArrError):
        format_aep('not an aep', 'ari')


@pytest.mark.parametrize('duration, expected', [(60, '60m'), (1440, '1440m'), (0.5, '0.5m')])
def test_format_duration(duration, expected):
    assert format_duration(duration) == expected


def make_config(tmp_path, **overrides):
    data = {
        'site': {'name': '1', 'latitude': -33.9347, 'longitude': 150.8372, 'catchment_area': 11.4},
        'ifd': {'source': 'bom', 'year': 1990},
        'output': {'path': str(tmp_path), 'format': 'csv'},
    }
    data.update(overrides)
    return ArrConfig.from_dict(data)


def test_write_outputs_creates_expected_files(tmp_path, api_response_1990):
    config = make_config(
        tmp_path,
        events={'aep': ['50%'], 'duration': [60, 1440], 'output_notation': 'ari'},
        losses={'method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    write_outputs(config, results)

    assert (tmp_path / 'Event_File.tef').exists()
    assert (tmp_path / 'bc_dbase.csv').exists()
    assert (tmp_path / 'soils.tsoilf').exists()
    assert (tmp_path / 'soil_infiltration.trd').exists()
    assert (tmp_path / 'rf_inflow' / '1_RF_50p60m.csv').exists()
    assert (tmp_path / 'rf_inflow' / '1_RF_50p1440m.csv').exists()


def test_tef_contains_expected_event_definitions(tmp_path, api_response_1990):
    config = make_config(
        tmp_path,
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        losses={'method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    write_outputs(config, results)

    tef = (tmp_path / 'Event_File.tef').read_text()
    assert 'Define Event == 50p' in tef
    assert 'BC Event Source == ~ARI~ | 50p' in tef
    assert 'Define Event == 1440m' in tef
    assert 'Define Event == tp01' in tef
    assert 'Define Event == tp10' in tef


def test_rf_inflow_csv_structure(tmp_path, api_response_1990):
    config = make_config(
        tmp_path,
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        losses={'method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    write_outputs(config, results)

    lines = (tmp_path / 'rf_inflow' / '1_RF_50p1440m.csv').read_text().splitlines()
    assert lines[0].startswith('!')
    assert lines[1].startswith('Event ID,')
    assert lines[2].startswith('Time (hour),TP01')
    assert lines[3] == '0,0,0,0,0,0,0,0,0,0,0'
    # second last data row's time should equal duration/60 hours
    last_row = lines[-2].split(',')
    assert float(last_row[0]) == pytest.approx(1440 / 60)
    # last data row's time should be one extra step
    last_row = lines[-1].split(',')
    assert float(last_row[0]) == pytest.approx((1440 + 60) / 60)


def test_rf_inflow_complete_storm_prepends_preburst(tmp_path, api_response_1990):
    # 20%/1440min is a 'Use PB TP' placeholder cell that auto-triggers complete storm.
    config = make_config(
        tmp_path,
        events={'aep': ['20%'], 'duration': [1440], 'output_notation': 'ari'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    assert results[0].preburst is not None
    write_outputs(config, results)

    lines = (tmp_path / 'rf_inflow' / '1_RF_20p1440m.csv').read_text().splitlines()
    pb = results[0].preburst
    data_rows = lines[4:]  # skip header rows + the initial "time=0" row
    # total number of data rows == preburst steps + design burst steps
    assert len(data_rows) == len(pb.increments) + len(results[0].patterns[0].increments) + 1
    # first preburst row's rainfall matches preburst depth * first increment / 100
    first_row = data_rows[0].split(',')
    expected = pb.increments[0] * pb.depth / 100.0
    assert float(first_row[1]) == pytest.approx(expected)


def test_trd_sets_expected_variables(tmp_path, api_response_1990):
    config = make_config(
        tmp_path,
        events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        losses={'method': 'interpolate'},
    )
    engine = ArrEngine(config, api_response_1990)
    results = engine.run()
    write_outputs(config, results)

    trd = (tmp_path / 'soil_infiltration.trd').read_text()
    assert 'If Event == 50p' in trd
    assert 'If Event == 1440m' in trd
    assert f'Set Variable IL_1 == {results[0].initial_loss:.1f}' in trd
    assert f'Set Variable CL_1 == {results[0].continuing_loss:.1f}' in trd


def test_write_outputs_append_mode_multi_site(tmp_path, api_response_1990):
    config_a = make_config(
        tmp_path, events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        losses={'method': 'interpolate'})
    config_a.site.name = 'A'
    config_b = make_config(
        tmp_path, events={'aep': ['50%'], 'duration': [1440], 'output_notation': 'ari'},
        losses={'method': 'interpolate'})
    config_b.site.name = 'B'

    write_outputs(config_a, ArrEngine(config_a, api_response_1990).run(), append=False)
    write_outputs(config_b, ArrEngine(config_b, api_response_1990).run(), append=True)

    bc_dbase = (tmp_path / 'bc_dbase.csv').read_text()
    assert bc_dbase.count('\n') == 3  # header + 2 site rows (+ trailing newline)
    assert 'A,' in bc_dbase and 'B,' in bc_dbase

    tsoilf = (tmp_path / 'soils.tsoilf').read_text()
    assert '1, ILCL, <<IL_A>>' in tsoilf
    assert '2, ILCL, <<IL_B>>' in tsoilf
