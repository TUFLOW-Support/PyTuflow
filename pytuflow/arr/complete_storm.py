"""Complete storm (preburst-extended design burst) assembly for :mod:`pytuflow.arr`.

A "complete storm" prepends a preburst rainfall period ahead of the ARR design
burst, so that the burst initial loss can be expressed as the full storm initial loss
(rather than a reduced burst initial loss that already accounts for the preburst
rainfall having "used up" some of the loss). This module ports the relevant logic from
``ArrTemporal``/``export()`` in ``ARR_legacy/ARR_WebRes.py``, plus support for the ARR
Data Hub's new ``RecPreburstTP`` "recommended" preburst temporal pattern (which the
legacy script did not have access to).

Four preburst pattern methods are supported (``preburst.pattern_method`` in the
config):

* ``"recommended"`` (default) - uses the Data Hub's ``RecPreburstTP`` layer to select a
  specific historical event's preburst *duration and temporal pattern shape*
  (increments/timestep) for the requested AEP/duration - no extra
  interpolation/derivation needed for the shape. This is the preferred method for
  AEP/duration cells where the burst initial loss table returns the ``"Use PB TP"``
  placeholder (see :mod:`pytuflow.arr.engine`), since those cells have no fixed burst
  initial loss value to derive a preburst depth from. If the Data Hub has no exact
  (Duration, AEP) match for this layer, the preburst pattern for the *same* AEP as
  requested, whose *duration* is closest to the requested duration, is used instead (a
  warning is logged) - see :func:`recommended_preburst`/
  :func:`_closest_duration_same_aep_row`. If no row at all shares the requested AEP
  (and, failing that, no row at all shares the requested duration), further fallbacks
  based on the same event rarity (AEP band) are used instead - see
  :func:`_same_duration_and_band_row`/:func:`_closest_duration_and_band_row`.
  ``RecPreburstTP`` is an NSW-only
  layer - if the Data Hub has no ``RecPreburstTP`` data at all for the queried location
  (e.g. any non-NSW location), this falls back further still to shaping the preburst
  using ``preburst.pattern_duration``/``pattern_tp``/``duration_proportional`` (the same
  settings as the ``"temporal_pattern"`` method below, defaulting to a preburst twice
  the storm duration, shaped by ``"TP01"``, capped at ``pattern_duration_max`` hours) -
  a warning is logged - see
  :func:`build_preburst`. The preburst *depth* (magnitude) is not taken from
  ``RecPreburstTP`` at all (its own ``"Preburst Depth"``/``"Preburst Ratio"`` fields are
  not used, since the Data Hub's ``"Preburst Depth"`` field is not actually a preburst
  depth) - instead, as with the ``"constant"``/``"temporal_pattern"`` methods below, it
  is derived from the ``preburst.percentile`` ratio table multiplied by the point design
  burst depth.
* ``"constant"`` - a single preburst block of a fixed duration (``preburst.pattern_duration``,
  in hours, or a proportion of the storm duration if ``preburst.duration_proportional``,
  capped at ``pattern_duration_max`` hours in the proportional case)
  at a constant rate, matching the legacy "Constant Rate" method.
* ``"temporal_pattern"`` - shapes the preburst rainfall using an existing point temporal
  pattern (``preburst.pattern_tp``) at the closest available duration to the computed
  preburst duration (see ``pattern_duration_max`` above), matching the legacy
  non-constant method. ``preburst.pattern_tp``
  is either a specific pattern (e.g. ``"TP03"``, used for every design burst temporal
  pattern in the event), or ``"design_burst"``, which matches each design burst
  temporal pattern to a preburst pattern of the *same* ``tp_number`` (e.g. the
  ``"TP01"`` design burst gets a ``"TP01"`` preburst) - see
  :func:`temporal_pattern_preburst`.
* ``"none"`` - disables complete storm assembly for any AEP/duration cell that would
  otherwise auto-trigger it (a ``"Use PB TP"`` placeholder cell, or a missing burst
  initial loss table entirely - see :mod:`pytuflow.arr.engine`): instead of building a
  preburst pattern, the burst initial loss for that cell is simply set to 0 (a warning
  is logged). Cannot be combined with ``complete_storm: true`` (which forces every
  event to be a complete storm, and therefore always needs a preburst pattern to be
  built) - see :meth:`pytuflow.arr.config.ArrConfig.validate`.

For the first three methods, the preburst depth is derived from the appropriate
percentile preburst ratio table (``Preburst10``/``25``/``50``/``75``/``90``, selected by
``preburst.percentile``), log-linear interpolated (duration and AEP axes are
log-interpolated, but the ratio values themselves are interpolated linearly, since a
ratio can be exactly 0.0 - see :func:`_preburst_ratio`) and multiplied by the point
(pre-ARF) design burst depth -
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


def _closest_duration_same_aep_row(rows: list, duration: float, aep_pct: float) -> Optional[dict]:
    """Primary fallback for :func:`recommended_preburst`, when no exact (Duration, AEP)
    match is available: among ``selected_patterns`` rows for the *same* (exact) AEP as
    requested, returns the one whose *duration* is closest to the requested duration,
    breaking ties (two candidate durations equally close) by choosing the lower
    duration. Returns ``None`` if no row at all shares the requested AEP."""
    candidates = [row for row in rows if abs(float(row['AEP']) - aep_pct) < 1e-6]
    if not candidates:
        return None
    min_dist = min(abs(float(row['Duration']) - duration) for row in candidates)
    tied = [row for row in candidates if abs(float(row['Duration']) - duration) == min_dist]
    return min(tied, key=lambda row: float(row['Duration']))


def _same_duration_and_band_row(rows: list, duration: float, aep_name: str, aep_pct: float,
                                 output_notation: str) -> Optional[dict]:
    """Fallback for :func:`recommended_preburst`, when no exact (Duration, AEP) match is
    available: among ``selected_patterns`` rows with the same duration and the same
    event rarity (AEP band - ``'frequent'``/``'intermediate'``/``'rare'``, see
    :func:`pytuflow.arr.temporal_patterns.aep_band`) as the requested event, returns
    the one whose AEP is *closest* to the requested ``aep_pct`` (rather than simply the
    first one found) - e.g. for an AEP rarer than the table's rarest AEP for that
    band/duration (typically 1%), this picks that rarest (closest) AEP's pattern rather
    than an arbitrary same-band pattern. Returns ``None`` if none match."""
    from .temporal_patterns import aep_band
    target_band = aep_band(aep_name, output_notation)
    candidates = [
        row for row in rows
        if int(row['Duration']) == int(duration) and aep_band(f"{float(row['AEP'])}%", output_notation) == target_band
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda row: abs(float(row['AEP']) - aep_pct))


def _closest_duration_and_band_row(rows: list, duration: float, aep_name: str,
                                    output_notation: str) -> Optional[dict]:
    """Further fallback for :func:`recommended_preburst`, when no row exists at all for
    the requested *duration* (same event rarity band or otherwise) - e.g. very short
    durations below the Data Hub's minimum ``RecPreburstTP`` duration of 30 min. Returns
    the row with the same event rarity (AEP band) as the requested event whose duration
    is *closest* to the requested duration (ties broken by whichever appears first),
    or ``None`` if no row at all shares that event rarity band."""
    from .temporal_patterns import aep_band
    target_band = aep_band(aep_name, output_notation)
    candidates = [row for row in rows if aep_band(f"{float(row['AEP'])}%", output_notation) == target_band]
    if not candidates:
        return None
    return min(candidates, key=lambda row: abs(float(row['Duration']) - duration))


def recommended_preburst(response: ArrApiResponse, duration: float, aep_name: str, aep_pct: float,
                          output_notation: str = 'ari', point_depth: Optional[float] = None,
                          percentile: str = '50%') -> Optional[PreburstPattern]:
    """Looks up the Data Hub's recommended preburst temporal pattern (``RecPreburstTP``
    layer) for the given duration/AEP, to use as the preburst *shape* (increments/
    timestep). If no exact (Duration, AEP) match is available, falls back, in order:

    1. The preburst pattern for the *same* (exact) AEP as requested, whose *duration*
       is closest to the requested duration (ties - two candidate durations equally
       close - broken by choosing the lower duration) - see
       :func:`_closest_duration_same_aep_row`. This is the primary fallback, e.g. for a
       duration that falls between two durations the Data Hub does have data for at
       this AEP (such as 270 min, between the Data Hub's 180 and 360 min rows).
    2. If no row at all shares the requested AEP (e.g. an AEP band the Data Hub has no
       ``RecPreburstTP`` data for whatsoever), the preburst pattern with the same
       duration and the same event rarity (AEP band) as the requested event, whose
       *AEP* is closest to the requested one (see :func:`_same_duration_and_band_row`).
    3. If no row at all shares the requested duration either, the preburst pattern (of
       the same event rarity band) whose *duration* is closest to the requested
       duration (see :func:`_closest_duration_and_band_row`) - e.g. for durations
       shorter than the Data Hub's minimum ``RecPreburstTP`` duration of 30 min.

    A warning is logged whenever any of these fallbacks is used. Returns ``None`` if no
    match is found at all (e.g. the Data Hub has no ``RecPreburstTP`` data for this
    event rarity band whatsoever).

    The preburst *depth* (magnitude) is not taken from ``RecPreburstTP`` at all - its
    own ``"Preburst Depth"``/``"Preburst Ratio"`` fields are not used, since the Data
    Hub's ``"Preburst Depth"`` field is not actually a preburst depth. Instead, as with
    the ``"constant"``/``"temporal_pattern"`` methods, the depth is derived from the
    ``percentile`` ratio table (log-linear interpolated - see :func:`_preburst_ratio`)
    multiplied by ``point_depth`` (the point design burst depth), which is therefore
    required.
    """
    layer = response.layer('RecPreburstTP')
    if not layer or 'selected_patterns' not in layer:
        return None
    rows = layer['selected_patterns']
    row = _nearest_row(rows, duration, aep_pct)
    if row is None:
        row = _closest_duration_same_aep_row(rows, duration, aep_pct)
        if row is not None:
            logger.warning(
                "No recommended preburst temporal pattern available for %s/%smin - falling back to the "
                "preburst pattern for %s%% AEP/%smin (closest available duration, same AEP).",
                aep_name, duration, row['AEP'], row['Duration'],
            )
    if row is None:
        row = _same_duration_and_band_row(rows, duration, aep_name, aep_pct, output_notation)
        if row is not None:
            logger.warning(
                "No recommended preburst temporal pattern available for %s/%smin - falling back to the "
                "preburst pattern for %s%% AEP/%smin (same duration, same event rarity).",
                aep_name, duration, row['AEP'], row['Duration'],
            )
    if row is None:
        closest = _closest_duration_and_band_row(rows, duration, aep_name, output_notation)
        if closest is not None:
            logger.warning(
                "No recommended preburst temporal pattern available for %s/%smin at all - falling back to the "
                "preburst pattern for %s%% AEP/%smin (closest available duration, same event rarity).",
                aep_name, duration, closest['AEP'], closest['Duration'],
            )
            row = closest
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




def _preburst_ratio_frame(response: ArrApiResponse, percentile: str) -> pd.DataFrame:
    """Returns the raw duration x AEP preburst ratio table (``Preburst<percentile>``,
    or ``RecPreburst`` if ``percentile == 'recommended'`` and available - see
    :func:`_preburst_ratio`) as a :class:`pandas.DataFrame`, without interpolating -
    used to check whether a given duration/AEP falls inside or outside the table's own
    range (see :meth:`pytuflow.arr.engine.ArrEngine._initial_loss`)."""
    from .engine import _table_to_frame  # local import - avoids a cycle
    key = 'RecPreburst' if percentile == 'recommended' else f'Preburst{percentile.strip("%")}'
    table = response.layer(key)
    if table is None and key == 'RecPreburst':
        table = response.layer('Preburst50', required=True)
    elif table is None:
        raise ArrError(f"ARR Data Hub response is missing the '{key}' preburst ratio layer.")
    return _table_to_frame(table)


def _preburst_ratio(response: ArrApiResponse, percentile: str, duration: float, aep_pct: float) -> float:
    """Interpolates the preburst ratio (fraction of point burst depth) from the
    ``Preburst<percentile>`` layer (or, if ``percentile == 'recommended'``, the
    ``RecPreburst`` layer - the Data Hub's preferred/recommended preburst ratio, which
    is not necessarily the same as the exact 50th percentile) for the given
    duration/AEP, using log-linear interpolation (log10-transformed duration/AEP axes,
    but linear ratio values - see `_interp_table`'s `log_values` parameter).

    ``RecPreburst`` is an NSW-only layer - for other locations (where it's absent),
    ``percentile == 'recommended'`` automatically falls back to the ``Preburst50``
    (50th percentile) layer instead (a warning is logged), rather than raising."""
    from .engine import _interp_table, _table_to_frame  # local import - avoids a cycle
    key = 'RecPreburst' if percentile == 'recommended' else f'Preburst{percentile.strip("%")}'
    table = response.layer(key)
    if table is None and key == 'RecPreburst':
        logger.warning(
            "preburst.percentile == 'recommended' was requested, but the ARR Data Hub response does not "
            "contain a 'RecPreburst' layer for this location (it's NSW-only) - falling back to the 50%% "
            "percentile ('Preburst50' layer) instead."
        )
        table = response.layer('Preburst50', required=True)
    elif table is None:
        raise ArrError(f"ARR Data Hub response is missing the '{key}' preburst ratio layer.")
    df = _table_to_frame(table)
    # Log-linear (not log-log): duration and AEP axes are log-interpolated, but the
    # ratio values themselves are interpolated linearly, since a preburst ratio can be
    # exactly 0.0 (which can't be log-transformed). See `_interp_table`.
    return float(_interp_table(df, [duration], [aep_pct], log_values=False).iloc[0, 0])


def _figure_out_pb_duration(target_duration: float, pattern_duration: float, duration_proportional: bool,
                             pattern_duration_max: Optional[float] = None) -> float:
    """Computes the target preburst duration (minutes), given either an absolute
    duration (hours) or a proportion of the storm duration.

    ``pattern_duration_max`` (hours) caps the result when ``duration_proportional`` is
    ``True`` - without this, a proportional ``pattern_duration`` would produce an
    unrealistically long preburst period for long storm durations (e.g. a 72 hour storm
    with the default ``pattern_duration=2`` would otherwise get a 144 hour preburst).
    Has no effect when ``duration_proportional`` is ``False`` (an absolute
    ``pattern_duration`` is always used as given, uncapped)."""
    if duration_proportional:
        pb_duration = target_duration * float(pattern_duration)
        if pattern_duration_max is not None:
            pb_duration = min(pb_duration, float(pattern_duration_max) * 60.0)
        return pb_duration
    return float(pattern_duration) * 60.0


def constant_preburst(response: ArrApiResponse, config: ArrConfig, duration: float,
                       aep_name: str, aep_pct: float, point_depth: float) -> PreburstPattern:
    """Builds a single constant-rate preburst block, matching the legacy "Constant Rate"
    preburst pattern method."""
    cfg = config.preburst
    if cfg.pattern_duration is None:
        raise ArrError("preburst.pattern_duration is required for the 'constant' preburst pattern method.")
    pb_duration = _figure_out_pb_duration(
        duration, cfg.pattern_duration, cfg.duration_proportional, cfg.pattern_duration_max)
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
    target_dur = _figure_out_pb_duration(
        duration, cfg.pattern_duration, cfg.duration_proportional, cfg.pattern_duration_max)
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
    with ``preburst.pattern_tp == "design_burst"``.

    ``preburst.pattern_method == "none"`` should never reach this function - the caller
    (:meth:`pytuflow.arr.engine.ArrEngine.run`) is expected to special-case it before
    calling :func:`build_preburst` (setting the burst initial loss to 0 with a warning,
    rather than building any preburst pattern at all)."""
    method = (config.preburst.pattern_method or 'recommended').lower()
    if method == 'none':
        raise ArrError(
            "build_preburst() should not be called when preburst.pattern_method == 'none' - the caller must "
            "handle this case (setting the burst initial loss to 0) before calling build_preburst()."
        )
    if method == 'recommended':
        pattern = recommended_preburst(
            response, duration, aep_name, aep_pct, config.events.output_notation,
            point_depth=point_depth, percentile=config.preburst.percentile,
        )
        if pattern is None:
            # the Data Hub's 'RecPreburstTP' layer (NSW-only) has no data at all for
            # this event rarity band (e.g. any non-NSW location) - fall back to
            # shaping the preburst using the configured (or defaulted)
            # `pattern_duration`/`pattern_tp`/`duration_proportional`, the same as the
            # 'temporal_pattern' pattern method. This fallback needs `tp_set` (to look
            # up the point temporal pattern shape) - if it isn't available, there's
            # nothing further to fall back to.
            if tp_set is not None:
                try:
                    pattern = temporal_pattern_preburst(
                        response, config, tp_set, duration, aep_name, aep_pct, point_depth,
                        design_patterns=design_patterns)
                except ArrError:
                    pattern = None
                else:
                    logger.warning(
                        "No recommended preburst temporal pattern available for %s/%smin at all ('RecPreburstTP' "
                        "layer has no data for this location/event rarity) - falling back to "
                        "preburst.pattern_duration=%s (duration_proportional=%s) / pattern_tp=%s as the preburst "
                        "shape.",
                        aep_name, duration, config.preburst.pattern_duration,
                        config.preburst.duration_proportional, config.preburst.pattern_tp,
                    )
        if pattern is None:
            raise ArrError(
                f"No recommended preburst temporal pattern available for {aep_name}/{duration}min "
                f"('RecPreburstTP' layer), and the pattern_duration/pattern_tp fallback also failed - try a "
                f"different preburst.pattern_method."
            )
        return pattern
    if method == 'constant':
        return constant_preburst(response, config, duration, aep_name, aep_pct, point_depth)
    if method == 'temporal_pattern':
        return temporal_pattern_preburst(
            response, config, tp_set, duration, aep_name, aep_pct, point_depth, design_patterns=design_patterns)
    raise ArrError(f"Unrecognised preburst.pattern_method: '{config.preburst.pattern_method}'.")
