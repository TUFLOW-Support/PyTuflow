"""Complete storm (preburst-extended design burst) assembly for :mod:`pytuflow.arr`.

A "complete storm" prepends a preburst rainfall period ahead of the ARR design
burst, so that the burst initial loss can be expressed as the full storm initial loss
(rather than a reduced burst initial loss that already accounts for the preburst
rainfall having "used up" some of the loss). This module ports the relevant logic from
``ArrTemporal``/``export()`` in ``ARR_legacy/ARR_WebRes.py``, plus support for the ARR
Data Hub's new ``RecPreburstTP`` "recommended" preburst temporal pattern (which the
legacy script did not have access to).

Three preburst pattern methods are supported (``preburst.pattern_method`` in the
config):

* ``"recommended"`` (default) - uses the Data Hub's ``RecPreburstTP`` layer, which
  supplies a specific historical event's preburst duration/depth/increments directly
  for the requested AEP/duration - no extra interpolation/derivation required. This is
  the only method available for AEP/duration cells where the burst initial loss table
  returns the ``"Use PB TP"`` placeholder (see :mod:`pytuflow.arr.engine`), since those
  cells have no fixed burst initial loss value to derive a preburst depth from. If the
  Data Hub has no exact (Duration, AEP) match for this layer, the first available
  preburst pattern with the same duration and the same event rarity (AEP band) as the
  requested event is used instead (a warning is logged) - see
  :func:`recommended_preburst`.
* ``"constant"`` - a single preburst block of a fixed duration (``preburst.pattern_duration``,
  in hours, or a proportion of the storm duration if ``preburst.duration_proportional``)
  at a constant rate, matching the legacy "Constant Rate" method.
* ``"pattern"`` - shapes the preburst rainfall using a specific existing point temporal
  pattern (``preburst.pattern_tp``, e.g. ``"TP03"``) at the closest available duration to
  the computed preburst duration, matching the legacy non-constant method.

For the ``"constant"``/``"pattern"`` methods, the preburst depth is derived from the
appropriate percentile preburst ratio table (``Preburst10``/``25``/``50``/``75``/``90``,
selected by ``preburst.percentile``) multiplied by the point (pre-ARF) design burst
depth - matching the legacy script's use of ``PreBurst.get_depths()``. If
``preburst.percentile == "recommended"``, the Data Hub's ``RecPreburst`` layer (its
preferred/recommended preburst ratio) is used instead - this is not necessarily the
same value as the exact 50th percentile (``"50%"``).

If the resulting preburst depth is negligible relative to the point design burst depth
(implied preburst ratio < 0.01, i.e. less than 1%), the preburst period is dropped
entirely and the event falls back to a standard (non complete storm) burst - see
:meth:`pytuflow.arr.engine.ArrEngine.run`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .api_client import ArrApiResponse
from .config import ArrConfig
from .exceptions import ArrError
from .temporal_patterns import TemporalPatternSet

logger = logging.getLogger('pytuflow.arr')



@dataclass
class PreburstPattern:
    """A single preburst rainfall hyetograph to prepend ahead of the design burst."""
    depth: float  # mm
    timestep: float  # minutes
    increments: list  # percentages of `depth`, need not sum to exactly 100
    method: str  # 'recommended' | 'constant' | 'pattern'
    event_id: Optional[int] = None  # only set for the 'recommended' method


def _nearest_row(df: pd.DataFrame, duration: float, aep_pct: float) -> Optional[dict]:
    """Finds the closest matching (Duration, AEP) row in a `RecPreburstTP`-style
    ``selected_patterns`` list of dicts, requiring an exact match on both fields (the
    Data Hub only returns a fixed set of AEP/duration combinations for this layer)."""
    for row in df:
        if int(row['Duration']) == int(duration) and abs(float(row['AEP']) - aep_pct) < 1e-6:
            return row
    return None


def _same_duration_and_band_row(rows: list, duration: float, aep_name: str, output_notation: str) -> Optional[dict]:
    """Fallback for :func:`recommended_preburst`, when no exact (Duration, AEP) match is
    available: returns the first ``selected_patterns`` row with the same duration and
    the same event rarity (AEP band - ``'frequent'``/``'intermediate'``/``'rare'``,
    see :func:`pytuflow.arr.temporal_patterns.aep_band`) as the requested event, or
    ``None`` if none match."""
    from .temporal_patterns import aep_band
    target_band = aep_band(aep_name, output_notation)
    for row in rows:
        if int(row['Duration']) != int(duration):
            continue
        if aep_band(f"{float(row['AEP'])}%", output_notation) == target_band:
            return row
    return None


def recommended_preburst(response: ArrApiResponse, duration: float, aep_name: str, aep_pct: float,
                          output_notation: str = 'ari') -> Optional[PreburstPattern]:
    """Looks up the Data Hub's recommended preburst temporal pattern (``RecPreburstTP``
    layer) for the given duration/AEP. If no exact (Duration, AEP) match is available,
    falls back to the first available preburst pattern with the same duration and the
    same event rarity (AEP band) as the requested event (see
    :func:`_same_duration_and_band_row`) - a warning is logged when this fallback is
    used. Returns ``None`` if no match is found at all (e.g. no preburst data available
    for that duration at all)."""
    layer = response.layer('RecPreburstTP')
    if not layer or 'selected_patterns' not in layer:
        return None
    rows = layer['selected_patterns']
    row = _nearest_row(rows, duration, aep_pct)
    if row is None:
        row = _same_duration_and_band_row(rows, duration, aep_name, output_notation)
        if row is not None:
            logger.warning(
                "No recommended preburst temporal pattern available for %s/%smin - falling back to the "
                "preburst pattern for %s%% AEP/%smin (same duration, same event rarity).",
                aep_name, duration, row['AEP'], row['Duration'],
            )
    if row is None:
        return None
    timestep = float(row['Increment Rate (min)'])
    inc_keys = sorted(
        (k for k in row if re.match(r'^Inc_\d+$', k)),
        key=lambda k: int(k.split('_')[1]),
    )
    raw = [float(row[k]) for k in inc_keys]
    # The Data Hub's raw Inc_* values are relative weights that do not sum to 100 (or to
    # 1) - normalise them to percentages summing to 100 so that, downstream, multiplying
    # by `depth / 100` (the same convention used for design temporal pattern increments)
    # reproduces the authoritative 'Preburst Depth' total.
    total = sum(raw)

    increments = [v / total * 100.0 for v in raw] if total else raw
    return PreburstPattern(
        depth=float(row['Preburst Depth']), timestep=timestep, increments=increments,
        method='recommended', event_id=int(row['Event ID']) if row.get('Event ID') is not None else None,
    )


def _preburst_ratio(response: ArrApiResponse, percentile: str, duration: float, aep_pct: float) -> float:
    """Interpolates the preburst ratio (fraction of point burst depth) from the
    ``Preburst<percentile>`` layer (or, if ``percentile == 'recommended'``, the
    ``RecPreburst`` layer - the Data Hub's preferred/recommended preburst ratio, which
    is not necessarily the same as the exact 50th percentile) for the given
    duration/AEP, using the same log-log interpolation as the IFD depth tables."""
    from .engine import _interp_table, _table_to_frame  # local import - avoids a cycle
    key = 'RecPreburst' if percentile == 'recommended' else f'Preburst{percentile.strip("%")}'
    table = response.layer(key, required=True)
    df = _table_to_frame(table)
    return float(_interp_table(df, [duration], [aep_pct]).iloc[0, 0])


def _figure_out_pb_duration(target_duration: float, pattern_duration: float, duration_proportional: bool) -> float:
    """Computes the target preburst duration (minutes), given either an absolute
    duration (hours) or a proportion of the storm duration."""
    if duration_proportional:
        return target_duration * float(pattern_duration)
    return float(pattern_duration) * 60.0


def constant_preburst(response: ArrApiResponse, config: ArrConfig, duration: float,
                       aep_name: str, aep_pct: float, point_depth: float) -> PreburstPattern:
    """Builds a single constant-rate preburst block, matching the legacy "Constant Rate"
    preburst pattern method."""
    cfg = config.preburst
    if cfg.pattern_duration is None:
        raise ArrError("preburst.pattern_duration is required for the 'constant' preburst pattern method.")
    pb_duration = _figure_out_pb_duration(duration, cfg.pattern_duration, cfg.duration_proportional)
    ratio = _preburst_ratio(response, cfg.percentile, duration, aep_pct)
    depth = ratio * point_depth
    return PreburstPattern(depth=depth, timestep=pb_duration, increments=[100.0], method='constant')


def pattern_preburst(response: ArrApiResponse, config: ArrConfig, tp_set: TemporalPatternSet,
                      duration: float, aep_name: str, aep_pct: float, point_depth: float) -> PreburstPattern:
    """Shapes the preburst rainfall using a specific existing point temporal pattern
    (``preburst.pattern_tp``), matching the legacy non-constant preburst pattern method.
    """
    cfg = config.preburst
    if cfg.pattern_duration is None:
        raise ArrError("preburst.pattern_duration is required for the 'pattern' preburst pattern method.")
    if not cfg.pattern_tp or cfg.pattern_tp == 'design_burst':
        raise ArrError(
            "preburst.pattern_tp must be a specific temporal pattern (e.g. 'TP03') for the 'pattern' preburst "
            "pattern method - the legacy 'design_burst' (per-design-TP preburst) option is not yet supported."
        )
    target_dur = _figure_out_pb_duration(duration, cfg.pattern_duration, cfg.duration_proportional)
    from .temporal_patterns import aep_band
    band = aep_band(aep_name, config.events.output_notation)
    available = sorted(tp_set.point_tp.loc[tp_set.point_tp['aep_band'] == band, 'duration'].unique())
    if not available:
        raise ArrError(f"No point temporal patterns available for AEP band '{band}' to build a preburst pattern from.")
    pb_duration = min(available, key=lambda d: abs(d - target_dur))

    match = re.search(r'\d+', cfg.pattern_tp)
    if not match:
        raise ArrError(f"Unrecognised preburst.pattern_tp: '{cfg.pattern_tp}' (expected e.g. 'TP03').")
    tp_number = int(match.group())
    rows = tp_set.point_tp[
        (tp_set.point_tp['duration'] == pb_duration)
        & (tp_set.point_tp['aep_band'] == band)
        & (tp_set.point_tp['tp_number'] == tp_number)
    ]
    if rows.empty:
        raise ArrError(f"Temporal pattern '{cfg.pattern_tp}' not found for duration {pb_duration} min, AEP band '{band}'.")
    row = rows.iloc[0]
    ratio = _preburst_ratio(response, cfg.percentile, duration, aep_pct)
    depth = ratio * point_depth
    return PreburstPattern(depth=depth, timestep=float(row.timestep), increments=list(row.increments), method='pattern')


def build_preburst(response: ArrApiResponse, config: ArrConfig, tp_set: TemporalPatternSet,
                    duration: float, aep_name: str, aep_pct: float, point_depth: float) -> PreburstPattern:
    """Builds the preburst pattern to prepend to the design burst for a complete storm
    event, dispatching to the configured ``preburst.pattern_method`` (defaulting to
    ``"recommended"``)."""
    method = (config.preburst.pattern_method or 'recommended').lower()
    if method == 'recommended':
        pattern = recommended_preburst(response, duration, aep_name, aep_pct, config.events.output_notation)
        if pattern is None:
            raise ArrError(
                f"No recommended preburst temporal pattern available for {aep_name}/{duration}min "
                f"('RecPreburstTP' layer) - try a different preburst.pattern_method."
            )
        return pattern
    if method == 'constant':
        return constant_preburst(response, config, duration, aep_name, aep_pct, point_depth)
    if method == 'pattern':
        return pattern_preburst(response, config, tp_set, duration, aep_name, aep_pct, point_depth)
    raise ArrError(f"Unrecognised preburst.pattern_method: '{config.preburst.pattern_method}'.")
