"""Shared pytest fixtures for :mod:`pytuflow.arr` tests."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from pytuflow.arr.api_client import ArrApiResponse

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.fixture
def api_response_1990() -> ArrApiResponse:
    """A cached, real ARR Data Hub API response (no climate change), for the site used
    to produce ``ARR_legacy_output/`` (lat -33.9347, lon 150.8372, area 11.4 km2,
    ARFParams zone 'East Coast North', TP region 'ECsouth').

    The response's ``PointTP``/``ArealTP`` zip URLs are rewritten from the API's
    internal-network host to the public Data Hub host, matching the automatic fallback
    behaviour that :mod:`pytuflow.arr.temporal_patterns` performs at runtime.
    """
    with open(FIXTURES / 'api_response_1990.json', encoding='utf-8') as f:
        data = json.load(f)
    for layer in ('PointTP', 'ArealTP'):
        data['layers'][layer]['url'] = data['layers'][layer]['url'].replace(
            '192.168.70.14:5000', 'data-dev.arr-software.org')
    return ArrApiResponse(data)


@pytest.fixture
def point_tp_csv() -> str:
    """Real ``ECsouth`` point temporal pattern increments CSV, extracted from a cached
    Data Hub zip download."""
    with zipfile.ZipFile(FIXTURES / 'point_tp.zip') as z:
        name = next(n for n in z.namelist() if 'increments' in n.lower())
        return z.read(name).decode('utf-8')


@pytest.fixture
def areal_tp_csv() -> str:
    """Real ``ECsouth`` areal temporal pattern increments CSV, extracted from a cached
    Data Hub zip download."""
    with zipfile.ZipFile(FIXTURES / 'areal_tp.zip') as z:
        name = next(n for n in z.namelist() if 'increments' in n.lower())
        return z.read(name).decode('utf-8')
