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
    'ifd': {'source': 'bom', 'year': 1990},
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
    assert params['CCAdjIFDDatasets'] == 1


def test_api_response_ifd_table(api_response_1990):
    table = api_response_1990.ifd_table(1990)
    assert 'index' in table and 'columns' in table and 'data' in table


def test_api_response_ifd_table_bad_year_raises(api_response_1990):
    with pytest.raises(ArrApiError, match='baseline year'):
        api_response_1990.ifd_table(2050)


def test_api_response_missing_layer_raises(api_response_1990):
    with pytest.raises(ArrApiError, match='CCAdjIFDDatasets'):
        api_response_1990.cc_adj_ifd_table(2090, 'SSP2')


def test_api_response_layer_optional_returns_none(api_response_1990):
    assert api_response_1990.layer('DoesNotExist') is None
