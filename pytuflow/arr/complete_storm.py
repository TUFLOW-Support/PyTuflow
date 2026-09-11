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

* ``"recommended"`` (default) - uses the Data Hub's ``RecPreburstTP`` layer to select a
  specific historical event's preburst *duration and temporal pattern shape*
  (increments/timestep) for the requested AEP/duration - no extra
  interpolation/derivation needed for the shape. This is the only method available for
  AEP/duration cells where the burst initial loss table returns the ``"Use PB TP"``
  placeholder (see :mod:`pytuflow.arr.engine`), since those cells have no fixed burst
  initial loss value to derive a preburst depth from. If the Data Hub has no exact
  (Duration, AEP) match for this layer, the first available preburst pattern with the
  same duration and the same event rarity (AEP band) as the requested event is used
  instead (a warning is logged) - see :func:`recommended_preburst`. If the Data Hub has
  no ``RecPreburstTP`` data at all for this duration (e.g. very short durations below
  its minimum of 30 min), the first available point/design temporal pattern with the
  same duration and event rarity is used as the preburst shape instead (a warning is
  logged) - see :func:`_first_tp_preburst`. The preburst *depth* (magnitude) is not
  taken from ``RecPreburstTP`` at all (its own ``"Preburst Depth"``/``"Preburst Ratio"``
  fields are not used, since the Data Hub's ``"Preburst Depth"`` field is not actually a
  preburst depth) - instead, as with the ``"constant"``/``"temporal_pattern"`` methods
  below, it is derived from the ``preburst.percentile`` ratio table multiplied by the
  point design burst depth.
* ``"constant"`` - a single preburst block of a fixed duration (``preburst.pattern_duration``,
  in hours, or a proportion of the storm duration if ``preburst.duration_proportional``)
  at a constant rate, matching the legacy "Constant Rate" method.
* ``"temporal_pattern"`` - shapes the preburst rainfall using an existing point temporal
  pattern (``preburst.pattern_tp``) at the closest available duration to the computed
  preburst duration, matching the legacy non-constant method. ``preburst.pattern_tp``
  is either a specific pattern (e.g. ``"TP03"``, used for every design burst temporal
  pattern in the event), or ``"design_burst"``, which matches each design burst
  temporal pattern to a preburst pattern of the *same* ``tp_number`` (e.g. the
  ``"TP01"`` design burst gets a ``"TP01"`` preburst) - see
  :func:`temporal_pattern_preburst`.

For all three methods, the preburst depth is derived from the appropriate percentile
preburst ratio table (``Preburst10``/``25``/``50``/``75``/``90``, selected by
``preburst.percentile``), log-log interpolated (in duration and AEP, matching the IFD
depth interpolation) and multiplied by the point (pre-ARF) design burst depth -
matching the legacy script's use of ``PreBurst.get_depths()``. If
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
    method: str  # 'recommended' | 'constant' | 'temporal_pattern'
    event_id: Optional[int] = None  # only set for the 'recommended' method
    # only set for the 'temporal_pattern' method with pattern_tp == 'design_burst':
    # maps each design burst temporal pattern's `tp_number` to its own preburst
    # increments (all sharing the same `depth`/`timestep` above) - see
    # `temporal_pattern_preburst()`. `increments` above is simply the first of these,
    # for callers that don't care about the per-TP distinction.
    per_tp_increments: Optional[dict] = None


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
                          output_notation: str = 'ari', point_depth: Optional[float] = None,
                          percentile: str = '50%') -> Optional[PreburstPattern]:
    """Looks up the Data Hub's recommended preburst temporal pattern (``RecPreburstTP``
    layer) for the given duration/AEP, to use as the preburst *shape* (increments/
    timestep). If no exact (Duration, AEP) match is available, falls back to the first
    available preburst pattern with the same duration and the same event rarity (AEP
    band) as the requested event (see :func:`_same_duration_and_band_row`) - a warning
    is logged when this fallback is used. Returns ``None`` if no match is found at all
    (e.g. no preburst data available for that duration at all).

    The preburst *depth* (magnitude) is not taken from ``RecPreburstTP`` at all - its
    own ``"Preburst Depth"``/``"Preburst Ratio"`` fields are not used, since the Data
    Hub's ``"Preburst Depth"`` field is not actually a preburst depth. Instead, as with
    the ``"constant"``/``"temporal_pattern"`` methods, the depth is derived from the
    ``percentile`` ratio table (log-log interpolated - see :func:`_preburst_ratio`)
    multiplied by ``point_depth`` (the point design burst depth), which is therefore
    required.
    """
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
    if point_depth is None:
        raise ArrError("'point_depth' is required to derive the recommended preburst depth.")
    timestep = float(row['Increment Rate (min)'])
    inc_keys = sorted(
        (k for k in row if re.match(r'^Inc_\d+$', k)),
        key=lambda k: int(k.split('_')[1]),
    )
    raw = [float(row[k]) for k in inc_keys]
    # The Data Hub's raw Inc_* values are relative weights that do not sum to 100 (or to
    # 1) - normalise them to percentages summing to 100, matching the convention used
    # for design temporal pattern increments (multiplying by `depth / 100`).
    total = sum(raw)

    increments = [v / total * 100.0 for v in raw] if total else raw
    ratio = _preburst_ratio(response, percentile, duration, aep_pct)
    depth = ratio * float(point_depth)
    return PreburstPattern(
        depth=depth, timestep=timestep, increments=increments,
        method='recommended', event_id=int(row['Event ID']) if row.get('Event ID') is not None else None,
    )


