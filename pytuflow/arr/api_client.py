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

    def climate_change_loss_factors(self, baseline_year: int, ssp: str) -> tuple:
        """Returns ``(initial_loss_factor, continuing_loss_factor)`` from the
        ``ClimateChange`` layer's ``loss_factors`` tables, for the given baseline year
        (2030-2100, in 10-year increments) and SSP scenario (SSP1/SSP2/SSP3/SSP5). Both
        design rainfall losses are multiplied by these factors for climate-change
        events, matching the legacy script's treatment of climate-change-adjusted
        losses."""
        cc = self.layer('ClimateChange', required=True)
        loss_factors = cc.get('loss_factors') or {}
        il_table = loss_factors.get('Initial_Loss')
        cl_table = loss_factors.get('Continuing_Loss')
        if il_table is None or cl_table is None:
            raise ArrApiError(
                "ARR Data Hub response is missing 'ClimateChange' loss factor tables "
                "('Initial_Loss'/'Continuing_Loss')."
            )
        il_factor = _lookup_loss_factor(il_table, baseline_year, ssp)
        cl_factor = _lookup_loss_factor(cl_table, baseline_year, ssp)
        return il_factor, cl_factor


def _lookup_loss_factor(table: dict, baseline_year: int, ssp: str) -> float:
    """Looks up a single climate change loss factor value from a ``{"index":
    ..., "columns": ..., "data": ...}`` table (rows are baseline years, columns are
    SSP-labelled, e.g. ``'Losses SSP2-4.5'``)."""
    col_idx = None
    for i, col in enumerate(table['columns']):
        if str(col).upper().startswith(f'LOSSES {ssp.upper()}') or ssp.upper() in str(col).upper():
            col_idx = i
            break
    if col_idx is None:
        raise ArrApiError(
            f"ARR Data Hub 'ClimateChange' loss factor table does not contain SSP '{ssp}' "
            f"(available columns: {table['columns']})"
        )
    years = [int(y) for y in table['index']]
    if baseline_year not in years:
        raise ArrApiError(
            f"ARR Data Hub 'ClimateChange' loss factor table does not contain baseline year "
            f"'{baseline_year}' (available: {years})"
        )
    row_idx = years.index(baseline_year)
    return float(table['data'][row_idx][col_idx])


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
            params['ClimateChange'] = 1
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
