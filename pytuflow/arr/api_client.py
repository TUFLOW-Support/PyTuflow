"""Client for the ARR Data Hub API.

Replaces the legacy ``ARR_WebRes.py`` (ARR Data Hub HTML/text scraping) and
``BOM_WebRes.py`` (BOM IFD web page scraping) modules. The upgraded ARR Data Hub API
now serves current IFD tables and climate change factors directly, so there is no
need for the new module to talk to BOM at all. Climate-change rainfall is derived from
the Data Hub's climate change factors applied to the historical IFD depths.

See https://data.arr-software.org/about for the full list of available API layers.
"""

from __future__ import annotations

import json
import logging
import mimetypes
import random
import re
import time
from pathlib import Path
from typing import Optional

import numpy as np

from .config import ArrConfig, SHAPEFILE_OPTIONAL_SIBLINGS, SHAPEFILE_REQUIRED_SIBLINGS
from .downloader import Downloader, FilePart
from .exceptions import ArrApiError

logger = logging.getLogger('pytuflow.arr')

#: Default (dev) base URL for the ARR Data Hub API. Point queries (``site.latitude``/
#: ``site.longitude``) are simple GET requests; catchment-boundary queries
#: (``site.catchment_boundary`` - GeoJSON/Shapefile/KML) are ``multipart/form-data`` POST
#: requests instead - see https://data.arr-software.org/about.
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

#: Frequent event (exceedances per year) magnitudes, mapped to the AEP (%) used to label their
#: columns once merged into the IFD table (matches :func:`pytuflow.arr.arf.aep_name_to_pct`), and to
#: the AEP (%) column label used by the Data Hub's ``AllBoMIFD`` layer. Frequent events need Data Hub v1.1+.
FREQUENT_EY_AEP_PCT = {12: 99.85, 6: 99.75, 4: 98.17, 3: 95.02, 2: 86.47}
_FREQUENT_EY_HUB_AEP = {12: 99.999, 6: 99.752, 4: 98.168, 3: 95.021, 2: 86.466}


def is_frequent_ey(aep_name) -> bool:
    """True if the AEP/ARI/EY label is one of the frequent events (12EY, 6EY, 4EY, 3EY, 2EY)."""
    name = str(aep_name).strip().upper()
    if not name.endswith('EY'):
        return False
    try:
        return float(name[:-2]) in FREQUENT_EY_AEP_PCT
    except ValueError:
        return False


def _parse_version(version) -> tuple:
    """Parses a Data Hub version string such as ``'2026v1.1'`` into ``(1, 1)``. Returns
    ``(1, 0)`` if missing/unrecognised (i.e. treated as v1)."""
    match = re.search(r'v(\d+)(?:\.(\d+))?', str(version or ''), re.IGNORECASE)
    if not match:
        return 1, 0
    return int(match.group(1)), int(match.group(2) or 0)


#: Initial delay (seconds) before the first retry; doubles on each subsequent retry.
RETRY_BASE_DELAY = 1.0
#: Upper limit (seconds) on the delay between retries.
RETRY_MAX_DELAY = 30.0


def _is_retryable(downloader: Downloader) -> bool:
    """Transient failures only: no response at all, rate limiting, or a server error."""
    code = downloader.ret_code
    return code is None or code == 429 or code >= 500


def _download_with_retry(url: str, max_retries: int, **kwargs) -> Downloader:
    """Runs ``Downloader(url).download(**kwargs)``, retrying up to ``max_retries`` times on
    transient failures with exponential backoff (``RETRY_BASE_DELAY * 2 ** attempt``, capped
    at ``RETRY_MAX_DELAY``, with random jitter). Returns the last downloader used."""
    attempt = 0
    while True:
        downloader = Downloader(url)
        try:
            downloader.download(**kwargs)
        except OSError as e:  # includes requests.RequestException (connection errors/timeouts)
            downloader.ret_code = None
            downloader.error_string = str(e)
        if downloader.ok() or not _is_retryable(downloader) or attempt >= max_retries:
            return downloader
        delay = min(RETRY_BASE_DELAY * 2 ** attempt, RETRY_MAX_DELAY)
        delay *= random.uniform(0.5, 1.0)  # nosec B311
        attempt += 1
        logger.warning("ARR Data Hub request failed (HTTP %s: %s) - retrying in %.1fs (retry %d of %d)",
                       downloader.ret_code, downloader.error_string, delay, attempt, max_retries)
        time.sleep(delay)