def _first_tp_preburst(response: ArrApiResponse, config: ArrConfig, tp_set: TemporalPatternSet,
                        duration: float, aep_name: str, aep_pct: float, point_depth: float) -> Optional[PreburstPattern]:
    """Last-resort fallback for :func:`recommended_preburst`, used when the
    ``RecPreburstTP`` layer has no data at all for this duration (e.g. very short
    durations below the Data Hub's minimum ``RecPreburstTP`` duration of 30 min, which
    means :func:`_same_duration_and_band_row` also finds nothing to fall back to).
    Uses the first available point temporal pattern (lowest ``tp_number``) for the same
    duration and event rarity (AEP band) as the requested event as the preburst shape,
    scaled to the configured preburst ratio depth. Returns ``None`` if no point temporal
    patterns are available for that duration/band either."""
    if tp_set is None:
        return None
    from .temporal_patterns import aep_band
    band = aep_band(aep_name, config.events.output_notation)
    rows = tp_set.point_tp[(tp_set.point_tp['duration'] == duration) & (tp_set.point_tp['aep_band'] == band)]
    if rows.empty:
        return None
    row = rows.sort_values('tp_number').iloc[0]
    ratio = _preburst_ratio(response, config.preburst.percentile, duration, aep_pct)
    depth = ratio * point_depth
    logger.warning(
        "No recommended preburst temporal pattern available for %s/%smin at all ('RecPreburstTP' layer has no "
        "data for this duration) - falling back to the first design temporal pattern (TP%02d, same duration/event "
        "rarity) as the preburst shape.",
        aep_name, duration, int(row.tp_number),
    )
    return PreburstPattern(depth=depth, timestep=float(row.timestep), increments=list(row.increments), method='recommended')


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


