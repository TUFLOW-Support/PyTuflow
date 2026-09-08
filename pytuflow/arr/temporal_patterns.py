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
                 catchment_area: Optional[float] = None) -> None:
        self.point_tp = point_tp
        self.areal_tp = areal_tp
        self.tp_area = nearest_areal_tp_area(catchment_area) if catchment_area is not None else None

    @classmethod
    def from_api_response(cls, point_tp_url: str, areal_tp_url: Optional[str] = None,
                           catchment_area: Optional[float] = None) -> 'TemporalPatternSet':
        """Downloads and parses point (and optionally areal) temporal patterns directly
        from the Data Hub API's supplied download URLs."""
        point_csv = _download_increments_csv(point_tp_url)
        point_tp = parse_point_tp_csv(point_csv)
        areal_tp = None
        if areal_tp_url:
            areal_csv = _download_increments_csv(areal_tp_url)
            areal_tp = parse_areal_tp_csv(areal_csv)
        return cls(point_tp, areal_tp, catchment_area)

    def _areal_candidates(self, duration: int) -> pd.DataFrame:
        if self.areal_tp is None or self.tp_area is None:
            return pd.DataFrame()
        df = self.areal_tp[(self.areal_tp['area'] == self.tp_area) & (self.areal_tp['duration'] == duration)]
        return df

    def patterns(self, duration: int, aep_name: str, output_notation: str = 'ari') -> list:
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
                return [
                    TemporalPattern(int(r.event_id), int(r.tp_number), float(r.timestep), r.increments, 'areal')
                    for r in candidates.sort_values('tp_number').itertuples()
                ]
            logger.warning(
                "No areal temporal pattern available for duration %s min (area bucket %s km2) - "
                "falling back to point temporal pattern.", duration, self.tp_area
            )

        candidates = self.point_tp[(self.point_tp['duration'] == duration) & (self.point_tp['aep_band'] == band)]
        if candidates.empty:
            raise ArrError(f"No point temporal pattern available for duration {duration} min, AEP band '{band}'.")
        return [
            TemporalPattern(int(r.event_id), int(r.tp_number), float(r.timestep), r.increments, 'point')
            for r in candidates.sort_values('tp_number').itertuples()
        ]

    def available_durations(self, aep_name: str, output_notation: str = 'ari') -> list:
        """Returns the sorted list of durations (minutes) with a point temporal pattern
        available for the given AEP's band (areal durations are a subset/superset
        depending on catchment - see :meth:`patterns`)."""
        band = aep_band(aep_name, output_notation)
        durs = self.point_tp.loc[self.point_tp['aep_band'] == band, 'duration'].unique().tolist()
        return sorted(int(d) for d in durs)
