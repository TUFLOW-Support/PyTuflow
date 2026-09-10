"""Temporal pattern download and selection, ported from ``ArrTemporal`` in
``ARR_legacy/ARR_WebRes.py``.

The ARR Data Hub's ``PointTP``/``ArealTP`` layers no longer embed the actual pattern
increments - they just return a ``url`` to a zip file containing an ``*_Increments.csv``
(and an ``*_AllStats.csv``, which is not currently used). This module downloads and
parses those increment CSVs, and selects the appropriate temporal pattern(s) for a given
AEP/duration, combining point and areal temporal patterns the same way the legacy script
did (Book 2, Chapter 5 of ARR).
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

import pandas as pd

from .downloader import Downloader, DownloaderRequests
from .exceptions import ArrApiError, ArrError

logger = logging.getLogger('pytuflow.arr')

#: AEP-band areal TP catchment area buckets (km2), ARR Book 2 Chapter 5.
_AREAL_TP_AREAS = (100, 200, 500, 1000, 2500, 5000, 10000, 20000, 40000)


def aep_band(aep_name: str, output_notation: str = 'ari') -> str:
    """Returns the ARR temporal pattern AEP band (``'frequent'``, ``'intermediate'``,
    or ``'rare'``) for a given AEP/ARI/EY magnitude label, per ARR Figure 2.5.12.

    Parameters
    ----------
    aep_name : str
        AEP/ARI/EY magnitude label (e.g. ``'1%'``, ``'1 in 200'``, ``'0.5EY'``).
    output_notation : str
        ``'ari'`` or ``'aep'`` - only used to log the ARR ARI/AEP mismatch warnings
        for 50%/20% AEP (matching legacy behaviour); does not affect the returned band.
    """
    aep_name = str(aep_name).strip()
    if aep_name.endswith('EY'):
        return 'frequent'
    if aep_name.lower().startswith('1 in'):
        logger.warning(
            "'%s' event is considered 'Very Rare'. Temporal patterns for 'Very Rare' events are not yet "
            "provided... using 'Rare' temporal patterns.", aep_name
        )
        return 'rare'
    if aep_name.endswith('%'):
        pct = float(aep_name[:-1])
        if pct < 1:
            logger.warning(
                "%s%% AEP event is considered 'Very Rare'. Temporal patterns for 'Very Rare' events are not "
                "yet provided... using 'Rare' temporal patterns.", aep_name[:-1]
            )
            return 'rare'
        if pct <= 3.2:
            return 'rare'
        if pct <= 14.4:
            return 'intermediate'
        return 'frequent'
    raise ArrError(f"Unrecognised AEP/ARI/EY magnitude: '{aep_name}'")


def nearest_areal_tp_area(catchment_area: float) -> Optional[int]:
    """Returns the areal temporal pattern catchment-area bucket (km2) to use for a given
    catchment area, or ``None`` if the catchment is too small (< 75 km2) for areal
    temporal patterns to apply (point temporal patterns should be used instead)."""
    area = float(catchment_area)
    if area < 75:
        return None
    for bucket in _AREAL_TP_AREAS:
        if area <= bucket:
            return bucket
    return _AREAL_TP_AREAS[-1]


def _iter_csv_rows(csv_text: str):
    """Yields each data row (as a list of stripped string fields) from an increments
    CSV, skipping the header row and any blank rows. Uses the ``csv`` module directly
    rather than ``pandas.read_csv`` because these files have a ragged number of columns
    (the increments column count varies by duration) which trips up strict CSV readers.
    """
    import csv
    reader = csv.reader(io.StringIO(csv_text))
    next(reader, None)  # header
    for parts in reader:
        if not parts or not parts[0].strip():
            continue
        yield [p.strip() for p in parts]


def _download_increments_csv(url: str) -> str:
    """Downloads a temporal pattern zip file from ``url`` and returns the decoded
    contents of the ``*_Increments.csv`` file within it.

    The Data Hub API has been observed to return internal-network URLs (e.g.
    ``192.168.x.x``) for these zip downloads rather than the public API host - if the
    URL as given fails to connect, this retries once against the public Data Hub host
    with the same path, which is otherwise identical.
    """
    try:
        return _fetch_zip_increments_csv(url)
    except Exception:
        from .api_client import DEFAULT_BASE_URL
        parsed = urlsplit(url)
        fallback_host = urlsplit(DEFAULT_BASE_URL).netloc
        if parsed.netloc == fallback_host:
            raise
        fallback_url = urlunsplit((urlsplit(DEFAULT_BASE_URL).scheme, fallback_host, parsed.path, parsed.query, parsed.fragment))
        logger.warning("Failed to download temporal pattern zip from '%s'; retrying against '%s'.", url, fallback_url)
        return _fetch_zip_increments_csv(fallback_url)


def _fetch_zip_increments_csv(url: str) -> str:
    downloader = Downloader(url)
    kwargs = {'timeout': (5, 20)} if isinstance(downloader, DownloaderRequests) else {}
    downloader.download(**kwargs)
    if not downloader.ok():
        raise ArrApiError(
            f"Failed to download temporal pattern zip '{url}' (using {downloader.type()} downloader): "
            f"HTTP {downloader.ret_code}: {downloader.error_string}"
        )
    data = downloader.data
    if isinstance(data, str):
        data = data.encode('utf-8')
    z = zipfile.ZipFile(io.BytesIO(data))
    names = [n for n in z.namelist() if 'increments' in n.lower()]
    if not names:
        raise ArrApiError(f"Temporal pattern zip '{url}' does not contain an Increments CSV.")
    return z.read(names[0]).decode('utf-8')


def parse_point_tp_csv(csv_text: str) -> pd.DataFrame:
    """Parses a point temporal pattern ``*_Increments.csv`` file into a long-format
    DataFrame with one row per pattern.

    Returns
    -------
    pd.DataFrame
        Columns: ``event_id``, ``duration`` (min), ``timestep`` (min), ``region``,
        ``aep_band`` (frequent/intermediate/rare, lowercase), ``tp_number`` (1-10, cycles
        within each duration+band group), ``increments`` (list[float], percentages).
    """
    rows = []
    counters: dict = {}
    for parts in _iter_csv_rows(csv_text):
        duration = int(parts[1])
        timestep = float(parts[2])
        band = parts[4].strip().lower()
        key = (duration, band)
        counters[key] = counters.get(key, 0) + 1
        tp_number = counters[key]
        if tp_number > 10:
            tp_number = ((tp_number - 1) % 10) + 1
        n = int(duration / timestep)
        increments = [float(v) for v in parts[5:5 + n]]
        rows.append({
            'event_id': int(parts[0]), 'duration': duration, 'timestep': timestep,
            'region': parts[3].strip(), 'aep_band': band, 'tp_number': tp_number,
            'increments': increments,
        })
    return pd.DataFrame(rows)


def parse_areal_tp_csv(csv_text: str) -> pd.DataFrame:
    """Parses an areal temporal pattern ``*_Increments.csv`` file into a long-format
    DataFrame with one row per pattern.

    Returns
    -------
    pd.DataFrame
        Columns: ``event_id``, ``duration`` (min), ``timestep`` (min), ``region``,
        ``area`` (km2), ``tp_number`` (1-10, cycles within each duration+region group),
        ``increments`` (list[float], percentages).
    """
    rows = []
    counters: dict = {}
    for parts in _iter_csv_rows(csv_text):
        duration = int(parts[1])
        timestep = float(parts[2])
        region = parts[3].strip()
        area = int(float(parts[4]))
        key = (duration, area, region)
        counters[key] = counters.get(key, 0) + 1
        tp_number = counters[key]
        if tp_number > 10:
            tp_number = ((tp_number - 1) % 10) + 1
        n = int(duration / timestep)
        increments = [float(v) for v in parts[5:5 + n]]
        rows.append({
            'event_id': int(parts[0]), 'duration': duration, 'timestep': timestep,
            'region': region, 'area': area, 'tp_number': tp_number, 'increments': increments,
        })
    return pd.DataFrame(rows)


@dataclass
class TemporalPattern:
    """A single selected temporal pattern for a given duration/AEP."""
    event_id: int
    tp_number: int
    timestep: float  # minutes
    increments: list  # percentages, sums to ~100
    source: str  # 'point' or 'areal'
    region: Optional[str] = None  # TP region label - distinguishes 'additional_tp' regions
    band: Optional[str] = None  # AEP band this pattern was selected from - set when 'all_point_tp' pulls in extra bands
    group: int = 0  # 0 = primary areal TP area bucket, 1.. = 'add_areal_tp' additional (next closest) buckets


#: Named additional temporal pattern regions and their representative lat/lon
#: coordinates, ported from the legacy script's ``ARR_TUFLOW_func_lib.tpRegion_coords()``
#: - used to fetch that region's own point temporal patterns as "additional"
#: realisations (see ``temporal_patterns.additional_tp`` / :func:`fetch_additional_region_point_tp`).
TP_REGION_COORDS = {
    'rangelands west': (-23.3026, 118.1178),
    'wet tropics': (-16.9202, 145.7727),
    'rangelands': (-23.70173, 133.8766),
    'central slopes': (-26.5715, 148.7845),
    'monsoonal north': (-12.4538, 130.8412),
    'murray basin': (-35.3086, 149.1244),
    'east coast north': (-27.6541, 152.6674),
    'east coast south': (-33.8701, 151.2063),
    'southern slopes mainland': (-37.8171, 144.9552),
    'southern slopes tasmania': (-42.8798, 147.3217),
    'east flatlands': (-34.9237, 138.6000),
    'west flatlands': (-31.9509, 115.8578),
}


@dataclass
class AdditionalRegionTP:
    """Result of :func:`fetch_additional_region_point_tp`/:func:`load_additional_region_point_tp_csv`:
    the parsed point temporal pattern rows for the additional region, plus the raw ARR
    Data Hub JSON response (``None`` if loaded from a local CSV file rather than
    fetched from the Data Hub) and increments CSV text, kept for optional verbose
    working-data output (see :mod:`pytuflow.arr.working_data`)."""
    region: str
    dataframe: pd.DataFrame
    csv_text: str
    raw_response: Optional[dict] = None


def fetch_additional_region_point_tp(region_name: str, base_url: Optional[str] = None) -> AdditionalRegionTP:
    """Fetches and parses the point temporal patterns for a named additional TP region
    (``temporal_patterns.additional_tp``), by issuing a separate ARR Data Hub API
    request for that region's representative coordinates (see
    :data:`TP_REGION_COORDS`). The resulting rows' ``region`` column is overwritten
    with the title-cased ``region_name`` so they can be distinguished from the site's
    own patterns downstream (see :meth:`TemporalPatternSet.add_region_patterns`)."""
    key = region_name.strip().lower()
    if key not in TP_REGION_COORDS:
        raise ArrError(
            f"Unrecognised additional temporal pattern region: '{region_name}' - must be one of "
            f"{sorted(k.title() for k in TP_REGION_COORDS)}."
        )
    lat, lon = TP_REGION_COORDS[key]
    from .api_client import ArrApiClient
    client = ArrApiClient(base_url) if base_url else ArrApiClient()
    logger.info("Fetching additional temporal patterns for region '%s' (%s, %s).", region_name, lat, lon)
    point_tp_layer, raw_response = client.fetch_point_tp_for_coords(lat, lon)
    csv_text = _download_increments_csv(point_tp_layer['url'])
    df = parse_point_tp_csv(csv_text)
    df = df.copy()
    region_title = region_name.strip().title()
    df['region'] = region_title
    return AdditionalRegionTP(region=region_title, dataframe=df, raw_response=raw_response, csv_text=csv_text)


def load_additional_region_point_tp_csv(csv_path: str) -> AdditionalRegionTP:
    """Loads point temporal pattern increments from a local CSV file
    (``temporal_patterns.additional_tp`` entries that are file paths rather than named
    regions) instead of fetching them from the Data Hub - e.g. a previous run's
    ``<site>_PointTP_Increments.csv``/``<site>_PointTP_Increments_<region>.csv``
    working-data output, or any other file in the same ARR Data Hub increments CSV
    format. Unlike :func:`fetch_additional_region_point_tp`, the region label is taken
    directly from the CSV's own ``Region`` column rather than overwritten, since the
    file may already contain a meaningful region name (or several, if hand-assembled)."""
    path = Path(csv_path)
    if not path.is_file():
        raise ArrError(f"Additional temporal pattern CSV file not found: '{csv_path}'")
    csv_text = path.read_text(encoding='utf-8')
    df = parse_point_tp_csv(csv_text)
    if df.empty:
        raise ArrError(f"Additional temporal pattern CSV file '{csv_path}' contains no data rows.")
    region = str(df['region'].iloc[0]).strip()
    logger.info("Loaded additional temporal patterns for region '%s' from local file '%s'.", region, csv_path)
    return AdditionalRegionTP(region=region, dataframe=df, csv_text=csv_text)


class TemporalPatternSet:
    """Combined point + (optional) areal temporal patterns for a single catchment,
    replicating ``ArrTemporal.combineArealTp`` from the legacy script.

    Areal temporal patterns are used in preference to point temporal patterns for any
    duration where an areal pattern is available for the catchment's area bucket,
    *and* the duration is >= the shortest duration provided by the areal pattern set
    (shorter durations always use the point pattern, matching legacy behaviour).

    Note: unlike the legacy script, this does not implement the "borrow from the next
    closest areal TP area bucket" fallback when a duration/region combination runs out
    of the standard 10 realizations for the chosen area bucket - if that happens, this
    falls back to the point temporal pattern for that duration instead, with a warning
    logged. This can be revisited if it turns out to matter in practice.
    """

    def __init__(self, point_tp: pd.DataFrame, areal_tp: Optional[pd.DataFrame] = None,
                 catchment_area: Optional[float] = None, point_tp_csv: Optional[str] = None,
                 areal_tp_csv: Optional[str] = None) -> None:
        self.point_tp = point_tp
        self.areal_tp = areal_tp
        self.tp_area = nearest_areal_tp_area(catchment_area) if catchment_area is not None else None
        #: region name(s) present in the catchment's own (native) point temporal
        #: patterns, captured before any :meth:`add_region_patterns` calls - used to
        #: ensure native patterns are always sorted/output before any additional
        #: ``additional_tp`` region patterns (see :meth:`patterns`).
        self._native_point_regions = set(point_tp['region'].unique()) if point_tp is not None and not point_tp.empty else set()
        #: raw downloaded increments CSV text, kept only for optional verbose working-data
        #: output (see :mod:`pytuflow.arr.working_data`) - not otherwise used.
        self.point_tp_csv = point_tp_csv
        self.areal_tp_csv = areal_tp_csv

    @classmethod
    def from_api_response(cls, point_tp_url: str, areal_tp_url: Optional[str] = None,
                           catchment_area: Optional[float] = None) -> 'TemporalPatternSet':
        """Downloads and parses point (and optionally areal) temporal patterns directly
        from the Data Hub API's supplied download URLs."""
        point_csv = _download_increments_csv(point_tp_url)
        point_tp = parse_point_tp_csv(point_csv)
        areal_csv = None
        areal_tp = None
        if areal_tp_url:
            areal_csv = _download_increments_csv(areal_tp_url)
            areal_tp = parse_areal_tp_csv(areal_csv)
        return cls(point_tp, areal_tp, catchment_area, point_tp_csv=point_csv, areal_tp_csv=areal_csv)

    @classmethod
    def from_files(cls, point_tp_path: str, areal_tp_path: Optional[str] = None,
                   catchment_area: Optional[float] = None) -> 'TemporalPatternSet':
        """Loads point (and optionally areal) temporal patterns from local increments
        CSV files (``temporal_patterns.point_tp_csv``/``areal_tp_csv``) - in the same
        format as the Data Hub's own ``*_Increments.csv`` files (e.g. a previous run's
        ``working_data`` output) - instead of downloading them from the Data Hub API."""
        point_path = Path(point_tp_path)
        if not point_path.is_file():
            raise ArrError(f"temporal_patterns.point_tp_csv file not found: '{point_tp_path}'")
        point_csv = point_path.read_text(encoding='utf-8')
        point_tp = parse_point_tp_csv(point_csv)
        areal_csv = None
        areal_tp = None
        if areal_tp_path:
            areal_path = Path(areal_tp_path)
            if not areal_path.is_file():
                raise ArrError(f"temporal_patterns.areal_tp_csv file not found: '{areal_tp_path}'")
            areal_csv = areal_path.read_text(encoding='utf-8')
            areal_tp = parse_areal_tp_csv(areal_csv)
        logger.info("Loaded point temporal patterns from local file '%s'%s.", point_tp_path,
                    f" and areal temporal patterns from '{areal_tp_path}'" if areal_tp_path else "")
        return cls(point_tp, areal_tp, catchment_area, point_tp_csv=point_csv, areal_tp_csv=areal_csv)

    def add_region_patterns(self, region_point_tp: pd.DataFrame) -> None:
        """Appends additional point temporal pattern rows (e.g. from
        :func:`fetch_additional_region_point_tp`) to this set's point temporal
        patterns - they are included alongside the site's own patterns for any
        matching duration/AEP band (see :meth:`patterns`), each tagged with their own
        ``region`` value so they can be told apart downstream (see
        :mod:`pytuflow.arr.writers`)."""
        self.point_tp = pd.concat([self.point_tp, region_point_tp], ignore_index=True)

    def _areal_candidates(self, duration: int, area: Optional[int] = None) -> pd.DataFrame:
        area = self.tp_area if area is None else area
        if self.areal_tp is None or area is None:
            return pd.DataFrame()
        df = self.areal_tp[(self.areal_tp['area'] == area) & (self.areal_tp['duration'] == duration)]
        return df

    def _additional_areal_patterns(self, duration: int, n: int) -> list:
        """Adds ``n`` additional sets of areal temporal patterns from the next ``n``
        closest (larger) catchment area buckets beyond the one actually used for this
        catchment (``temporal_patterns.add_areal_tp``) - e.g. ``n=1`` adds one extra set
        (up to 10 patterns) from the next closest area bucket, ``n=2`` adds two extra
        sets (up to 20 patterns) from the next two closest buckets, etc."""
        results = []
        if self.tp_area is None or self.areal_tp is None:
            return results
        start = _AREAL_TP_AREAS.index(self.tp_area)
        added = 0
        for i in range(1, n + 1):
            idx = start + i
            if idx >= len(_AREAL_TP_AREAS):
                logger.warning(
                    "Limiting number of additional areal temporal patterns to %d (ran out of larger area "
                    "buckets beyond %s km2).", added, self.tp_area,
                )
                break
            next_area = _AREAL_TP_AREAS[idx]
            candidates = self._areal_candidates(duration, next_area)
            if candidates.empty:
                logger.warning(
                    "No areal temporal pattern available for duration %s min at the next closest area bucket "
                    "(%s km2) - skipping additional areal temporal pattern set %d.", duration, next_area, i,
                )
                continue
            for r in candidates.sort_values('tp_number').itertuples():
                results.append(TemporalPattern(
                    int(r.event_id), int(r.tp_number), float(r.timestep), r.increments, 'areal',
                    region=r.region, group=i,
                ))
            added += 1
        return results

    def patterns(self, duration: int, aep_name: str, output_notation: str = 'ari',
                 all_point_tp: bool = False, add_areal_tp: int = 0) -> list:
        """Returns the list of :class:`TemporalPattern` to use for the given
        duration/AEP, preferring areal patterns where available for the catchment,
        otherwise falling back to point patterns for that AEP band.

        Parameters
        ----------
        duration : int
            Storm duration (minutes).
        aep_name : str
            AEP/ARI/EY magnitude label (e.g. ``'1%'``).
        output_notation : str
            ``'ari'`` or ``'aep'`` (passed through to :func:`aep_band` for warning text
            only).
        all_point_tp : bool
            If ``True`` (``temporal_patterns.all_point_tp``), and this duration uses
            point (not areal) temporal patterns, also includes the point temporal
            patterns for the other two AEP bands (``'frequent'``/``'intermediate'``/``'rare'``)
            alongside the requested event's own band - i.e. all point temporal patterns
            for that duration, regardless of event rarity.
        add_areal_tp : int
            If > 0 (``temporal_patterns.add_areal_tp``), and this duration uses areal
            temporal patterns, also includes this many additional sets of areal
            temporal patterns from the next closest (larger) catchment area buckets -
            see :meth:`_additional_areal_patterns`.
        """
        band = aep_band(aep_name, output_notation)

        areal_min_dur = int(self.areal_tp['duration'].min()) if self.areal_tp is not None and not self.areal_tp.empty else None
        use_areal = (
            self.tp_area is not None
            and areal_min_dur is not None
            and duration >= areal_min_dur
        )
        if use_areal:
            candidates = self._areal_candidates(duration)
            if not candidates.empty:
                results = [
                    TemporalPattern(int(r.event_id), int(r.tp_number), float(r.timestep), r.increments, 'areal',
                                    region=r.region)
                    for r in candidates.sort_values('tp_number').itertuples()
                ]
                if add_areal_tp:
                    results.extend(self._additional_areal_patterns(duration, add_areal_tp))
                return results
            logger.warning(
                "No areal temporal pattern available for duration %s min (area bucket %s km2) - "
                "falling back to point temporal pattern.", duration, self.tp_area
            )

        bands = [band]
        if all_point_tp:
            bands.extend(b for b in ('frequent', 'intermediate', 'rare') if b != band)

        results = []
        for b in bands:
            candidates = self.point_tp[(self.point_tp['duration'] == duration) & (self.point_tp['aep_band'] == b)]
            if candidates.empty:
                if b == band:
                    raise ArrError(f"No point temporal pattern available for duration {duration} min, AEP band '{b}'.")
                logger.warning(
                    "No point temporal pattern available for duration %s min, AEP band '%s' ('all_point_tp') - "
                    "skipping.", duration, b,
                )
                continue
            band_results = [
                TemporalPattern(
                    int(r.event_id), int(r.tp_number), float(r.timestep), r.increments, 'point',
                    region=r.region, band=b,
                )
                for r in candidates.itertuples()
            ]
            # ensure the catchment's own (native) region patterns are listed first within
            # this band, ahead of any additional `additional_tp` region patterns (which
            # would otherwise sort alphabetically by region name and could sort before
            # the native region).
            band_results.sort(key=lambda p: (p.region not in self._native_point_regions, p.region, p.tp_number))
            results.extend(band_results)
        return results

    def available_durations(self, aep_name: str, output_notation: str = 'ari') -> list:
        """Returns the sorted list of durations (minutes) with a point temporal pattern
        available for the given AEP's band (areal durations are a subset/superset
        depending on catchment - see :meth:`patterns`)."""
        band = aep_band(aep_name, output_notation)
        durs = self.point_tp.loc[self.point_tp['aep_band'] == band, 'duration'].unique().tolist()
        return sorted(int(d) for d in durs)
