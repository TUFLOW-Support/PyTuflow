"""Core event-assembly engine for :mod:`pytuflow.arr`.

For each requested AEP x duration combination, this module:

1. Selects the design (or climate-change-adjusted) rainfall depth from the Data Hub's
   IFD table and interpolates it onto the requested durations/AEPs.
2. Applies the Areal Reduction Factor (see :mod:`pytuflow.arr.arf`) to get an areal
   design burst depth.
3. Selects the burst initial loss directly from the Data Hub's probability-neutral
   burst loss table (``BurstIL``/``BurstLossesNew``), or, for ``losses.method`` other
   than ``"datahub"``, extrapolates/overrides it (see :mod:`pytuflow.arr.losses`).
4. Selects the appropriate set of temporal patterns (see
   :mod:`pytuflow.arr.temporal_patterns`) and multiplies each pattern's percentage
   increments by the areal design burst depth to produce a rainfall hyetograph.

If ``config.complete_storm`` is set, or if the Data Hub's burst initial loss table
returns its ``"Use PB TP"`` placeholder for a given AEP/duration cell (meaning that cell
*requires* complete storm assembly regardless of the config setting - see
:mod:`pytuflow.arr.complete_storm`), a preburst rainfall period is additionally built
and prepended ahead of the design burst, and the full storm initial loss (rather than
the reduced burst initial loss) is used - see :meth:`ArrEngine._storm_initial_loss` and
:mod:`pytuflow.arr.complete_storm`.
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
from .losses import extrapolate_short_duration_losses
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
    burst_loss_table: Optional[pd.DataFrame] = field(default=None, init=False, repr=False)

    # -- data preparation -------------------------------------------------------------

    def _durations(self) -> list:
        dur = self.config.events.duration
        if dur == 'all':
            raise ArrError("events.duration == 'all' is not yet supported.")
        return [float(d) for d in dur]

    def _aep_names(self) -> list:
        aep = self.config.events.aep
        if aep == 'all':
            raise ArrError("events.aep == 'all' is not yet supported.")
        return list(aep)

    def _ifd_frame(self, baseline_year: int, ssp: Optional[str] = None) -> pd.DataFrame:
        if ssp is not None:
            table = self.response.cc_adj_ifd_table(baseline_year, ssp)
        else:
            table = self.response.ifd_table(baseline_year)
        return _table_to_frame(table)

    def _burst_loss_frame(self) -> pd.DataFrame:
        """Returns the probability-neutral burst initial loss table (duration x AEP%),
        preferring ``BurstLossesNew`` (numeric AEP columns) and falling back to
        ``BurstIL`` (string AEP columns) if that is what the Data Hub returned."""
        table = self.response.layer('BurstLossesNew') or self.response.layer('BurstIL')
        if table is None:
            raise ArrError("ARR Data Hub response is missing burst initial loss data "
                            "(expected 'BurstLossesNew' or 'BurstIL' layer).")
        return _table_to_frame(table)

    def _storm_continuing_loss(self, aep_name: str) -> float:
        """Looks up the storm continuing loss (mm/h) for the given AEP from the
        ``NewStormLosses`` layer (not duration-dependent)."""
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
            point_tp = self.response.layer('PointTP', required=True)
            areal_tp = self.response.layer('ArealTP')
            point_url = point_tp['url']
            areal_url = areal_tp['url'] if areal_tp else None
            self._tp_set = TemporalPatternSet.from_api_response(
                point_url, areal_url, catchment_area=self.config.site.catchment_area)
        return self._tp_set

    def _storm_initial_loss(self, aep_name: str) -> float:
        """Looks up the (non-reduced) storm initial loss (mm) for the given AEP - used
        for complete storm events, where the full storm initial loss applies (rather
        than a burst initial loss already reduced for preburst rainfall)."""
        new_losses = self.response.layer('NewStormLosses')
        if new_losses and 'losses' in new_losses:
            aep_pct = aep_name_to_pct(aep_name)
            for row in new_losses['losses']:
                if abs(_aep_str_to_pct(row['AEP']) - aep_pct) < 1e-6:
                    return float(row['Storm Initial Loss (mm)'])
        storm_losses = self.response.layer('StormLosses')
        if storm_losses and 'Storm Initial Losses (mm)' in storm_losses:
            return float(storm_losses['Storm Initial Losses (mm)'])
        raise ArrError("ARR Data Hub response is missing storm initial loss data "
                        "('NewStormLosses'/'StormLosses' layers).")

    def _initial_loss(self, duration: float, aep_name: str, durations: list) -> float:
        aep_pct = aep_name_to_pct(aep_name)
        burst_losses = self._burst_loss_frame()
        losses_cfg = self.config.losses
        if losses_cfg.method != 'datahub':
            extended = extrapolate_short_duration_losses(
                burst_losses, durations, method=losses_cfg.method,
                ils=losses_cfg.user_initial_loss, mar=losses_cfg.mar,
                static_loss_value=losses_cfg.static_loss,
            )
            burst_losses = extended
        # nearest available AEP column (exact match expected in practice)
        col = min(burst_losses.columns, key=lambda c: abs(float(c) - aep_pct))
        if duration not in burst_losses.index:
            raise ArrError(
                f"No burst initial loss available for duration {duration} min - "
                f"set losses.method to extrapolate below {burst_losses.index.min()} min."
            )
        value = burst_losses.loc[duration, col]
        try:
            return float(value)
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
        try:
            self.burst_loss_table = self._burst_loss_frame()
        except ArrError:
            self.burst_loss_table = None

        for scenario_label, baseline_year, ssp in scenarios:
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
                    patterns = tp_set.patterns(duration, aep_name, self.config.events.output_notation)
                    band = _band_of(patterns, aep_name, self.config.events.output_notation)
                    cl = self._storm_continuing_loss(aep_name)

                    preburst = None
                    needs_complete_storm = self.config.complete_storm
                    il = None
                    if not needs_complete_storm:
                        try:
                            il = self._initial_loss(duration, aep_name, durations)
                        except _NeedsCompleteStorm as e:
                            logger.info(
                                "%s/%smin requires complete storm assembly (%s) - automatically switching to "
                                "complete storm for this event.", aep_name, duration, e
                            )
                            needs_complete_storm = True

                    if needs_complete_storm:
                        from .complete_storm import build_preburst
                        preburst = build_preburst(
                            self.response, self.config, tp_set, duration, aep_name, aep_pct, depth_point)
                        il = self._storm_initial_loss(aep_name)

                    results.append(EventResult(
                        aep_name=aep_name, duration=duration, depth_point=depth_point,
                        arf=arf_value, depth_areal=depth_areal, initial_loss=il,
                        continuing_loss=cl, aep_band=band, patterns=patterns,
                        cc_scenario=scenario_label, preburst=preburst,
                    ))
        return results


def _aep_str_to_pct(aep_str: str) -> float:
    aep_str = str(aep_str).strip()
    if aep_str.endswith('%'):
        return float(aep_str[:-1])
    return aep_name_to_pct(aep_str)


def _band_of(patterns: list, aep_name: str, output_notation: str) -> str:
    from .temporal_patterns import aep_band
    return aep_band(aep_name, output_notation)
