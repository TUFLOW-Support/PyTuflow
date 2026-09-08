"""Client for the ARR Data Hub API.

Replaces the legacy ``ARR_WebRes.py`` (ARR Data Hub HTML/text scraping) and
``BOM_WebRes.py`` (BOM IFD web page scraping) modules. The upgraded ARR Data Hub API
now serves both current and climate-change-adjusted IFD tables directly, so there is no
need for the new module to talk to BOM at all, nor calculate climate-change-adjusted
rainfall/losses itself.

See https://data-dev.arr-software.org/about for the full list of available API layers.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from .config import ArrConfig
from .downloader import Downloader
from .exceptions import ArrApiError

logger = logging.getLogger('pytuflow.arr')

#: Default (dev) base URL for the ARR Data Hub API. Point queries are simple GET requests;
#: see https://data-dev.arr-software.org/about for catchment-boundary (geojson/shapefile/kml)
#: POST request details, which will be supported in a future update.
DEFAULT_BASE_URL = 'https://data-dev.arr-software.org/'

#: Data layers requested for every query, matching the "Command Line Name" column in the
#: ARR Data Hub "Advanced Use" API docs.
_BASE_LAYERS = (
    'RiverRegion',
    'ARFParams',
    'StormLosses',
    'TemporalPatterns',
    'ArealTemporalPatterns',
    'BoMIFD',
    'Preburst',
    'OtherPreburst',
)


class ArrApiResponse:
    """Thin wrapper around the parsed JSON response from the ARR Data Hub API, providing
    convenience accessors for the layers used by :mod:`pytuflow.arr`.
    """

    def __init__(self, data: dict) -> None:
        self.raw = data
        self.title = data.get('title')
        self.input_data = data.get('input_data', {})
        self.layers = data.get('layers', {})

    def layer(self, name: str, required: bool = False) -> Optional[dict]:
        """Returns the raw (dict-of-tables or dict-of-values) data for the named layer."""
        value = self.layers.get(name)
        if required and value is None:
            raise ArrApiError(f"ARR Data Hub response is missing expected layer '{name}'")
        return value

    def ifd_table(self, year: int) -> dict:
        """Returns the BoM recommended IFD table (``RecIFD`` layer) for the given baseline
        year (1990 or 2030)."""
        rec_ifd = self.layer('RecIFD', required=True)
        key = {
            1990: 'Recommended Historical (1961-1990) Baseline',
            2030: 'Recommended Current (2030) Baseline',
        }.get(year)
        if key is None or key not in rec_ifd:
            raise ArrApiError(
                f"ARR Data Hub response does not contain an IFD table for baseline year '{year}' "
                f"(available: {list(rec_ifd)})"
            )
        return rec_ifd[key]

    def cc_adj_ifd_table(self, baseline_year: int, ssp: str) -> dict:
        """Returns a climate-change-adjusted IFD table (``CCAdjIFDDatasets`` layer) for the
        given baseline year (2030, 2050, or 2090) and SSP scenario (SSP1/SSP2/SSP3/SSP5)."""
        cc_adj = self.layer('CCAdjIFDDatasets', required=True)
        key = f'BoM IFD Depths ({baseline_year} Baseline - {ssp})'
        if key not in cc_adj:
            raise ArrApiError(
                f"ARR Data Hub response does not contain a climate-change-adjusted IFD table "
                f"for '{key}' (available: {list(cc_adj)})"
            )
        return cc_adj[key]


class ArrApiClient:
    """Fetches data from the ARR Data Hub API for a single site (point) config."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url

    def build_params(self, config: ArrConfig) -> dict:
        """Builds the GET query parameters for the API request, based on the config's
        site location and which optional layers are required (e.g. climate change)."""
        params = {
            'lat_coord': config.site.latitude,
            'lon_coord': config.site.longitude,
            'type': 'json',
        }
        for layer in _BASE_LAYERS:
            params[layer] = 1
        if config.climate_change.enabled:
            params['CCAdjIFDDatasets'] = 1
        return params

    def fetch(self, config: ArrConfig) -> ArrApiResponse:
        """Requests data from the ARR Data Hub API for the given config's site, and
        returns the parsed response."""
        params = self.build_params(config)
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        url = f'{self.base_url}?{query}'
        logger.info('Requesting ARR Data Hub data: %s', url)
        downloader = Downloader(url)
        downloader.download()
        if not downloader.ok():
            raise ArrApiError(
                f"ARR Data Hub request failed (using {downloader.type()} downloader): "
                f"HTTP {downloader.ret_code}: {downloader.error_string}"
            )
        try:
            data = json.loads(downloader.data)
        except json.JSONDecodeError as e:
            raise ArrApiError(f"ARR Data Hub response is not valid JSON: {e}") from e
        return ArrApiResponse(data)
