"""Live smoke test against the real ARR Data Hub API (dev environment). Skipped by
default - set the ``ARR_LIVE_TESTS=1`` environment variable to run it (e.g. in CI on a
schedule, or manually when validating against API changes). This deliberately makes a
real network request and does not use any cached fixtures.
"""

from __future__ import annotations

import os

import pytest

from pytuflow.arr.api_client import ArrApiClient
from pytuflow.arr.config import ArrConfig
from pytuflow.arr.engine import ArrEngine
from pytuflow.arr.writers import write_outputs

pytestmark = pytest.mark.skipif(
    os.environ.get('ARR_LIVE_TESTS') != '1',
    reason="Live ARR Data Hub API tests are skipped by default; set ARR_LIVE_TESTS=1 to run.",
)


def test_live_fetch_and_assemble(tmp_path):
    config = ArrConfig.from_dict({
        'site': {'name': '1', 'latitude': -33.9347, 'longitude': 150.8372, 'catchment_area': 11.4},
        'ifd': {'source': 'bom', 'year': 1990},
        'events': {'aep': ['50%'], 'duration': [60, 1440], 'output_notation': 'ari'},
        'losses': {'method': 'interpolate'},
        'output': {'path': str(tmp_path), 'format': 'csv'},
    })
    client = ArrApiClient()
    response = client.fetch(config)
    engine = ArrEngine(config, response)
    results = engine.run()
    assert len(results) == 2
    for r in results:
        assert r.depth_areal > 0
        assert len(r.patterns) == 10

    write_outputs(config, results)
    assert (tmp_path / 'Event_File.tef').exists()
    assert (tmp_path / 'rf_inflow' / '1_RF_50p1440m.csv').exists()
