"""Tests for :mod:`pytuflow.arr.downloader` and :mod:`pytuflow.arr.api_client`."""

from __future__ import annotations

import json

import pytest

from pytuflow.arr.api_client import ArrApiClient, ArrApiResponse
from pytuflow.arr.config import ArrConfig
from pytuflow.arr.downloader import Downloader, DownloaderRequests
from pytuflow.arr.exceptions import ArrApiError

SITE_CONFIG = {
    'site': {'name': '1', 'latitude': -33.9347, 'longitude': 150.8372, 'catchment_area': 11.4},
    'ifd': {'baseline_year': 1990},
    'events': {'aep': ['1%'], 'duration': [1440], 'output_notation': 'ari'},
    'output': {'path': '/tmp/unused', 'format': 'csv'},
}


def test_downloader_factory_selects_requests_without_qgis():
    downloader = Downloader('https://example.com')
    assert isinstance(downloader, DownloaderRequests)
    assert downloader.type() == 'Requests'


def test_build_params_includes_base_layers():
    config = ArrConfig.from_dict(SITE_CONFIG)
    client = ArrApiClient()
    params = client.build_params(config)
    assert params['lat_coord'] == -33.9347
    assert params['lon_coord'] == 150.8372
    assert params['type'] == 'json'
    assert params['BoMIFD'] == 1
    assert 'CCAdjIFDDatasets' not in params


def test_build_params_includes_cc_layer_when_enabled():
    data = dict(SITE_CONFIG)
    data['climate_change'] = {'enabled': True, 'scenarios': [{'baseline_year': 2090, 'ssp': 'SSP2'}]}
    config = ArrConfig.from_dict(data)
    client = ArrApiClient()
    params = client.build_params(config)
    assert 'CCAdjIFDDatasets' not in params
    assert params['ClimateChange'] == 1


def test_api_response_ifd_table(api_response_1990):
    table = api_response_1990.ifd_table(1990)
    assert 'index' in table and 'columns' in table and 'data' in table


def test_api_response_ifd_table_bad_year_raises(api_response_1990):
    with pytest.raises(ArrApiError, match='baseline year'):
        api_response_1990.ifd_table(2050)


def test_climate_change_rainfall_factors():
    columns = ['<1 hour', '1.5 Hours', '2 Hours', '>24 Hours']
    data = {'layers': {'ClimateChange': {'rainfall_factors': {
        'SSP2-4.5': {'columns': columns, 'index': [2030, 2090],
                     'data': [[1.18, 1.17, 1.16, 1.1], [1.3, 1.28, 1.26, 1.2]]},
    }}}}
    hours, factors = ArrApiResponse(data).climate_change_rainfall_factors(2090, 'SSP2')
    assert hours == [1.0, 1.5, 2.0, 24.0]
    assert factors == [1.3, 1.28, 1.26, 1.2]
    with pytest.raises(ArrApiError, match='baseline year'):
        ArrApiResponse(data).climate_change_rainfall_factors(2050, 'SSP2')
    with pytest.raises(ArrApiError, match='SSP'):
        ArrApiResponse(data).climate_change_rainfall_factors(2090, 'SSP5')


def test_api_response_missing_layer_raises(api_response_1990):
    with pytest.raises(ArrApiError, match='ClimateChange'):
        api_response_1990.climate_change_rainfall_factors(2090, 'SSP2')


def test_api_response_layer_optional_returns_none(api_response_1990):
    assert api_response_1990.layer('DoesNotExist') is None


def test_climate_change_loss_factors():
    data = {
        'layers': {
            'ClimateChange': {
                'label': 'Climate Change Factors',
                'loss_factors': {
                    'Initial_Loss': {
                        'columns': ['Losses SSP1-2.6', 'Losses SSP2-4.5', 'Losses SSP3-7.0', 'Losses SSP5-8.5'],
                        'index': [2030, 2050, 2090],
                        'data': [[1.02, 1.02, 1.02, 1.03], [1.03, 1.03, 1.04, 1.04], [1.03, 1.05, 1.07, 1.08]],
                    },
                    'Continuing_Loss': {
                        'columns': ['Losses SSP1-2.6', 'Losses SSP2-4.5', 'Losses SSP3-7.0', 'Losses SSP5-8.5'],
                        'index': [2030, 2050, 2090],
                        'data': [[1.04, 1.05, 1.05, 1.05], [1.06, 1.06, 1.07, 1.08], [1.06, 1.09, 1.13, 1.16]],
                    },
                },
            }
        }
    }
    response = ArrApiResponse(data)
    il_factor, cl_factor = response.climate_change_loss_factors(2090, 'SSP2')
    assert il_factor == pytest.approx(1.05)
    assert cl_factor == pytest.approx(1.09)


def test_climate_change_loss_factors_missing_layer_raises(api_response_1990):
    with pytest.raises(ArrApiError, match='ClimateChange'):
        api_response_1990.climate_change_loss_factors(2090, 'SSP2')


def test_build_params_omits_all_ifd_datasets_for_bom_source():
    config = ArrConfig.from_dict(SITE_CONFIG)
    params = ArrApiClient().build_params(config)
    assert 'AllIFDDatasets' not in params


def test_build_params_excludes_lat_lon_when_catchment_boundary(tmp_path):
    boundary = tmp_path / 'catchment.geojson'
    boundary.write_text('{}')
    data = json.loads(json.dumps(SITE_CONFIG))
    del data['site']['latitude']
    del data['site']['longitude']
    data['site']['catchment_boundary'] = str(boundary)
    config = ArrConfig.from_dict(data)
    params = ArrApiClient().build_params(config)
    assert 'lat_coord' not in params
    assert 'lon_coord' not in params


