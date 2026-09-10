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
    assert params['ClimateChange'] == 1


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


def test_build_params_includes_all_ifd_datasets_when_limb_source():
    config = ArrConfig.from_dict({
        **SITE_CONFIG,
        'ifd': {'source': 'limb', 'year': 2020},
    })
    params = ArrApiClient().build_params(config)
    assert params.get('AllIFDDatasets') == 1


def test_build_params_omits_all_ifd_datasets_for_bom_source():
    config = ArrConfig.from_dict(SITE_CONFIG)
    params = ArrApiClient().build_params(config)
    assert 'AllIFDDatasets' not in params


#: Real LIMB 2020 high-resolution IFD table, from a live Data Hub query at
#: (152.93, -27.684) - within South East Queensland.
LIMB_2020_TABLE = {
    'index': [5, 10, 15, 20, 25, 30],
    'columns': [63.2, 50.0, 39.35, 20.0, 18.13, 10.0, 5.0, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05],
    'data': [
        [9.9, 11.2, 12.3, 15.3, 15.7, 18.2, 20.9, 24.4, 27.1, 30.7, 36.0, 40.2, 44.7],
        [16.6, 18.9, 20.7, 25.4, 25.9, 28.8, 32.2, 36.3, 39.1, 44.2, 51.6, 57.5, 63.8],
        [21.0, 23.9, 26.3, 32.0, 32.6, 36.0, 39.9, 44.4, 47.3, 53.5, 62.4, 69.7, 77.3],
        [24.1, 27.5, 30.2, 36.7, 37.4, 41.4, 45.7, 50.7, 53.9, 61.1, 71.2, 79.5, 88.2],
        [26.5, 30.2, 33.1, 40.3, 41.1, 45.6, 50.4, 55.9, 59.5, 67.3, 78.7, 87.8, 97.7],
        [28.4, 32.3, 35.5, 43.2, 44.1, 49.1, 54.4, 60.4, 64.4, 73.1, 85.3, 94.9, 106.0],
    ],
}


def test_limb_ifd_table_returns_expected_dataset():
    data = {
        'layers': {
            'AllIFDDatasets': {
                'LIMB 2020 IFD Depths - High Resolution': LIMB_2020_TABLE,
                'LIMB 2020 IFD Depths - BoM Resolution': LIMB_2020_TABLE,
                'BoM IFD Depths': LIMB_2020_TABLE,
            }
        }
    }
    response = ArrApiResponse(data)
    table = response.limb_ifd_table(2020)
    assert table == LIMB_2020_TABLE


def test_limb_ifd_table_missing_layer_raises(api_response_1990):
    with pytest.raises(ArrApiError, match='AllIFDDatasets'):
        api_response_1990.limb_ifd_table(2020)


def test_limb_ifd_table_missing_dataset_raises_seq_message():
    # 'AllIFDDatasets' layer present, but no LIMB dataset key (i.e. queried location is
    # outside South East Queensland, so only the BoM dataset is returned).
    data = {'layers': {'AllIFDDatasets': {'BoM IFD Depths': LIMB_2020_TABLE}}}
    response = ArrApiResponse(data)
    with pytest.raises(ArrApiError, match='South East Queensland'):
        response.limb_ifd_table(2020)
