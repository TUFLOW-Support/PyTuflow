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
from typing import Optional, Union

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


#: Values <= 0 in a duration x AEP table (e.g. a preburst ratio table's genuinely zero
#: entries for very long durations) can't be log-transformed - they're floored to this
#: tiny positive constant before taking log10, so log-log interpolation stays well
#: defined; the interpolated result for a bracket next to such an entry ends up
#: extremely small (practically negligible) rather than exactly zero. Exact (Duration,
#: AEP) grid matches are restored to their literal table value afterwards regardless
#: (see below), so a requested duration/AEP that lands exactly on a zero table entry
#: still returns exactly ``0.0``, not this floor value.
_LOG_INTERP_FLOOR = 1e-6


def _interp_table(df: pd.DataFrame, durations: list, aep_pcts: list) -> pd.DataFrame:
    """Log-log interpolates a duration x AEP table onto the requested durations/AEPs -
    both the duration/AEP axes *and* the table's values are transformed to log10
    first, then linearly interpolated (i.e. ``np.interp`` against log10(duration)/
    log10(aep) axes and log10(value)), and the result is transformed back
    (``10 ** result``) - matching true log-log (power-law) interpolation, as used for
    ARR IFD depth tables. Used for both IFD/rainfall depth tables and preburst ratio
    tables (see :func:`pytuflow.arr.complete_storm._preburst_ratio`), so interpolating
    either the preburst ratio or the preburst depth directly (ratio x point depth) for
    the same duration/AEP gives the same result.

    An exact (Duration, AEP) match in the table (including a value of exactly ``0.0``,
    which can't be log-transformed - see :data:`_LOG_INTERP_FLOOR`) is always returned
    as its literal table value, bypassing interpolation (and the log/``10**`` round
    trip) entirely.

    Values outside the range of the table are clamped to the nearest edge value (no
    extrapolation) - callers needing extrapolation (e.g. short-duration losses) must
    handle that explicitly beforehand.
    """
    log_dur = np.log10(df.index.values.astype(float))
    log_aep = np.log10(df.columns.values.astype(float))
    target_log_dur = np.log10(np.array(durations, dtype=float))
    target_log_aep = np.log10(np.array(aep_pcts, dtype=float))

    values = df.values.astype(float)
    log_values = np.log10(np.where(values > 0, values, _LOG_INTERP_FLOOR))

    # interpolate across AEP for every known duration row first
    aep_interp = np.empty((df.shape[0], len(aep_pcts)))
    for i in range(df.shape[0]):
        row = log_values[i, :]
        aep_interp[i, :] = np.interp(target_log_aep, log_aep, row)

    # then interpolate across duration for every requested aep column
    out_log = np.empty((len(durations), len(aep_pcts)))
    for j in range(len(aep_pcts)):
        out_log[:, j] = np.interp(target_log_dur, log_dur, aep_interp[:, j])

    out = 10 ** out_log

    # restore exact (Duration, AEP) grid matches to their literal table value, bypassing
    # the log/10** round trip (this also correctly restores a literal 0.0 table value,
    # which was floored to _LOG_INTERP_FLOOR above purely for the log transform).
    dur_index = df.index.values.astype(float)
    aep_columns = df.columns.values.astype(float)
    for oi, dur in enumerate(durations):
        dur_matches = np.nonzero(np.isclose(dur_index, float(dur)))[0]
        if not len(dur_matches):
            continue
        for oj, aep in enumerate(aep_pcts):
            aep_matches = np.nonzero(np.isclose(aep_columns, float(aep)))[0]
            if not len(aep_matches):
                continue
            out[oi, oj] = values[dur_matches[0], aep_matches[0]]

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
        baseline_ifd = self._ifd_frame(self.config.ifd.baseline_year, None)
        needed_durations = sorted({float(d) for d in durations} | ({threshold} if threshold is not None else set()))
        aep_pcts = [float(c) for c in burst_loss_columns]
        point_depths = _interp_table(baseline_ifd, needed_durations, aep_pcts)
        point_depths.columns = burst_loss_columns
        return point_depths

    def _burst_loss_frame(self) -> pd.DataFrame:
        """Returns the burst initial loss table (duration x AEP%), according to
        ``losses.method``:

        * ``"recommended"`` - the Data Hub's newer burst initial loss table
          (``BurstLossesNew``) supplies the duration/AEP *grid* (which cells exist,
          and which of those are the ``"Use PB TP"`` placeholder in the Data Hub's own
          data), but every numeric cell's *value* - and therefore also whether it ends
          up negative and so gets converted to the ``"Use PB TP"`` placeholder instead,
          forcing complete storm assembly - is always recalculated directly from
          ``storm initial loss - preburst.percentile ratio * point design depth``
          (against the configured ``ifd.baseline_year``), rather than trusting the Data
          Hub's own raw value - see :meth:`_recompute_burst_losses_for_ifd_year`. This
          is necessary for consistency: the Data Hub's raw ``BurstLossesNew`` values
          (and its own ``"Use PB TP"`` designation) are only ever computed against its
          own recommended preburst percentile and the 2030 baseline - if
          ``preburst.percentile`` or ``ifd.baseline_year`` is set differently, the raw
          value/placeholder would be inconsistent with the configured preburst ratio,
          and in particular whether complete storm assembly is triggered for a given
          cell could silently disagree with what the configured percentile actually
          implies. ``BurstLossesNew`` is NSW-only - for other locations, an empty table
          is returned instead of raising, signalling to :meth:`_initial_loss` that every
          duration/AEP cell must instead be derived directly from the preburst ratio and
          storm initial loss (equivalent to every cell being a ``"Use PB TP"``
          placeholder).
        * ``"probability_neutral"`` - the legacy (NSW-only) probability-neutral burst
          initial loss table (``BurstIL``). Raises :class:`ArrError` if the Data Hub
          hasn't provided this layer for the queried location (i.e. it's not in NSW) -
          unlike ``BurstLossesNew`` above, there is no meaningful fallback for this
          method if the table is missing, since it isn't preburst-derived at all.
          Unlike ``BurstLossesNew``, this is an independently-calibrated table that is
          *not* derived from preburst depths/ratios and is not tied to any particular
          IFD baseline year - it is always used as-is, unaffected by ``ifd.baseline_year``.
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
            return _table_to_frame(table)
        table = self.response.layer('BurstLossesNew')
        if table is None:
            # 'BurstLossesNew' is NSW-only - for other locations, there is no per-
            # duration/AEP burst initial loss table at all, only the flat (AEP/duration
            # independent) storm initial loss - see _storm_initial_loss_pct_datahub.
            # Return an empty table rather than raising: _initial_loss() treats an
            # empty table as "every cell must be derived from the preburst ratio",
            # exactly as it already does for individual 'Use PB TP' placeholder cells.
            return pd.DataFrame()
        burst_losses = _table_to_frame(table)
        # always recalculate every numeric cell from the preburst ratio - see the
        # docstring above and :meth:`_recompute_burst_losses_for_ifd_year` - not just
        # when `ifd.baseline_year != 2030`, so the result stays consistent with
        # whatever `preburst.percentile` is configured, regardless of baseline year.
        return self._recompute_burst_losses_for_ifd_year(burst_losses)

    def _recompute_burst_losses_for_ifd_year(self, burst_losses: pd.DataFrame) -> pd.DataFrame:
        """The Data Hub's burst initial loss table (``BurstLossesNew``/``BurstIL``) is
        only computed by the Data Hub itself against its own recommended preburst
        percentile and the 2030 ("current") baseline IFD depths - it is derived
        as the (duration-independent) storm initial loss minus a preburst depth, where
        that preburst depth is itself a preburst ratio multiplied by the 2030
        baseline's point design depth. Every numeric cell is always recalculated the
        same way, but against the *configured* ``preburst.percentile`` and
        ``ifd.baseline_year`` (rather than trusting the Data Hub's own raw value,
        which is only ever consistent with its own recommended percentile and the
        2030 baseline):

            burst_il = storm_il - preburst_ratio(percentile, duration, aep) * point_depth(ifd.baseline_year)

        matching the same preburst-based derivation used elsewhere (see
        :meth:`_fill_placeholder_adjacent_gaps`, :meth:`_extrapolate_edge_aep_loss`). If
        the recalculated value would be negative (the preburst rainfall alone exceeds
        the storm initial loss), the cell is set to the ``"Use PB TP"`` placeholder
        instead, forcing complete storm assembly for that cell - matching the Data
        Hub's own convention, but now based on the *configured* preburst ratio rather
        than the Data Hub's own recommended one, so switching ``preburst.percentile``
        can change whether a given cell triggers complete storm assembly, as expected.
        This is applied uniformly to every cell in the table's domain, including cells
        the Data Hub itself already flagged as ``"Use PB TP"`` - that flag is only ever
        valid for the Data Hub's own recommended percentile, so it must be
        recalculated (and may become numeric instead) for a different configured
        ``preburst.percentile`` just like any other cell.
        """
        from .complete_storm import _preburst_ratio
        baseline_ifd = self._ifd_frame(self.config.ifd.baseline_year, None)
        percentile = self.config.preburst.percentile
        # cast to object dtype upfront - a recalculated cell may need to become the
        # "Use PB TP" placeholder string, which a purely-numeric (float64) column
        # dtype cannot hold (e.g. `BurstIL`, which may have no placeholders at all).
        result = burst_losses.astype(object).copy()
        for dur in burst_losses.index:
            duration = float(dur)
            for col in burst_losses.columns:
                aep_pct = float(col)
                point_depth = float(_interp_table(baseline_ifd, [duration], [aep_pct]).iloc[0, 0])
                ratio = _preburst_ratio(self.response, percentile, duration, aep_pct)
                storm_il = self._storm_initial_loss_pct_datahub(aep_pct)
                recalculated = storm_il - ratio * point_depth
                if recalculated < 0:
                    logger.debug(
                        "Duration %s min, AEP %s%%: recalculated burst initial loss for ifd.baseline_year=%s (storm "
                        "initial loss %.3f mm - preburst depth %.3f mm = %.3f mm) is negative - treating this "
                        "cell as 'Use PB TP' (complete storm assembly required).", dur, aep_pct,
                        self.config.ifd.baseline_year, storm_il, ratio * point_depth, recalculated,
                    )
                    result.loc[dur, col] = 'Use PB TP'
                else:
                    result.loc[dur, col] = recalculated
        return result

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
        # 'NewStormLosses' is NSW-only - non-NSW locations instead have a flat (not
        # AEP-dependent) 'StormLossesNonNSW' summary value.
        non_nsw_losses = self.response.layer('StormLossesNonNSW')
        if non_nsw_losses and 'Storm Continuing Losses (mm/h)' in non_nsw_losses:
            return float(non_nsw_losses['Storm Continuing Losses (mm/h)'])
        # fall back to the legacy single 'StormLosses' summary value (not AEP-dependent)
        storm_losses = self.response.layer('StormLosses')
        if storm_losses and 'Storm Continuing Losses (mm/h)' in storm_losses:
            return float(storm_losses['Storm Continuing Losses (mm/h)'])
        raise ArrError("ARR Data Hub response is missing continuing loss data "
                        "('NewStormLosses'/'StormLossesNonNSW'/'StormLosses' layers).")

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
        initial loss (see :meth:`_initial_loss`).

        An AEP outside ``NewStormLosses``' own AEP row range - rarer than its rarest,
        or more frequent than its most frequent (typically 50%-1% AEP; e.g. 63.2%
        AEP/1 EY) - holds the nearest edge row's own storm initial loss constant,
        mirroring how the burst initial loss table/preburst ratio are extrapolated at
        those same edges (see :meth:`_extrapolate_edge_aep_loss`), rather than falling
        back to the non-AEP-specific ``StormLossesNonNSW``/``StormLosses`` layers,
        which aren't NSW's per-AEP storm initial loss dataset.
        """
        new_losses = self.response.layer('NewStormLosses')
        if new_losses and 'losses' in new_losses:
            rows = new_losses['losses']
            for row in rows:
                if abs(_aep_str_to_pct(row['AEP']) - aep_pct) < 1e-6:
                    return float(row['Storm Initial Loss (mm)'])
            row_aeps = [_aep_str_to_pct(row['AEP']) for row in rows]
            if row_aeps and (aep_pct < min(row_aeps) or aep_pct > max(row_aeps)):
                nearest_row = min(rows, key=lambda row: abs(_aep_str_to_pct(row['AEP']) - aep_pct))
                return float(nearest_row['Storm Initial Loss (mm)'])
        # 'NewStormLosses' is NSW-only - non-NSW locations instead have a flat (not
        # AEP-dependent) 'StormLossesNonNSW' summary value. Also used as a last-resort
        # fallback for an NSW AEP that falls strictly *within* NewStormLosses' own AEP
        # range but isn't itself one of its rows (an interior gap, not an edge).
        non_nsw_losses = self.response.layer('StormLossesNonNSW')
        if non_nsw_losses and 'Storm Initial Losses (mm)' in non_nsw_losses:
            return float(non_nsw_losses['Storm Initial Losses (mm)'])
        storm_losses = self.response.layer('StormLosses')
        if storm_losses and 'Storm Initial Losses (mm)' in storm_losses:
            return float(storm_losses['Storm Initial Losses (mm)'])
        raise ArrError("ARR Data Hub response is missing storm initial loss data "
                        "('NewStormLosses'/'StormLossesNonNSW'/'StormLosses' layers).")

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

    def _derive_burst_loss_via_ratio(self, duration: float, aep_pct: float) -> Union[float, str]:
        """Derives a single burst initial loss cell directly from the preburst ratio
        and storm initial loss (log-log interpolated, never interpolating the burst
        loss table's own values)::

            burst_il = storm_il - preburst_ratio(percentile, duration, aep) * point_depth(duration, aep)

        Returns the ``"Use PB TP"`` placeholder string instead (with an info-level log
        message) if the result would be negative (the preburst rainfall alone exceeds
        the storm initial loss) - matching the Data Hub's own convention, and forcing
        complete storm assembly for that cell. Used both to gap-fill individual missing
        duration cells within an existing ``BurstLossesNew`` table (see
        :meth:`_derive_missing_duration_burst_losses`) and to derive every cell when no
        ``BurstLossesNew`` table exists at all for this location (see
        :meth:`_initial_loss`)."""
        from .complete_storm import _preburst_ratio
        baseline_ifd = self._ifd_frame(self.config.ifd.baseline_year, None)
        percentile = self.config.preburst.percentile
        point_depth = float(_interp_table(baseline_ifd, [duration], [aep_pct]).iloc[0, 0])
        ratio = _preburst_ratio(self.response, percentile, duration, aep_pct)
        storm_il = self._storm_initial_loss_pct_datahub(aep_pct)
        implied_burst_loss = storm_il - ratio * point_depth
        if implied_burst_loss < 0:
            logger.debug(
                "Duration %s min, AEP %s%%: implied burst initial loss (storm initial loss %.3f mm - "
                "preburst depth %.3f mm = %.3f mm) is negative - treating this cell as 'Use PB TP' "
                "(complete storm assembly required).", duration, aep_pct, storm_il, ratio * point_depth,
                implied_burst_loss,
            )
            return 'Use PB TP'
        return implied_burst_loss

    def _derive_missing_duration_burst_losses(self, burst_losses: pd.DataFrame, durations: list) -> pd.DataFrame:
        """Gap-fills any requested duration that falls *within* the range of
        ``burst_losses`` (i.e. between its minimum and maximum duration) but isn't
        itself one of its rows - e.g. a requested duration of 270 min, when the table
        only has rows at 180 and 360 min. Dispatches on ``losses.method``:

        * ``"recommended"`` (``BurstLossesNew``) - rather than linearly interpolating
          the table's raw loss *values* between the two
          bracketing duration rows - which would be inconsistent with
          :meth:`_recompute_burst_losses_for_ifd_year` (which always recalculates every
          numeric cell from the preburst ratio table) and
          would not make sense for a gap bracketed by (or adjacent to) a
          ``"Use PB TP"`` placeholder cell - every missing duration/AEP cell is instead
          derived directly via :meth:`_derive_burst_loss_via_ratio`, the same way as
          :meth:`_recompute_burst_losses_for_ifd_year`/:meth:`_extrapolate_edge_aep_loss`,
          never interpolating the burst loss table's own values. Applied uniformly
          regardless of whether the bracketing/neighbouring cells are numeric or already
          ``"Use PB TP"`` placeholders.
        * ``"probability_neutral"`` (``BurstIL``) - unlike ``BurstLossesNew``, this
          table is an independently-calibrated NSW probability-neutral loss table, not
          derived from preburst depths/ratios at all (confirmed against the legacy
          script, which loads it from its own ``[BURSTIL]`` data block and applies no
          preburst-based derivation to it whatsoever). So its gaps are instead plainly
          (straight duration axis, not log) linearly interpolated between the two
          bracketing rows' own raw loss values, matching the legacy script's
          ``interpolate_nan`` for this table - see
          :func:`pytuflow.arr.losses.interpolate_missing_durations`. This table has no
          ``"Use PB TP"`` placeholder cells in practice.
        """
        if burst_losses.empty:
            return burst_losses
        if self.config.losses.method == 'probability_neutral':
            return interpolate_missing_durations(burst_losses, durations)

        lower_bound = float(burst_losses.index.min())
        upper_bound = float(burst_losses.index.max())
        missing = sorted({
            float(d) for d in durations
            if lower_bound < float(d) < upper_bound and float(d) not in burst_losses.index
        })
        if not missing:
            return burst_losses

        # cast to object dtype upfront - a derived cell may need to become the
        # "Use PB TP" placeholder string, which a purely-numeric (float64) column
        # dtype cannot hold.
        result = burst_losses.astype(object).copy()
        for dur in missing:
            for col in burst_losses.columns:
                aep_pct = float(col)
                result.loc[dur, col] = self._derive_burst_loss_via_ratio(dur, aep_pct)
        return result.sort_index()


    def _extrapolate_edge_aep_loss(self, burst_losses: pd.DataFrame, duration: float, aep_pct: float,
                                    durations: list) -> float:
        """Computes the burst initial loss for an AEP outside the Data Hub's burst
        initial loss table's AEP column range - either rarer than its rarest (smallest
        %) column, or more frequent than its most frequent (largest %) column, e.g.
        63.2% AEP (1 EY) when ``BurstLossesNew``/``BurstIL``/``NewStormLosses`` only
        extend from 50% down to 1% AEP. Dispatches on ``losses.method``:

        * ``"recommended"`` (``BurstLossesNew``) - holds the preburst ratio constant
          beyond that edge and applies it against the actual (not clamped) point design
          depth at the requested AEP - the same principle as the
          ``'constant_preburst_ratio'`` short-duration extrapolation method, applied
          along the AEP axis instead of the duration axis.

          Unlike the legacy script (which has no burst/storm initial loss data at all
          for these AEPs and ultimately falls back to a burst initial loss of 0), the
          preburst ratio table (``Preburst<percentile>``/``RecPreburst``) is looked up
          via :func:`complete_storm._preburst_ratio`, which log-log interpolates and
          clamps to the nearest edge value beyond the table's rarest/most-frequent AEP
          column - i.e. it naturally "holds the ratio constant" without any extra code
          here. The point design depth, however, is *not* clamped - the Data Hub's IFD
          table extends to both rarer (e.g. 0.05%) and more frequent AEPs than the loss
          tables do, so the actual (log-log interpolated) point depth at the requested
          AEP is used.
        * ``"probability_neutral"`` (``BurstIL``) - unlike ``BurstLossesNew``, this
          table is not derived from preburst depths/ratios at all (see
          :meth:`_burst_loss_frame`), so there is no principled preburst-based way to
          extrapolate it. Instead, the nearest (rarest, or most frequent, matching
          which edge was exceeded) available AEP column's own raw loss value is held
          constant (at the requested duration, gap-filled via
          :meth:`_derive_missing_duration_burst_losses` if needed, clamped to the
          nearest available duration if the requested duration falls outside the
          table's own duration range entirely).
        """
        available_aeps = [float(c) for c in burst_losses.columns]
        is_rare_edge = aep_pct < min(available_aeps)
        if self.config.losses.method == 'probability_neutral':
            filled = self._derive_missing_duration_burst_losses(burst_losses, durations)
            if duration in filled.index:
                row_duration = duration
            else:
                # requested duration is outside the table's own duration range entirely
                # (handled separately by `losses.extrapolation_method`) - clamp to the
                # nearest available duration rather than attempting to extrapolate here.
                row_duration = min(filled.index, key=lambda d: abs(float(d) - duration))
            edge_aep_col = (min if is_rare_edge else max)(filled.columns, key=lambda c: float(c))
            return float(filled.loc[row_duration, edge_aep_col])
        from .complete_storm import _preburst_ratio
        percentile = self.config.preburst.percentile
        ratio = _preburst_ratio(self.response, percentile, duration, aep_pct)
        baseline_ifd = self._ifd_frame(self.config.ifd.baseline_year, None)
        point_depth = float(_interp_table(baseline_ifd, [duration], [aep_pct]).iloc[0, 0])
        storm_il = self._storm_initial_loss_pct(aep_pct)
        return storm_il - ratio * point_depth

    def _initial_loss(self, duration: float, aep_name: str, durations: list,
                       scenario_label: Optional[str] = None) -> float:
        aep_pct = aep_name_to_pct(aep_name)
        burst_losses = self._burst_loss_frame()
        if burst_losses.empty:
            # no per-duration/AEP burst initial loss table exists at all for this
            # location/method (e.g. 'BurstLossesNew' is NSW-only, and is missing
            # entirely for other locations - see _burst_loss_frame) - derive this cell
            # directly from the preburst ratio and storm initial loss, exactly as for an
            # individual 'Use PB TP' placeholder cell in an existing table.
            value = self._derive_burst_loss_via_ratio(duration, aep_pct)
            if value == 'Use PB TP':
                raise _NeedsCompleteStorm(
                    f"No burst initial loss table is available for this location (e.g. 'BurstLossesNew' is "
                    f"NSW-only), and the derived burst initial loss for {aep_name}/{duration}min would be "
                    f"negative (the preburst rainfall alone exceeds the storm initial loss)."
                )
            # only record this cell as "extrapolated" if the requested duration/AEP is
            # actually outside the underlying preburst ratio table's own range (rarer/
            # more frequent than its AEP columns, or shorter/longer than its duration
            # rows) - otherwise every cell would be flagged, since there's no
            # BurstLossesNew/BurstIL table to compare against at all for this location,
            # even though most cells here are a plain in-range lookup, not a genuine
            # edge-case extrapolation.
            from .complete_storm import _preburst_ratio_frame
            ratio_table = _preburst_ratio_frame(self.response, self.config.preburst.percentile)
            table_durations = [float(d) for d in ratio_table.index]
            table_aeps = [float(c) for c in ratio_table.columns]
            if (duration < min(table_durations) or duration > max(table_durations)
                    or aep_pct < min(table_aeps) or aep_pct > max(table_aeps)):
                self._extrapolated_loss_records.append({
                    'cc_scenario': scenario_label,
                    'duration': duration,
                    'aep_pct': aep_pct,
                    'initial_loss': value,
                })
            return value
        # AEPs outside the burst loss table's AEP column range - either rarer than its
        # rarest (smallest %), or more frequent than its most frequent (largest %,
        # typically 50%, e.g. 63.2% AEP/1 EY) - have no burst/storm initial loss data
        # at all in the Data Hub (the loss tables are limited to 50%-1% AEP, unlike the
        # IFD depth table, which extends much further in both directions) - hold the
        # preburst ratio constant beyond that edge (or, for 'probability_neutral', the
        # nearest AEP column's raw loss value - see _extrapolate_edge_aep_loss) instead
        # of silently reusing the nearest column's raw loss value unchanged.
        available_aeps = [float(c) for c in burst_losses.columns]
        if available_aeps and (aep_pct < min(available_aeps) or aep_pct > max(available_aeps)):
            value = self._extrapolate_edge_aep_loss(burst_losses, duration, aep_pct, durations)
            self._extrapolated_loss_records.append({
                'cc_scenario': scenario_label,
                'duration': duration,
                'aep_pct': aep_pct,
                'initial_loss': value,
            })
            return value
        # gap-fill any requested duration that falls within the table's duration range
        # but isn't itself one of its rows (e.g. 270 min, between rows at 180 and
        # 360 min) - derived directly from the preburst ratio/point depth (log-log
        # interpolated), never by interpolating the burst loss table's raw values -
        # see _derive_missing_duration_burst_losses.
        burst_losses = self._derive_missing_duration_burst_losses(burst_losses, durations)
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
        scenarios: list = [(None, self.config.ifd.baseline_year, None)]
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
                            if (self.config.preburst.pattern_method or '').lower() == 'none':
                                # 'none' disables auto complete storm assembly entirely -
                                # just set the burst initial loss to 0 for this cell
                                # instead of building any preburst pattern.
                                logger.warning(
                                    "%s/%smin requires complete storm assembly (%s), but "
                                    "preburst.pattern_method == 'none' - setting the burst initial loss to 0 "
                                    "for this event instead of assembling a complete storm.",
                                    aep_name, duration, e,
                                )
                                il = 0.0
                            else:
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