def temporal_pattern_preburst(response: ArrApiResponse, config: ArrConfig, tp_set: TemporalPatternSet,
                               duration: float, aep_name: str, aep_pct: float, point_depth: float,
                               design_patterns: Optional[list] = None) -> PreburstPattern:
    """Shapes the preburst rainfall using a specific existing point temporal pattern
    (``preburst.pattern_tp``), matching the legacy non-constant preburst pattern method.

    ``preburst.pattern_tp`` is either a specific temporal pattern (e.g. ``"TP03"``),
    which is used for every design burst temporal pattern in this event, or
    ``"design_burst"``, which matches each design burst temporal pattern (in
    ``design_patterns`` - the actual point temporal patterns used for this event's
    design burst, i.e. ``TemporalPatternSet.patterns()``'s result) to the preburst
    pattern of the *same* ``tp_number``, so e.g. the ``"TP01"`` design burst gets a
    ``"TP01"`` preburst (see :attr:`PreburstPattern.per_tp_increments`)."""
    cfg = config.preburst
    if cfg.pattern_duration is None:
        raise ArrError("preburst.pattern_duration is required for the 'temporal_pattern' preburst pattern method.")
    if not cfg.pattern_tp:
        raise ArrError(
            "preburst.pattern_tp is required for the 'temporal_pattern' preburst pattern method - a specific "
            "temporal pattern (e.g. 'TP03') or 'design_burst'."
        )
    target_dur = _figure_out_pb_duration(duration, cfg.pattern_duration, cfg.duration_proportional)
    from .temporal_patterns import aep_band
    band = aep_band(aep_name, config.events.output_notation)
    available = sorted(tp_set.point_tp.loc[tp_set.point_tp['aep_band'] == band, 'duration'].unique())
    if not available:
        raise ArrError(f"No point temporal patterns available for AEP band '{band}' to build a preburst pattern from.")
    pb_duration = min(available, key=lambda d: abs(d - target_dur))
    ratio = _preburst_ratio(response, cfg.percentile, duration, aep_pct)
    depth = ratio * point_depth

    if cfg.pattern_tp == 'design_burst':
        if not design_patterns:
            raise ArrError(
                "No design burst temporal patterns available to match tp_number against for the "
                "'design_burst' preburst.pattern_tp option."
            )
        candidates = tp_set.point_tp[
            (tp_set.point_tp['duration'] == pb_duration) & (tp_set.point_tp['aep_band'] == band)
        ]
        per_tp_increments = {}
        timestep = None
        for p in design_patterns:
            rows = candidates[candidates['tp_number'] == p.tp_number]
            if rows.empty:
                raise ArrError(
                    f"Temporal pattern 'TP{p.tp_number:02d}' not found for duration {pb_duration} min, AEP band "
                    f"'{band}' to shape the preburst ('design_burst' preburst.pattern_tp option)."
                )
            row = rows.iloc[0]
            per_tp_increments[p.tp_number] = list(row.increments)
            timestep = float(row.timestep)
        first_tp = design_patterns[0].tp_number
        return PreburstPattern(
            depth=depth, timestep=timestep, increments=per_tp_increments[first_tp], method='temporal_pattern',
            per_tp_increments=per_tp_increments,
        )

    match = re.search(r'\d+', cfg.pattern_tp)
    if not match:
        raise ArrError(f"Unrecognised preburst.pattern_tp: '{cfg.pattern_tp}' (expected e.g. 'TP03', or 'design_burst').")
    tp_number = int(match.group())
    rows = tp_set.point_tp[
        (tp_set.point_tp['duration'] == pb_duration)
        & (tp_set.point_tp['aep_band'] == band)
        & (tp_set.point_tp['tp_number'] == tp_number)
    ]
    if rows.empty:
        raise ArrError(f"Temporal pattern '{cfg.pattern_tp}' not found for duration {pb_duration} min, AEP band '{band}'.")
    row = rows.iloc[0]
    return PreburstPattern(
        depth=depth, timestep=float(row.timestep), increments=list(row.increments), method='temporal_pattern',
    )


def build_preburst(response: ArrApiResponse, config: ArrConfig, tp_set: TemporalPatternSet,
                    duration: float, aep_name: str, aep_pct: float, point_depth: float,
                    design_patterns: Optional[list] = None) -> PreburstPattern:
    """Builds the preburst pattern to prepend to the design burst for a complete storm
    event, dispatching to the configured ``preburst.pattern_method`` (defaulting to
    ``"recommended"``). ``design_patterns`` (the design burst's own point temporal
    patterns for this event) is only required for the ``"temporal_pattern"`` method
    with ``preburst.pattern_tp == "design_burst"``."""
    method = (config.preburst.pattern_method or 'recommended').lower()
    if method == 'recommended':
        pattern = recommended_preburst(
            response, duration, aep_name, aep_pct, config.events.output_notation,
            point_depth=point_depth, percentile=config.preburst.percentile,
        )
        if pattern is None:
            pattern = _first_tp_preburst(response, config, tp_set, duration, aep_name, aep_pct, point_depth)
        if pattern is None:
            raise ArrError(
                f"No recommended preburst temporal pattern available for {aep_name}/{duration}min "
                f"('RecPreburstTP' layer) - try a different preburst.pattern_method."
            )
        return pattern
    if method == 'constant':
        return constant_preburst(response, config, duration, aep_name, aep_pct, point_depth)
    if method == 'temporal_pattern':
        return temporal_pattern_preburst(
            response, config, tp_set, duration, aep_name, aep_pct, point_depth, design_patterns=design_patterns)
    raise ArrError(f"Unrecognised preburst.pattern_method: '{config.preburst.pattern_method}'.")
