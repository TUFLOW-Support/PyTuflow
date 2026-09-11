"""Core event-assembly engine for :mod:`pytuflow.arr`.

For each requested AEP x duration combination, this module:

1. Selects the design (or climate-change-adjusted) rainfall depth from the Data Hub's
   IFD table and interpolates it onto the requested durations/AEPs.
2. Applies the Areal Reduction Factor (see :mod:`pytuflow.arr.arf`) to get an areal
   design burst depth.
3. Selects the burst initial loss from the Data Hub's burst loss table
   (``losses.method == "recommended"`` uses ``BurstLossesNew``; ``"probability_neutral"``
   uses the legacy NSW-only ``BurstIL`` table, raising an error if unavailable), then, if
   ``losses.extrapolation_method`` is not ``"none"``, extrapolates any requested
   durations shorter than the Data Hub's shortest provided duration (see
   :mod:`pytuflow.arr.losses`) - the two settings are independent of each other.
4. Selects the appropriate set of temporal patterns (see
   :mod:`pytuflow.arr.temporal_patterns`) and multiplies each pattern's percentage
   increments by the areal design burst depth to produce a rainfall hyetograph.

If ``config.complete_storm`` is set, or if the Data Hub's burst initial loss table
returns its ``"Use PB TP"`` placeholder for a given AEP/duration cell (meaning that cell
*requires* complete storm assembly regardless of the config setting - see
:mod:`pytuflow.arr.complete_storm`), a preburst rainfall period is additionally built
and prepended ahead of the design burst, and the full storm initial loss (rather than
the reduced burst initial loss) is used - see :meth:`ArrEngine._storm_initial_loss` and
:mod:`pytuflow.arr.complete_storm`. If the resulting preburst depth turns out to be
negligible (implied preburst ratio < 0.01 of the point design burst depth), the
preburst period is dropped and the event falls back to a standard burst-only event.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .api_client import ArrApiResponse
from .arf import aep_name_to_pct, arf_factors
from .config import ArrConfig
from .exceptions import ArrError
from .losses import extrapolate_short_duration_losses, interpolate_missing_durations
from .temporal_patterns import TemporalPattern, TemporalPatternSet

logger = logging.getLogger('pytuflow.arr')


class _NeedsCompleteStorm(Exception):
    """Internal signal raised by :meth:`ArrEngine._initial_loss` when a burst initial
    loss cell is the Data Hub's ``"Use PB TP"`` placeholder, meaning that cell can only
    be assembled via complete storm (preburst-extended) logic. Caught in
    :meth:`ArrEngine.run`; never escapes the module."""



def _table_to_frame(table: dict) -> pd.DataFrame:
    """Converts a Data Hub ``{"index": ..., "columns": ..., "data": ...}`` table into a
    :class:`pandas.DataFrame` with numeric index/columns."""
    df = pd.DataFrame(table['data'], index=table['index'], columns=table['columns'])
    df.index = df.index.astype(float)
    df.columns = df.columns.astype(float)
    return df.sort_index().sort_index(axis=1)


def _interp_table(df: pd.DataFrame, durations: list, aep_pcts: list) -> pd.DataFrame:
    """Log-linearly interpolates (in duration) and linearly interpolates (in AEP, on a
    log scale) a duration x AEP table onto the requested durations/AEPs. Uses numpy's
    ``interp`` against log10(duration) and log10(aep) axes, matching the legacy script's
    log-log interpolation of IFD depths.

    Values outside the range of the table are clamped to the nearest edge value (no
    extrapolation) - callers needing extrapolation (e.g. short-duration losses) must
    handle that explicitly beforehand.
    """
    log_dur = np.log10(df.index.values.astype(float))
    log_aep = np.log10(df.columns.values.astype(float))
    target_log_dur = np.log10(np.array(durations, dtype=float))
    target_log_aep = np.log10(np.array(aep_pcts, dtype=float))

    # interpolate across AEP for every known duration row first
    aep_interp = np.empty((df.shape[0], len(aep_pcts)))
    for i in range(df.shape[0]):
        row = df.iloc[i].values.astype(float)
        aep_interp[i, :] = np.interp(target_log_aep, log_aep, row)

    # then interpolate across duration for every requested aep column
    out = np.empty((len(durations), len(aep_pcts)))
    for j in range(len(aep_pcts)):
        out[:, j] = np.interp(target_log_dur, log_dur, aep_interp[:, j])

    return pd.DataFrame(out, index=durations, columns=[str(a) for a in aep_pcts])


@dataclass
class EventResult:
    """The assembled result for a single AEP x duration combination."""
    aep_name: str
    duration: float
    depth_point: float  # point design rainfall depth (mm), before ARF
    arf: float
    depth_areal: float  # areal design rainfall depth (mm), after ARF
    initial_loss: float  # mm
    continuing_loss: float  # mm/h
    aep_band: str  # 'frequent' | 'intermediate' | 'rare'
    patterns: list  # list[TemporalPattern]
    cc_scenario: Optional[str] = None  # e.g. '2090_SSP3', None for the base (no-CC) event
    preburst: Optional['PreburstPattern'] = None  # set only for complete storm events


@dataclass
class ArrEngine:
    """Assembles ARR design events (standard or complete storm) for a single site
    config, using an already-fetched :class:`~pytuflow.arr.api_client.ArrApiResponse`.
    """

    config: ArrConfig
    response: ArrApiResponse
    _tp_set: Optional[TemporalPatternSet] = field(default=None, init=False, repr=False)

    #: Working data captured during :meth:`run`, for optional verbose output (see
    #: :mod:`pytuflow.arr.working_data`). Populated by ``run()``; empty beforehand.
    #: ``arf_tables``/``depth_areal_tables`` are keyed by climate change scenario label
    #: (``None`` for the base, no-CC scenario).
    arf_tables: dict = field(default_factory=dict, init=False, repr=False)
    depth_areal_tables: dict = field(default_factory=dict, init=False, repr=False)
    burst_loss_table: dict = field(default_factory=dict, init=False, repr=False)
    #: Extrapolated burst initial loss values (mm), for QA (see
    #: :mod:`pytuflow.arr.working_data`), in the same duration (index) x AEP% (columns)
    #: table shape as ``burst_loss_table``, keyed by climate change scenario label
    #: (``None`` for the base, no-CC scenario). Only contains rows for durations that
    #: were actually extrapolated (i.e. ``losses.extrapolation_method != 'none'`` and the
    #: requested duration was shorter than the Data Hub's shortest provided duration);
    #: empty (no rows) if nothing was extrapolated.
    extrapolated_loss_table: dict = field(default_factory=dict, init=False, repr=False)
    #: Internal accumulator of extrapolated-loss records (populated in
    #: :meth:`_initial_loss`, consumed at the end of :meth:`run` to build
    #: ``extrapolated_loss_table``).
    _extrapolated_loss_records: list = field(default_factory=list, init=False, repr=False)
    #: Raw ARR Data Hub JSON responses and increments CSV text for each
    #: ``temporal_patterns.additional_tp`` region fetched, keyed by (title-cased)
    #: region name - populated by :meth:`_tp_set_for_config`, for optional working-data
    #: output (see :mod:`pytuflow.arr.working_data`). Each value is a dict with
    #: ``'raw'`` (the full JSON response) and ``'csv'`` (the downloaded point temporal
    #: pattern increments CSV text) keys.
    additional_tp_responses: dict = field(default_factory=dict, init=False, repr=False)

    # -- data preparation -------------------------------------------------------------

    def _durations(self) -> list:
        dur = self.config.events.duration
        return [float(d) for d in dur]

    def _aep_names(self) -> list:
        aep = self.config.events.aep
        aep_ = []
        for a in aep:
            try:
                float(a)
                aep_.append(f'{a}%')
            except (ValueError, TypeError):
                aep_.append(a)
        return aep_

    def _ifd_frame(self, baseline_year: int, ssp: Optional[str] = None) -> pd.DataFrame:
        if ssp is not None:
            table = self.response.cc_adj_ifd_table(baseline_year, ssp)
        elif self.config.ifd.source == 'limb':
            table = self.response.limb_ifd_table(baseline_year)
        else:
            table = self.response.ifd_table(baseline_year)
        return _table_to_frame(table)

    def _point_depths_for_preburst_ratio(self, durations: list, threshold: Optional[float],
                                          burst_loss_columns) -> pd.DataFrame:
        """Builds a duration x AEP table of point (unARF'd) design burst depths, needed
        by the ``'constant_preburst_ratio'`` loss extrapolation method - covers the
        reference (``threshold``) duration plus every requested ``durations`` value,
        for the same AEP columns as the burst initial loss table (aligned to those
        exact column values/dtype so they can be indexed together)."""
        baseline_ifd = self._ifd_frame(self.config.ifd.year, None)
        needed_durations = sorted({float(d) for d in durations} | ({threshold} if threshold is not None else set()))
        aep_pcts = [float(c) for c in burst_loss_columns]
        point_depths = _interp_table(baseline_ifd, needed_durations, aep_pcts)
        point_depths.columns = burst_loss_columns
        return point_depths

    def _burst_loss_frame(self) -> pd.DataFrame:
        """Returns the burst initial loss table (duration x AEP%), according to
        ``losses.method``:

        * ``"recommended"`` - the Data Hub's newer burst initial loss table
          (``BurstLossesNew``).
        * ``"probability_neutral"`` - the legacy (NSW-only) probability-neutral burst
          initial loss table (``BurstIL``). Raises :class:`ArrError` if the Data Hub
          hasn't provided this layer for the queried location (i.e. it's not in NSW).
        """
        method = self.config.losses.method
        if method == 'probability_neutral':
            table = self.response.layer('BurstIL')
            if table is None:
                raise ArrError(
                    "losses.method == 'probability_neutral' was requested, but the ARR Data Hub response "
                    "does not contain a 'BurstIL' layer for this location (probability-neutral burst "
                    "initial losses are only available in NSW)."
                )
        else:
            table = self.response.layer('BurstLossesNew')
            if table is None:
                raise ArrError("ARR Data Hub response is missing burst initial loss data ('BurstLossesNew' layer).")
        return _table_to_frame(table)

    def _storm_continuing_loss(self, aep_name: str) -> float:
        """Looks up the storm continuing loss (mm/h) for the given AEP from the
        ``NewStormLosses`` layer (not duration-dependent), unless
        ``losses.user_continuing_loss`` is set, in which case that fixed value is used
        instead (regardless of AEP), matching the legacy script's
        ``applyUserContinuingLoss``."""
        if self.config.losses.user_continuing_loss is not None:
            return float(self.config.losses.user_continuing_loss)
        new_losses = self.response.layer('NewStormLosses')
        if new_losses and 'losses' in new_losses:
            aep_pct = aep_name_to_pct(aep_name)
            for row in new_losses['losses']:
                if abs(_aep_str_to_pct(row['AEP']) - aep_pct) < 1e-6:
                    return float(row['Continuing Loss (mm/h)'])
        # fall back to the legacy single 'StormLosses' summary value (not AEP-dependent)
        storm_losses = self.response.layer('StormLosses')
        if storm_losses and 'Storm Continuing Losses (mm/h)' in storm_losses:
            return float(storm_losses['Storm Continuing Losses (mm/h)'])
        raise ArrError("ARR Data Hub response is missing continuing loss data "
                        "('NewStormLosses'/'StormLosses' layers).")

    def _tp_set_for_config(self) -> TemporalPatternSet:
        if self._tp_set is None:
            tp_cfg = self.config.temporal_patterns
            if tp_cfg.point_tp_csv:
                tp_set = TemporalPatternSet.from_files(
                    tp_cfg.point_tp_csv, tp_cfg.areal_tp_csv, catchment_area=self.config.site.catchment_area)
            else:
                point_tp = self.response.layer('PointTP', required=True)
                areal_tp = self.response.layer('ArealTP')
                point_url = point_tp['url']
                areal_url = areal_tp['url'] if areal_tp else None
                tp_set = TemporalPatternSet.from_api_response(
                    point_url, areal_url, catchment_area=self.config.site.catchment_area)
            from .temporal_patterns import (
                TP_REGION_COORDS, fetch_additional_region_point_tp, load_additional_region_point_tp_csv,
            )
            for entry in tp_cfg.additional_tp:
                if str(entry).strip().lower() in TP_REGION_COORDS:
                    result = fetch_additional_region_point_tp(entry)
                else:
                    result = load_additional_region_point_tp_csv(entry)
                tp_set.add_region_patterns(result.dataframe)
                self.additional_tp_responses[result.region] = {'raw': result.raw_response, 'csv': result.csv_text}
            self._tp_set = tp_set
        return self._tp_set

    def _cc_loss_factors(self, baseline_year: int, ssp: str) -> tuple:
        """Returns ``(initial_loss_factor, continuing_loss_factor)`` for the given
        climate change scenario, from the Data Hub's ``ClimateChange`` layer."""
        return self.response.climate_change_loss_factors(baseline_year, ssp)

    def _storm_initial_loss(self, aep_name: str) -> float:
        """Looks up the (non-reduced) storm initial loss (mm) for the given AEP - used
        for complete storm events, where the full storm initial loss applies (rather
        than a burst initial loss already reduced for preburst rainfall)."""
        return self._storm_initial_loss_pct(aep_name_to_pct(aep_name))

    def _storm_initial_loss_pct(self, aep_pct: float) -> float:
        """As :meth:`_storm_initial_loss`, but keyed directly by AEP percentage rather
        than an AEP name string. Returns ``losses.user_initial_loss`` directly (for any
        AEP) if set, matching the legacy script's ``applyUserInitialLoss`` (which
        replaces the storm initial loss used for complete storm events, and is also
        used to proportionally scale the burst initial loss table - see
        :meth:`_initial_loss`)."""
        if self.config.losses.user_initial_loss is not None:
            return float(self.config.losses.user_initial_loss)
        return self._storm_initial_loss_pct_datahub(aep_pct)

    def _storm_initial_loss_pct_datahub(self, aep_pct: float) -> float:
        """The Data Hub's own storm initial loss (mm) for the given AEP percentage,
        ignoring ``losses.user_initial_loss`` - used as the reference value when
        proportionally scaling the burst initial loss table for a user-supplied storm
        initial loss (see :meth:`_initial_loss`)."""
        new_losses = self.response.layer('NewStormLosses')
        if new_losses and 'losses' in new_losses:
            for row in new_losses['losses']:
                if abs(_aep_str_to_pct(row['AEP']) - aep_pct) < 1e-6:
                    return float(row['Storm Initial Loss (mm)'])
        storm_losses = self.response.layer('StormLosses')
        if storm_losses and 'Storm Initial Losses (mm)' in storm_losses:
            return float(storm_losses['Storm Initial Losses (mm)'])
        raise ArrError("ARR Data Hub response is missing storm initial loss data "
                        "('NewStormLosses'/'StormLosses' layers).")

    def _scale_burst_losses_to_user_il(self, burst_losses: pd.DataFrame) -> pd.DataFrame:
        """Proportionally scales every numeric cell of a duration x AEP% burst initial
        loss table so that the (per-AEP) storm initial loss matches
        ``losses.user_initial_loss``, preserving the Data Hub's relative
        duration/AEP reduction shape - i.e. ``scaled = burst_il * (user_il /
        storm_il_datahub(aep))`` - matching the legacy script's ``applyUserInitialLoss``
        scaling. Non-numeric placeholder cells (e.g. ``"Use PB TP"``) are left
        untouched. Logs a warning and leaves a column unscaled if the Data Hub's storm
        initial loss for that AEP is zero (cannot derive a scale factor)."""
        user_il = float(self.config.losses.user_initial_loss)
        scaled = burst_losses.copy()
        for col in scaled.columns:
            aep_pct = float(col)
            storm_il = self._storm_initial_loss_pct_datahub(aep_pct)
            if storm_il == 0:
                logger.warning(
                    "Cannot scale burst initial losses to the user-supplied storm initial loss for AEP %s%% - "
                    "the Data Hub's storm initial loss is zero.", aep_pct,
                )
                continue
            ratio = user_il / storm_il
            scaled[col] = scaled[col].map(lambda v: v * ratio if isinstance(v, (int, float)) else v)
        return scaled

    def _cc_burst_loss_table(self, base_burst_loss: pd.DataFrame, baseline_year: int, ssp: str) -> pd.DataFrame:
        """Builds a climate-change-adjusted burst initial loss table (same duration x
        AEP% shape as ``base_burst_loss``), dispatching on ``losses.climate_change_method``:

        * ``"burst"`` (default, legacy-equivalent) - scales each numeric burst initial
          loss cell directly by the Data Hub's climate-change initial loss adjustment
          factor.
        * ``"storm"`` - scales the (baseline) full storm initial loss by the same
          factor, then subtracts a climate-change preburst depth (the climate-change-
          adjusted point rainfall depth at that duration/AEP, multiplied by the
          ``preburst.percentile`` preburst ratio) to derive the climate-change burst
          initial loss.

        Non-numeric placeholder cells (e.g. ``"Use PB TP"``) are left untouched either
        way.
        """
        il_factor, _ = self._cc_loss_factors(baseline_year, ssp)
        if self.config.losses.climate_change_method == 'burst':
            return base_burst_loss.map(lambda v: v * il_factor if isinstance(v, (int, float)) else v)

        from .complete_storm import _preburst_ratio
        durations = [float(d) for d in base_burst_loss.index]
        aep_pcts = [float(c) for c in base_burst_loss.columns]
        cc_ifd = self._ifd_frame(baseline_year, ssp)
        cc_depths = _interp_table(cc_ifd, durations, aep_pcts)
        table = base_burst_loss.copy()
        for row_dur in durations:
            for col, aep_pct in zip(base_burst_loss.columns, aep_pcts):
                v = base_burst_loss.loc[row_dur, col]
                if not isinstance(v, (int, float)) or pd.isna(v):
                    continue
                storm_il_cc = self._storm_initial_loss_pct(aep_pct) * il_factor
                preburst_ratio = _preburst_ratio(self.response, self.config.preburst.percentile, row_dur, aep_pct)
                cc_point_depth = float(cc_depths.loc[row_dur, str(aep_pct)])
                cc_preburst = cc_point_depth * preburst_ratio
                table.loc[row_dur, col] = storm_il_cc - cc_preburst
        return table

    def _fill_placeholder_adjacent_gaps(self, burst_losses: pd.DataFrame, durations: list) -> pd.DataFrame:
        """Gap-fills any requested duration that falls between a ``"Use PB TP"``
        placeholder cell and a numeric burst initial loss cell (for the same AEP
        column) - rather than the plain linear interpolation used for gaps bracketed by
        two numeric cells (see :func:`pytuflow.arr.losses.interpolate_missing_durations`,
        called separately after this method), since interpolating a loss *value*
        towards/from an undefined placeholder doesn't make sense.

        Instead, for such a duration/AEP cell, the (interpolated) preburst depth -
        ``preburst.percentile`` ratio multiplied by the point design burst depth at that
        duration - is subtracted from the (duration-independent) storm initial loss to
        derive an implied burst initial loss:

        * If that implied burst initial loss is positive, it is used as the cell's
          value directly.
        * If it would be negative (i.e. the preburst rainfall alone exceeds the storm
          initial loss), the cell is set to the ``"Use PB TP"`` placeholder too, forcing
          complete storm assembly for that specific AEP/duration (matching the
          Data Hub's own convention for cells where a single fixed burst initial loss
          value isn't meaningful).

        A duration/AEP gap bracketed by two placeholder cells is also set to the
        placeholder (no numeric neighbour exists to derive anything from either way).
        Gaps bracketed by two numeric cells are left untouched (handled separately).
        """
        if burst_losses.empty:
            return burst_losses
        lower_bound = float(burst_losses.index.min())
        upper_bound = float(burst_losses.index.max())
        missing = sorted({
            float(d) for d in durations
            if lower_bound < float(d) < upper_bound and float(d) not in burst_losses.index
        })
        if not missing:
            return burst_losses

        known_durations = sorted(burst_losses.index)
        result = burst_losses.copy()
        baseline_ifd = None
        for dur in missing:
            lower_dur = max(d for d in known_durations if d < dur)
            upper_dur = min(d for d in known_durations if d > dur)
            for col in burst_losses.columns:
                lower_value = burst_losses.loc[lower_dur, col]
                upper_value = burst_losses.loc[upper_dur, col]
                lower_numeric = isinstance(lower_value, (int, float)) and not pd.isna(lower_value)
                upper_numeric = isinstance(upper_value, (int, float)) and not pd.isna(upper_value)
                if lower_numeric and upper_numeric:
                    continue  # both numeric - handled by interpolate_missing_durations
                if not lower_numeric and not upper_numeric:
                    # bracketed by two placeholders - no numeric neighbour to derive
                    # anything from, so the gap is a placeholder too.
                    result.loc[dur, col] = 'Use PB TP'
                    continue
                # exactly one side is numeric, the other a "Use PB TP" placeholder -
                # derive the implied burst initial loss from the preburst depth/storm
                # initial loss instead of interpolating towards/from an undefined value.
                aep_pct = float(col)
                if baseline_ifd is None:
                    baseline_ifd = self._ifd_frame(self.config.ifd.year, None)
                from .complete_storm import _preburst_ratio
                point_depth = float(_interp_table(baseline_ifd, [dur], [aep_pct]).iloc[0, 0])
                preburst_ratio = _preburst_ratio(self.response, self.config.preburst.percentile, dur, aep_pct)
                preburst_depth = preburst_ratio * point_depth
                # use the Data Hub's own (unscaled) storm initial loss here, not
                # `losses.user_initial_loss`, so this cell stays in "Data Hub space"
                # and is scaled consistently with the rest of the table afterwards
                # (see `_scale_burst_losses_to_user_il`, called by `_initial_loss`).
                storm_il = self._storm_initial_loss_pct_datahub(aep_pct)
                implied_burst_loss = storm_il - preburst_depth
                if implied_burst_loss < 0:
                    logger.info(
                        "Duration %s min, AEP %s%%: implied burst initial loss (storm initial loss %.3f mm - "
                        "preburst depth %.3f mm = %.3f mm) is negative - treating this cell as 'Use PB TP' "
                        "(complete storm assembly required).", dur, aep_pct, storm_il, preburst_depth,
                        implied_burst_loss,
                    )
                    result.loc[dur, col] = 'Use PB TP'
                else:
                    result.loc[dur, col] = implied_burst_loss
        return result

    def _initial_loss(self, duration: float, aep_name: str, durations: list,
                       scenario_label: Optional[str] = None) -> float:
        aep_pct = aep_name_to_pct(aep_name)
        burst_losses = self._burst_loss_frame()
        # gap-fill any requested duration bracketed by a "Use PB TP" placeholder and a
        # numeric cell (or two placeholders) first - see _fill_placeholder_adjacent_gaps
        # - then fall back to plain linear interpolation for any remaining gaps
        # bracketed by two numeric cells (e.g. 270 min, between rows at 180 and 360 min)
        # - matches the legacy script's `interpolate_nan`, independent of
        # `losses.extrapolation_method` (which only controls extrapolation *below* the
        # table's shortest duration).
        burst_losses = self._fill_placeholder_adjacent_gaps(burst_losses, durations)
        burst_losses = interpolate_missing_durations(burst_losses, durations)
        losses_cfg = self.config.losses
        threshold = float(burst_losses.index.min()) if not burst_losses.empty else None
        if losses_cfg.extrapolation_method != 'none':
            # always extrapolate using the Data Hub's own (unscaled) storm initial
            # loss here, not `losses.user_initial_loss` - the whole table (including
            # any extrapolated short-duration rows) is scaled to the user-supplied
            # value in one consistent step below, once everything is in "Data Hub
            # space" (avoids double-scaling the extrapolated rows).
            ils = None
            if losses_cfg.extrapolation_method in ('rahman', 'hill', 'interpolate_preburst',
                                                     'log_interpolate_preburst', 'constant_preburst_ratio'):
                ils = self._storm_initial_loss_pct_datahub(aep_pct)
            point_depths = None
            if losses_cfg.extrapolation_method == 'constant_preburst_ratio':
                # point (unARF'd) design burst depths at the reference (threshold) and
                # every requested short duration, matching the point depth convention
                # used elsewhere for preburst ratios (see `complete_storm._preburst_ratio`).
                point_depths = self._point_depths_for_preburst_ratio(durations, threshold, burst_losses.columns)
            extended = extrapolate_short_duration_losses(
                burst_losses, durations, method=losses_cfg.extrapolation_method,
                ils=ils, mar=losses_cfg.mar,
                static_loss_value=losses_cfg.static_loss,
                point_depths=point_depths,
            )
            burst_losses = extended
        if losses_cfg.user_initial_loss is not None:
            # scale the whole burst initial loss table proportionally so the design
            # storm initial loss matches the user-supplied value, preserving the Data
            # Hub's relative duration/AEP reduction shape - matches the legacy script's
            # `applyUserInitialLoss` scaling (`ilb_complete * (ils_user / ils)`).
            burst_losses = self._scale_burst_losses_to_user_il(burst_losses)
        # nearest available AEP column (exact match expected in practice)
        col = min(burst_losses.columns, key=lambda c: abs(float(c) - aep_pct))
        if duration not in burst_losses.index:
            raise ArrError(
                f"No burst initial loss available for duration {duration} min - "
                f"set losses.extrapolation_method to extrapolate below {burst_losses.index.min()} min."
            )
        value = burst_losses.loc[duration, col]
        try:
            value = float(value)
        except (TypeError, ValueError):
            # The Data Hub uses this placeholder to indicate that, for this AEP/duration,
            # the burst initial loss must be derived using the preburst temporal pattern
            # method rather than a single fixed value - i.e. this event requires complete
            # storm assembly. Signal this up to `run()`, which automatically switches to
            # complete storm assembly for just this cell (per user direction), rather than
            # requiring the user to opt in.
            raise _NeedsCompleteStorm(
                f"Burst initial loss for {aep_name}/{duration}min is a preburst-pattern "
                f"placeholder ('{value}')."
            )

        if threshold is not None and duration < threshold:
            self._extrapolated_loss_records.append({
                'cc_scenario': scenario_label,
                'duration': duration,
                'aep_pct': aep_pct,
                'initial_loss': value,
            })
        return value

    # -- assembly ------------------------------------------------------------------

    def run(self) -> list:
        """Assembles every requested AEP x duration event (and climate change scenario,
        if enabled) and returns a list of :class:`EventResult`."""
        durations = self._durations()
        aep_names = self._aep_names()
        aep_pcts = [aep_name_to_pct(a) for a in aep_names]
        arf_params = self.response.layer('ARFParams', required=True)
        tp_set = self._tp_set_for_config()

        results = []
        scenarios: list = [(None, self.config.ifd.year, None)]
        if self.config.climate_change.enabled:
            for s in self.config.climate_change.scenarios:
                scenarios.append((f'{s.baseline_year}_{s.ssp}', s.baseline_year, s.ssp))

        self.arf_tables = {}
        self.depth_areal_tables = {}
        self.burst_loss_table = {}
        self.extrapolated_loss_table = {}
        self._extrapolated_loss_records = []
        try:
            base_burst_loss = self._burst_loss_frame()
            if self.config.losses.user_initial_loss is not None:
                base_burst_loss = self._scale_burst_losses_to_user_il(base_burst_loss)
        except ArrError:
            base_burst_loss = None
        self.burst_loss_table[None] = base_burst_loss

        for scenario_label, baseline_year, ssp in scenarios:
            if scenario_label is not None and base_burst_loss is not None:
                # burst_loss table may contain non-numeric "Use PB TP" placeholder cells
                # (complete-storm-only cells) - only scale the numeric cells.
                self.burst_loss_table[scenario_label] = self._cc_burst_loss_table(
                    base_burst_loss, baseline_year, ssp)
            ifd = self._ifd_frame(baseline_year, ssp)
            depths = _interp_table(ifd, durations, aep_pcts)
            arf = arf_factors(
                self.config.site.catchment_area, durations, aep_names, arf_params,
                arf_frequent=self.config.arf.ignore_limits_for_frequent,
                min_arf=self.config.arf.min_arf,
            )
            depth_areal_table = pd.DataFrame(
                {aep_name: depths[str(aep_pct)].values * arf[aep_name].values
                 for aep_name, aep_pct in zip(aep_names, aep_pcts)},
                index=durations,
            )
            self.arf_tables[scenario_label] = arf
            self.depth_areal_tables[scenario_label] = depth_areal_table

            for aep_name, aep_pct in zip(aep_names, aep_pcts):
                for duration in durations:
                    depth_point = float(depths.loc[duration, str(aep_pct)])
                    arf_value = float(arf.loc[duration, aep_name])
                    depth_areal = depth_point * arf_value
                    patterns = tp_set.patterns(
                        duration, aep_name, self.config.events.output_notation,
                        all_point_tp=self.config.temporal_patterns.all_point_tp,
                        add_areal_tp=self.config.temporal_patterns.add_areal_tp,
                    )
                    band = _band_of(patterns, aep_name, self.config.events.output_notation)
                    cl = self._storm_continuing_loss(aep_name)

                    preburst = None
                    needs_complete_storm = self.config.complete_storm
                    il = None
                    if not needs_complete_storm:
                        try:
                            il = self._initial_loss(duration, aep_name, durations, scenario_label=scenario_label)
                        except _NeedsCompleteStorm as e:
                            logger.info(
                                "%s/%smin requires complete storm assembly (%s) - automatically switching to "
                                "complete storm for this event.", aep_name, duration, e
                            )
                            needs_complete_storm = True

                    if needs_complete_storm:
                        from .complete_storm import build_preburst
                        preburst = build_preburst(
                            self.response, self.config, tp_set, duration, aep_name, aep_pct, depth_point,
                            design_patterns=patterns)
                        implied_ratio = (preburst.depth / depth_point) if depth_point else 0.0
                        if implied_ratio < 0.01:
                            # negligible preburst contribution - drop it and fall back
                            # to a standard burst-only event rather than needlessly
                            # complicating the model with an insignificant preburst
                            # period.
                            logger.info(
                                "%s/%smin: implied preburst ratio (%.4f) is below the 0.01 threshold - "
                                "dropping the preburst period and outputting a standard burst-only event.",
                                aep_name, duration, implied_ratio,
                            )
                            preburst = None
                            try:
                                il = self._initial_loss(duration, aep_name, durations, scenario_label=scenario_label)
                            except _NeedsCompleteStorm:
                                # no fixed burst initial loss available either (a 'Use PB
                                # TP' placeholder cell) - since the preburst contribution
                                # is negligible, the full storm initial loss is an
                                # adequate proxy for the burst initial loss here.
                                il = self._storm_initial_loss(aep_name)
                        else:
                            il = self._storm_initial_loss(aep_name)

                    if ssp is not None:
                        # apply the Data Hub's climate-change loss adjustment factors -
                        # continuing loss is always simply factored. Initial loss
                        # follows `losses.climate_change_method`: complete storm events
                        # (which already use the full, unreduced storm initial loss)
                        # and the "burst" method both just factor `il` directly; the
                        # "storm" method instead re-derives the burst initial loss from
                        # the climate-change-scaled storm initial loss minus a
                        # climate-change preburst depth.
                        il_factor, cl_factor = self._cc_loss_factors(baseline_year, ssp)
                        cl = cl * cl_factor
                        if needs_complete_storm or self.config.losses.climate_change_method == 'burst':
                            il = il * il_factor
                        else:
                            from .complete_storm import _preburst_ratio
                            storm_il_cc = self._storm_initial_loss_pct(aep_pct) * il_factor
                            preburst_ratio = _preburst_ratio(self.response, self.config.preburst.percentile,
                                                              duration, aep_pct)
                            cc_preburst = depth_point * preburst_ratio
                            il = storm_il_cc - cc_preburst

                    results.append(EventResult(
                        aep_name=aep_name, duration=duration, depth_point=depth_point,
                        arf=arf_value, depth_areal=depth_areal, initial_loss=il,
                        continuing_loss=cl, aep_band=band, patterns=patterns,
                        cc_scenario=scenario_label, preburst=preburst,
                    ))

        # build one duration (index) x AEP% (columns) table per CC scenario from the
        # accumulated extrapolated-loss records, matching the shape of burst_loss_table.
        for scenario_label, _, _ in scenarios:
            rows = [r for r in self._extrapolated_loss_records if r['cc_scenario'] == scenario_label]
            if not rows:
                self.extrapolated_loss_table[scenario_label] = pd.DataFrame()
                continue
            table = pd.DataFrame(rows).pivot_table(
                index='duration', columns='aep_pct', values='initial_loss', aggfunc='first')
            self.extrapolated_loss_table[scenario_label] = table.sort_index()
        return results


def _aep_str_to_pct(aep_str: str) -> float:
    aep_str = str(aep_str).strip()
    if aep_str.endswith('%'):
        return float(aep_str[:-1])
    return aep_name_to_pct(aep_str)


def _band_of(patterns: list, aep_name: str, output_notation: str) -> str:
    from .temporal_patterns import aep_band
    return aep_band(aep_name, output_notation)