def test_build_params_includes_outlet_coords():
    data = json.loads(json.dumps(SITE_CONFIG))
    data['site']['outlet_latitude'] = -33.9
    data['site']['outlet_longitude'] = 151.0
    config = ArrConfig.from_dict(data)
    params = ArrApiClient().build_params(config)
    assert params['outlet_lat_coord'] == -33.9
    assert params['outlet_lon_coord'] == 151.0


def test_catchment_boundary_files_single_file(tmp_path):
    boundary = tmp_path / 'catchment.geojson'
    boundary.write_text('{"type": "FeatureCollection"}')
    files = ArrApiClient._catchment_boundary_files(str(boundary))
    assert len(files) == 1
    assert files[0].field_name == 'shapeFile[]'
    assert files[0].filename == 'catchment.geojson'
    assert files[0].content == boundary.read_bytes()


def test_catchment_boundary_files_shapefile_includes_siblings(tmp_path):
    shp = tmp_path / 'catchment.shp'
    shp.write_bytes(b'shp-bytes')
    (tmp_path / 'catchment.shx').write_bytes(b'shx-bytes')
    (tmp_path / 'catchment.dbf').write_bytes(b'dbf-bytes')
    (tmp_path / 'catchment.prj').write_bytes(b'prj-bytes')
    files = ArrApiClient._catchment_boundary_files(str(shp))
    filenames = {f.filename for f in files}
    assert filenames == {'catchment.shp', 'catchment.shx', 'catchment.dbf', 'catchment.prj'}
    assert all(f.field_name == 'shapeFile[]' for f in files)


def test_fetch_uses_post_for_catchment_boundary(tmp_path, monkeypatch):
    boundary = tmp_path / 'catchment.geojson'
    boundary.write_text('{}')
    data = json.loads(json.dumps(SITE_CONFIG))
    del data['site']['latitude']
    del data['site']['longitude']
    data['site']['catchment_boundary'] = str(boundary)
    config = ArrConfig.from_dict(data)

    captured = {}

    class FakeResponse:
        status_code = 200
        ok = True
        content = b'{"title": "catchment result", "layers": {}}'
        headers = {'content-type': 'application/json'}

    def fake_post(url, data=None, files=None, headers=None, timeout=None):
        captured['url'] = url
        captured['data'] = data
        captured['files'] = files
        return FakeResponse()

    monkeypatch.setattr('pytuflow.arr.downloader.requests.post', fake_post)
    response = ArrApiClient().fetch(config)
    assert response.title == 'catchment result'
    assert captured['data']['type'] == 'json'
    assert 'lat_coord' not in captured['data']
    field_names = {name for name, _ in captured['files']}
    assert field_names == {'shapeFile[]'}


def test_downloader_requests_post_passes_data_and_files(monkeypatch):
    from pytuflow.arr.downloader import FilePart

    captured = {}

    class FakeResponse:
        status_code = 200
        ok = True
        content = b'ok'
        headers = {'content-type': 'text/plain'}

    def fake_post(url, data=None, files=None, headers=None, timeout=None):
        captured.update(url=url, data=data, files=files, headers=headers, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr('pytuflow.arr.downloader.requests.post', fake_post)
    downloader = DownloaderRequests('https://example.com')
    file_part = FilePart(field_name='shapeFile[]', filename='c.geojson', content=b'{}',
                         content_type='application/geo+json')
    downloader.download(method='POST', data={'type': 'json'}, files=[file_part])
    assert downloader.ok()
    assert downloader.data == 'ok'
    assert captured['url'] == 'https://example.com'
    assert captured['data'] == {'type': 'json'}
    assert captured['files'] == [('shapeFile[]', ('c.geojson', b'{}', 'application/geo+json'))]


def _retry_config(max_retries):
    return ArrConfig.from_dict({
        'site': {'name': 'S', 'latitude': -27.0, 'longitude': 153.0},
        'events': {'aep': [1], 'duration': [60]},
        'output': {'path': 'out'},
        'max_retries': max_retries,
    })


def _fake_downloader(responses, calls):
    class Fake(DownloaderRequests):
        def __new__(cls, url):
            return object.__new__(cls)

        def download(self, **kwargs):
            calls.append(1)
            code = responses[min(len(calls), len(responses)) - 1]
            if isinstance(code, Exception):
                raise code
            self.ret_code = code
            self.data = '{}' if code == 200 else None
            self.error_string = '' if code == 200 else 'err'
    return Fake


def test_fetch_retries_with_exponential_backoff(monkeypatch):
    import requests
    from pytuflow.arr import api_client
    calls, sleeps = [], []
    fake = _fake_downloader([500, requests.ConnectionError('boom'), 200], calls)
    monkeypatch.setattr(api_client, 'Downloader', lambda url: fake(url))
    monkeypatch.setattr(api_client.time, 'sleep', sleeps.append)
    monkeypatch.setattr(api_client.random, 'uniform', lambda a, b: 1.0)
    ArrApiClient().fetch(_retry_config(3))
    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


def test_fetch_does_not_retry_client_errors_and_respects_max_retries(monkeypatch):
    from pytuflow.arr import api_client
    monkeypatch.setattr(api_client.time, 'sleep', lambda s: None)
    calls = []
    fake = _fake_downloader([404], calls)
    monkeypatch.setattr(api_client, 'Downloader', lambda url: fake(url))
    with pytest.raises(ArrApiError):
        ArrApiClient().fetch(_retry_config(3))
    assert len(calls) == 1

    calls.clear()
    fake = _fake_downloader([503], calls)
    monkeypatch.setattr(api_client, 'Downloader', lambda url: fake(url))
    with pytest.raises(ArrApiError):
        ArrApiClient().fetch(_retry_config(2))
    assert len(calls) == 3