class ArrApiResponse:
    """Thin wrapper around the parsed JSON response from the ARR Data Hub API, providing
    convenience accessors for the layers used by ``arr`` module.

    Parameters
    ----------
    data : dict
        The parsed response JSON file as a Python dict.
    """

    def __init__(self, data: dict) -> None:
        self.raw = data
        self.title = data.get('title')
        self.input_data = data.get('input_data', {})
        self.layers = data.get('layers', {})
        self.datahub_version = data.get('datahub_version')

    @property
    def is_v1_1_or_later(self) -> bool:
        """True if the response is from ARR Data Hub v1.1 or later (frequent event IFD depths,
        and baseline/native losses are only available from v1.1)."""
        return _parse_version(self.datahub_version) >= (1, 1)

    def require_frequent_event_support(self, aep_names) -> None:
        """Raises :class:`ArrApiError` if any frequent event (12EY, 6EY, 4EY, 3EY, 2EY) is
        requested but the response is from ARR Data Hub v1 rather than v1.1+."""
        frequent = [a for a in aep_names if is_frequent_ey(a)]
        if frequent and not self.is_v1_1_or_later:
            raise ArrApiError(
                f"Frequent events ({', '.join(str(a) for a in frequent)}) require ARR Data Hub v1.1 or later, "
                f"but the response is from version '{self.datahub_version or '1'}'."
            )

    def layer(self, name: str, required: bool = False) -> Optional[dict]:
        """Returns the raw (dict-of-tables or dict-of-values) data for the named layer."""
        value = self.layers.get(name)
        if required and value is None:
            raise ArrApiError(f"ARR Data Hub response is missing expected layer '{name}'")
        return value

    def ifd_table(self, year: int) -> dict:
        """Returns the Data Hub's recommended IFD table (``RecIFD`` layer) for the given
        baseline year (1990 or 2030). This is always the Data Hub's own recommended
        dataset for the queried location - which jurisdiction-specific source underlies
        it (e.g. BoM, or LIMB for South East Queensland) is determined server-side."""
        rec_ifd = self.layer('RecIFD', required=True)
        key = {
            1990: 'Default Historical (1961-1990) Baseline',
            2030: 'Default Current (2030) Baseline',
        }.get(year)
        if key is None or key not in rec_ifd:
            raise ArrApiError(
                f"ARR Data Hub response does not contain an IFD table for baseline year '{year}' "
                f"(available: {list(rec_ifd)})"
            )
        return self._with_frequent_events(rec_ifd[key], year)

    def _with_frequent_events(self, table: dict, year: int) -> dict:
        """Merges the frequent event (12/6/4/3/2 EY) columns of the ``AllBoMIFD`` layer (v1.1+,
        BoM IFD only) into an IFD table, relabelling them to the AEPs used by
        :func:`pytuflow.arr.arf.aep_name_to_pct`. Returns ``table`` unchanged if the layer is absent.

        The Data Hub only provides these depths for the 1990 baseline. For ``year == 2030`` they are
        scaled by the SSP2 2030 climate change rainfall factor (from the ``ClimateChange`` layer)."""
        all_ifd = self.layer('AllBoMIFD')
        if not all_ifd:
            return table
        bom = next((v for v in all_ifd.values() if isinstance(v, dict) and 'columns' in v), None)
        if bom is None:
            return table
        bom_index = list(bom['index'])
        bom_columns = [float(c) for c in bom['columns']]
        new_cols, new_data = [], []
        for ey, hub_aep in _FREQUENT_EY_HUB_AEP.items():
            col = next((i for i, c in enumerate(bom_columns) if abs(c - hub_aep) < 1e-6), None)
            if col is None or any(abs(float(c) - FREQUENT_EY_AEP_PCT[ey]) < 1e-6 for c in table['columns']):
                continue
            values = []
            for dur in table['index']:
                if dur not in bom_index:
                    break
                values.append(bom['data'][bom_index.index(dur)][col])
            else:
                new_cols.append(FREQUENT_EY_AEP_PCT[ey])
                new_data.append(values)
        if not new_cols:
            return table
        if year == 2030:
            hours, factors = self.climate_change_rainfall_factors(2030, 'SSP2')
            order = np.argsort(hours)
            factor_by_dur = np.interp(
                np.log10(np.array(table['index'], dtype=float) / 60.0),
                np.log10(np.array(hours)[order]), np.array(factors)[order])
            new_data = [[v * f for v, f in zip(col_values, factor_by_dur)] for col_values in new_data]
        return {
            'index': list(table['index']),
            'columns': list(table['columns']) + new_cols,
            'data': [list(row) + [col_values[i] for col_values in new_data]
                     for i, row in enumerate(table['data'])],
        }

    def climate_change_rainfall_factors(self, baseline_year: int, ssp: str) -> tuple:
        """Returns ``(durations_hours, factors)`` from the ``ClimateChange`` layer's
        ``rainfall_factors`` table for the given baseline year (2030-2100, in 10-year
        increments) and SSP scenario (SSP1/SSP2/SSP3/SSP5). The factors multiply the
        historical IFD depths. The table's duration columns are labelled e.g. ``"<1 hour"``
        (1 hour), ``"1.5 Hours"``, ..., ``">24 Hours"`` (24 hours)."""
        cc = self.layer('ClimateChange', required=True)
        rf_tables = cc.get('rainfall_factors')
        if not rf_tables:
            raise ArrApiError("ARR Data Hub response is missing 'ClimateChange' 'rainfall_factors' tables.")
        key = next((k for k in rf_tables if str(k).upper().startswith(ssp.upper())), None)
        if key is None:
            raise ArrApiError(
                f"ARR Data Hub 'ClimateChange' rainfall factor tables do not contain SSP '{ssp}' "
                f"(available: {list(rf_tables)})"
            )
        table = rf_tables[key]
        years = [int(y) for y in table['index']]
        if baseline_year not in years:
            raise ArrApiError(
                f"ARR Data Hub 'ClimateChange' rainfall factor table does not contain baseline year "
                f"'{baseline_year}' (available: {years})"
            )
        row = table['data'][years.index(baseline_year)]
        hours = []
        for col in table['columns']:
            m = re.search(r'\d+(?:\.\d+)?', str(col))
            if m is None:
                raise ArrApiError(f"Unrecognised 'ClimateChange' rainfall factor duration column '{col}'")
            hours.append(float(m.group()))
        return hours, [float(v) for v in row]

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
    """Fetches data from the ARR Data Hub API for a single site (point or catchment boundary) config.

    Failed requests (connection errors, timeouts, HTTP 429 and 5xx responses) are retried with exponential
    backoff. The number of retries is set by :attr:`ArrConfig.max_retries`.

    Parameters
    ----------
    base_url : str, optional
        The base URL of the ARR Data Hub API. Defaults to the public ARR Data Hub API
        (``https://data.arr-software.org/``).
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url

    def build_params(self, config: ArrConfig) -> dict:
        """Builds the query parameters for the API request, based on the config's site
        location (or catchment boundary) and which optional layers are required (e.g.
        climate change). Used both for GET point queries and as the form fields of a
        POST catchment-boundary upload (see :meth:`fetch`).

        Parameters
        ----------
        config : ArrConfig
            The ARR configuration to build the request parameters from.

        Returns
        -------
        dict
            The query parameters (or form fields) for the request.
        """
        params = {'type': 'json'}
        if config.site.catchment_boundary:
            # the centroid is derived from the uploaded boundary itself - no
            # lat_coord/lon_coord is sent for a catchment-boundary query.
            pass
        else:
            params['lat_coord'] = config.site.latitude
            params['lon_coord'] = config.site.longitude
        if config.site.outlet_latitude is not None:
            params['outlet_lat_coord'] = config.site.outlet_latitude
            params['outlet_lon_coord'] = config.site.outlet_longitude
        for layer in _BASE_LAYERS:
            params[layer] = 1
        frequent = any(is_frequent_ey(a) for a in config.events.aep)
        if config.climate_change.enabled or (frequent and config.ifd.baseline_year == 2030):
            params['ClimateChange'] = 1  # also needed to derive 2030 frequent event depths
        if frequent:
            params['AllBoMIFD'] = 1  # frequent event (12-2EY) IFD depths, v1.1+ only
        return params

    @staticmethod
    def _catchment_boundary_files(catchment_boundary: str) -> list[FilePart]:
        """Builds the ``shapeFile[]`` multipart file attachments for a catchment
        boundary upload. For a ``.shp`` path, also attaches its required
        ``.shx``/``.dbf`` siblings (and ``.prj``, if present) alongside it, matching the
        ARR Data Hub API's shapefile upload contract (see
        https://data.arr-software.org/about)."""
        path = Path(catchment_boundary)
        paths = [path]
        if path.suffix.lower() == '.shp':
            for sibling_ext in SHAPEFILE_REQUIRED_SIBLINGS:
                paths.append(path.with_suffix(sibling_ext))
            for sibling_ext in SHAPEFILE_OPTIONAL_SIBLINGS:
                sibling_path = path.with_suffix(sibling_ext)
                if sibling_path.is_file():
                    paths.append(sibling_path)
        files = []
        for p in paths:
            content_type = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
            files.append(FilePart(
                field_name='shapeFile[]', filename=p.name, content=p.read_bytes(), content_type=content_type,
            ))
        return files

    def fetch(self, config: ArrConfig) -> ArrApiResponse:
        """Requests data from the ARR Data Hub API for the given config's site (a
        lat/lon point, or an uploaded catchment boundary - see
        ``site.catchment_boundary``), and returns the parsed response.

        Parameters
        ----------
        config : ArrConfig
            The ARR configuration to fetch data for. The site location (or catchment boundary) and
            :attr:`ArrConfig.max_retries` are taken from this object.

        Returns
        -------
        ArrApiResponse
            The parsed ARR Data Hub response.

        Raises
        ------
        ArrApiError
            If the request fails (after exhausting any retries) or the response is not valid JSON.
        """
        params = self.build_params(config)
        if config.site.catchment_boundary:
            logger.info(
                "Requesting ARR Data Hub data for uploaded catchment boundary '%s'",
                config.site.catchment_boundary,
            )
            downloader = _download_with_retry(
                self.base_url, config.max_retries,
                method='POST', data=params,
                files=self._catchment_boundary_files(config.site.catchment_boundary),
            )
        else:
            query = '&'.join(f'{k}={v}' for k, v in params.items())
            url = f'{self.base_url}?{query}'
            logger.info('Requesting ARR Data Hub data: %s', url)
            downloader = _download_with_retry(url, config.max_retries)
        if not downloader.ok():
            raise ArrApiError(
                f"ARR Data Hub request failed (using {downloader.type()} downloader): "
                f"HTTP {downloader.ret_code}: {downloader.error_string}"
            )
        try:
            data = json.loads(downloader.data)
        except json.JSONDecodeError as e:
            raise ArrApiError(f"ARR Data Hub response is not valid JSON: {e}") from e
        response = ArrApiResponse(data)
        response.require_frequent_event_support(config.events.aep)
        return response

    def fetch_point_tp_for_coords(self, lat: float, lon: float) -> tuple:
        """Requests the ``PointTP`` and ``ArealTP`` layers for arbitrary coordinates,
        used to fetch an "additional" temporal pattern region's own point (and, if
        available, areal) temporal patterns (see ``temporal_patterns.additional_tp`` /
        :func:`pytuflow.arr.temporal_patterns.fetch_additional_region_point_tp`).
        Returns a ``(point_tp_layer, areal_tp_layer, raw_response)`` tuple: the raw
        ``PointTP`` layer dict (with its download ``url``), the raw ``ArealTP`` layer
        dict likewise (``None`` if the Data Hub doesn't provide one for these
        coordinates), and the full raw JSON response dict (kept for optional verbose
        working-data output, see :mod:`pytuflow.arr.working_data`).

        Parameters
        ----------
        lat : float
            Latitude of the additional temporal pattern region's representative location.
        lon : float
            Longitude of the additional temporal pattern region's representative location.

        Returns
        -------
        tuple
            ``(point_tp_layer, areal_tp_layer, raw_response)``: the ``PointTP`` layer dict, the ``ArealTP``
            layer dict (``None`` if not available), and the full raw JSON response dict.

        Raises
        ------
        ArrApiError
            If the request fails, the response is not valid JSON, or the ``PointTP`` layer is missing.
        """
        params = {
            'lat_coord': lat, 'lon_coord': lon, 'type': 'json',
            'TemporalPatterns': 1, 'ArealTemporalPatterns': 1,
        }
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        url = f'{self.base_url}?{query}'
        logger.info('Requesting ARR Data Hub PointTP/ArealTP data for additional temporal pattern region: %s', url)
        downloader = Downloader(url)
        downloader.download()
        if not downloader.ok():
            raise ArrApiError(
                f"ARR Data Hub request for additional temporal pattern region failed "
                f"(using {downloader.type()} downloader): HTTP {downloader.ret_code}: {downloader.error_string}"
            )
        try:
            data = json.loads(downloader.data)
        except json.JSONDecodeError as e:
            raise ArrApiError(f"ARR Data Hub response is not valid JSON: {e}") from e
        response = ArrApiResponse(data)
        return response.layer('PointTP', required=True), response.layer('ArealTP'), data

