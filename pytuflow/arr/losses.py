"""Short-duration initial loss extrapolation methods.

The ARR Data Hub's probability-neutral burst initial loss table (``BurstIL`` /
``BurstLossesNew`` layers) is now only provided down to a 30 minute duration (it used to
be limited to 60 minutes in the legacy BOM-based workflow). For durations shorter than
whatever the Data Hub actually provides, one of the methods below can be used to
extrapolate/estimate an initial loss value, exactly as the legacy ``ARR_to_TUFLOW``
script did (ported from ``ARR_TUFLOW_func_lib.py``).

Two families of extrapolation are available:

* ``"interpolate"`` / ``"log_interpolate"`` extrapolate the burst initial loss value
  itself directly (assuming 0 mm loss at 0 min duration), using either a straight
  duration axis or a ``log10(duration)`` axis respectively.
* ``"interpolate_preburst"`` / ``"log_interpolate_preburst"`` instead extrapolate the
  implied *preburst depth* (``storm initial loss - burst initial loss``) down to an
  assumed 0 mm preburst depth at 0 min duration, then convert back to a burst initial
  loss - matching the legacy script's ``interpolate_linear_preburst`` /
  ``interpolate_log_preburst`` methods, which extrapolate the preburst rainfall depth
  rather than the loss value. These require the storm initial loss (``ils``).

Separately, :func:`interpolate_missing_durations` linearly fills in any requested
duration that falls *within* the Data Hub's provided duration range but isn't itself one
of the table's rows (e.g. 270 min, between the table's 180 and 360 min rows) - matching
the legacy script's ``interpolate_nan``, which always linearly gap-fills such "internal"
missing durations regardless of the chosen ``lossMethod`` (the ``lossMethod``/
``extrapolation_method`` setting only controls extrapolation *below* the table's
shortest duration). This gap-filling is therefore always applied, independently of
``losses.extrapolation_method``.

Continuing loss is not duration-dependent and is not extrapolated by these methods - the
Data Hub's storm continuing loss value is used as-is for all durations.

The ``extrapolate_short_duration_losses`` methods are only relevant when
``losses.extrapolation_method`` in the config is set to something other than
``"none"`` - i.e. the user has explicitly opted to extrapolate a requested duration
shorter than the Data Hub's shortest provided duration, independently of which burst
loss table ``losses.method`` selects.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

import numpy as np
import pandas as pd

from .exceptions import ArrError

logger = logging.getLogger('pytuflow.arr')

#: Reference duration (minutes) used in the Rahman (2002) and Hill (1996/1998) initial
#: loss formulae. This is a fixed constant of the published methods, not related to
#: whatever duration the Data Hub currently happens to provide data down to.
_REF_DURATION = 60.0


def rahman_loss(duration: Iterable[float], ils: float) -> np.ndarray:
    """Initial loss for durations < 60 min using the Rahman et al. (2002) method.

    Parameters
    ----------
    duration : Iterable[float]
        Durations (minutes) to compute the initial loss for.
    ils : float
        Representative storm initial loss (mm), typically the Data Hub's design storm
        initial loss for the catchment.

    Returns
    -------
    np.ndarray
        Initial loss (mm) for each input duration.
    """
    d = np.asarray(list(duration), dtype=float)
    return float(ils) * (0.5 + 0.25 * np.log10(d / _REF_DURATION))


def hill_loss(duration: Iterable[float], ils: float, mar: float) -> np.ndarray:
    """Initial loss for durations < 60 min using the Hill et al. (1996/1998) method.

    Parameters
    ----------
    duration : Iterable[float]
        Durations (minutes) to compute the initial loss for.
    ils : float
        Representative storm initial loss (mm).
    mar : float
        Mean annual rainfall (mm) for the catchment.

    Returns
    -------
    np.ndarray
        Initial loss (mm) for each input duration.
    """
    d = np.asarray(list(duration), dtype=float)
    ils = float(ils)
    mar = float(mar)
    return ils * (1.0 - (1.0 / (1.0 + 142.0 * (d / _REF_DURATION) ** 0.5 / mar)))


def static_loss(duration: Iterable[float], loss: float) -> np.ndarray:
    """A constant (user-specified) initial loss for all given durations.

    Parameters
    ----------
    duration : Iterable[float]
        Durations (minutes) to compute the initial loss for.
    loss : float
        The constant initial loss value (mm) to adopt.
    """
    d = np.asarray(list(duration), dtype=float)
    return np.full(d.shape, float(loss))


def linear_interp_loss(duration: Iterable[float], ref_duration: float, ref_value: float) -> np.ndarray:
    """Linear interpolation of initial loss between an assumed 0 mm loss at 0 min
    duration, and a known loss value at ``ref_duration``.

    Parameters
    ----------
    duration : Iterable[float]
        Durations (minutes) to compute the initial loss for. Must be <= ``ref_duration``.
    ref_duration : float
        The (shortest known) duration (minutes) with a known initial loss value.
    ref_value : float
        The known initial loss (mm) at ``ref_duration``.
    """
    d = np.asarray(list(duration), dtype=float)
    return ref_value * (d / float(ref_duration))


def log_interp_loss(duration: Iterable[float], ref_duration: float, ref_value: float) -> np.ndarray:
    """Log-linear interpolation of initial loss between an assumed 0 mm loss at 0 min
    duration, and a known loss value at ``ref_duration``, matching the legacy
    ``interpolate_log`` method (interpolates on a ``log10(duration)`` axis, rather than
    ``linear_interp_loss``'s straight-line duration axis).

    Parameters
    ----------
    duration : Iterable[float]
        Durations (minutes) to compute the initial loss for. Must be <= ``ref_duration``.
    ref_duration : float
        The (shortest known) duration (minutes) with a known initial loss value.
    ref_value : float
        The known initial loss (mm) at ``ref_duration``.
    """
    d = np.asarray(list(duration), dtype=float)
    xp = [0.0, np.log10(float(ref_duration))]
    fp = [0.0, float(ref_value)]
    return np.interp(np.log10(d), xp, fp)


def linear_interp_pb_depth(duration: Iterable[float], ref_duration: float, ref_value: float) -> np.ndarray:
    """Linear interpolation of *preburst depth* (not initial loss) between an assumed
    0 mm depth at 0 min duration, and a known preburst depth at ``ref_duration`` -
    matches the legacy ``interpolate_linear_preburst`` method (``linear_interp_pb_dep``
    in ``ARR_TUFLOW_func_lib.py``). Used by the ``"interpolate_preburst"``
    extrapolation method: the extrapolated preburst *depth* (rather than the burst
    initial loss directly) is subtracted from the storm initial loss to derive the
    burst initial loss for the short duration.
    """
    return linear_interp_loss(duration, ref_duration, ref_value)


def log_interp_pb_depth(duration: Iterable[float], ref_duration: float, ref_value: float) -> np.ndarray:
    """Log-linear interpolation of *preburst depth* between an assumed 0 mm depth at
    0 min duration, and a known preburst depth at ``ref_duration`` - matches the
    legacy ``interpolate_log_preburst`` method (``log_interp_pb_dep`` in
    ``ARR_TUFLOW_func_lib.py``). Used by the ``"log_interpolate_preburst"``
    extrapolation method.
    """
    return log_interp_loss(duration, ref_duration, ref_value)


def extrapolate_short_duration_losses(
        known_losses: pd.DataFrame,
        target_durations: Iterable[float],
        method: str = 'interpolate',
        ils: Optional[float] = None,
        mar: Optional[float] = None,
        static_loss_value: Optional[float] = None,
) -> pd.DataFrame:
    """Extends a known initial-loss table (duration index, AEP columns) with additional
    rows for any ``target_durations`` shorter than the shortest known duration.

    Non-numeric placeholder cells in ``known_losses`` (e.g. the Data Hub's ``"Use PB
    TP"`` cells, indicating the preburst temporal pattern should be used directly
    instead of a fixed initial loss) are left untouched, and are not used as an
    interpolation reference (a warning is logged and the extrapolated cell is left as
    ``NaN`` in that case).

    Parameters
    ----------
    known_losses : pd.DataFrame
        Index = duration (minutes, ascending), columns = AEP magnitude. Values are
        initial loss (mm), or a non-numeric placeholder.
    target_durations : Iterable[float]
        Durations (minutes) that must be present in the returned table. Only entries
        shorter than ``known_losses.index.min()`` trigger extrapolation; other
        durations are returned unchanged (nearest known value is not invented here).
    method : str
        One of ``'interpolate'``, ``'log_interpolate'``, ``'interpolate_preburst'``,
        ``'log_interpolate_preburst'``, ``'rahman'``, ``'hill'``, ``'static'``.
    ils : float, optional
        Representative storm initial loss (mm). Required for ``'rahman'``/``'hill'``/
        ``'interpolate_preburst'``/``'log_interpolate_preburst'``.
    mar : float, optional
        Mean annual rainfall (mm). Required for ``'hill'``.
    static_loss_value : float, optional
        Constant initial loss (mm) to adopt. Required for ``'static'``.

    Returns
    -------
    pd.DataFrame
        A copy of ``known_losses`` with additional short-duration rows appended (sorted
        by duration).
    """
    if known_losses.empty:
        raise ArrError('Cannot extrapolate short duration losses from an empty losses table.')

    threshold = float(known_losses.index.min())
    short_durations = sorted({float(d) for d in target_durations if float(d) < threshold})
    if not short_durations:
        return known_losses.copy()

    if method == 'rahman' and ils is None:
        raise ArrError("'ils' is required when using the 'rahman' loss extrapolation method.")
    if method == 'hill' and (ils is None or mar is None):
        raise ArrError("'ils' and 'mar' are required when using the 'hill' loss extrapolation method.")
    if method == 'static' and static_loss_value is None:
        raise ArrError("'static_loss_value' is required when using the 'static' loss extrapolation method.")

    new_rows = pd.DataFrame(index=short_durations, columns=known_losses.columns, dtype=float)
    if method == 'rahman':
        values = rahman_loss(short_durations, ils)
        for col in known_losses.columns:
            new_rows[col] = values
    elif method == 'hill':
        values = hill_loss(short_durations, ils, mar)
        for col in known_losses.columns:
            new_rows[col] = values
    elif method == 'static':
        values = static_loss(short_durations, static_loss_value)
        for col in known_losses.columns:
            new_rows[col] = values
    elif method in ('interpolate', 'log_interpolate'):
        interp_fn = linear_interp_loss if method == 'interpolate' else log_interp_loss
        ref_row = known_losses.loc[threshold]
        for col in known_losses.columns:
            ref_value = ref_row[col]
            if not isinstance(ref_value, (int, float)) or pd.isna(ref_value):
                logger.warning(
                    "Cannot interpolate short duration losses for AEP column '%s' - reference value at "
                    "duration %s is non-numeric ('%s'). Leaving as NaN.", col, threshold, ref_value
                )
                new_rows[col] = np.nan
                continue
            new_rows[col] = interp_fn(short_durations, threshold, float(ref_value))
    elif method in ('interpolate_preburst', 'log_interpolate_preburst'):
        if ils is None:
            raise ArrError(f"'ils' (storm initial loss) is required when using the '{method}' loss "
                            f"extrapolation method.")
        interp_fn = linear_interp_pb_depth if method == 'interpolate_preburst' else log_interp_pb_depth
        ref_row = known_losses.loc[threshold]
        for col in known_losses.columns:
            ref_value = ref_row[col]
            if not isinstance(ref_value, (int, float)) or pd.isna(ref_value):
                logger.warning(
                    "Cannot interpolate short duration preburst depths for AEP column '%s' - reference value "
                    "at duration %s is non-numeric ('%s'). Leaving as NaN.", col, threshold, ref_value
                )
                new_rows[col] = np.nan
                continue
            # burst_loss = storm_ils - preburst_depth, so the known preburst depth at
            # `threshold` is recovered by inverting that relationship, extrapolated down
            # to 0 mm at 0 min duration, then converted back to a burst initial loss.
            ref_pb_depth = float(ils) - float(ref_value)
            extrapolated_pb_depth = interp_fn(short_durations, threshold, ref_pb_depth)
            new_rows[col] = float(ils) - extrapolated_pb_depth
    else:
        raise ArrError(f"Unknown loss extrapolation method: '{method}'")

    combined = pd.concat([known_losses, new_rows])
    return combined.sort_index()


def interpolate_missing_durations(known_losses: pd.DataFrame, target_durations: Iterable[float]) -> pd.DataFrame:
    """Linearly fills in any ``target_durations`` that fall *within* the range of
    ``known_losses`` (i.e. between its minimum and maximum duration) but aren't
    themselves one of its rows - e.g. a requested duration of 270 min, when the table
    only has rows at 180 and 360 min. Matches the legacy script's ``interpolate_nan``,
    which always linearly gap-fills such durations on a straight (not log) duration
    axis, regardless of the chosen ``lossMethod``/``extrapolation_method`` (that setting
    only controls extrapolation *below* the table's shortest duration - see
    :func:`extrapolate_short_duration_losses`).

    Non-numeric placeholder cells (e.g. the Data Hub's ``"Use PB TP"`` cells) adjacent to
    a gap are not used as interpolation references - the gap is left as ``NaN`` in that
    column, with a warning logged, rather than guessing.

    Parameters
    ----------
    known_losses : pd.DataFrame
        Index = duration (minutes, ascending), columns = AEP magnitude.
    target_durations : Iterable[float]
        Durations (minutes) that must be present in the returned table. Only entries
        strictly between ``known_losses.index.min()`` and ``known_losses.index.max()``,
        and not already present, trigger interpolation.

    Returns
    -------
    pd.DataFrame
        A copy of ``known_losses`` with additional interpolated rows inserted (sorted by
        duration).
    """
    if known_losses.empty:
        raise ArrError('Cannot interpolate missing durations from an empty losses table.')

    lower_bound = float(known_losses.index.min())
    upper_bound = float(known_losses.index.max())
    missing = sorted({
        float(d) for d in target_durations
        if lower_bound < float(d) < upper_bound and float(d) not in known_losses.index
    })
    if not missing:
        return known_losses.copy()

    known_durations = sorted(known_losses.index)
    new_rows = pd.DataFrame(index=missing, columns=known_losses.columns, dtype=float)
    for dur in missing:
        lower_dur = max(d for d in known_durations if d < dur)
        upper_dur = min(d for d in known_durations if d > dur)
        lower_row = known_losses.loc[lower_dur]
        upper_row = known_losses.loc[upper_dur]
        for col in known_losses.columns:
            lower_value, upper_value = lower_row[col], upper_row[col]
            if (not isinstance(lower_value, (int, float)) or pd.isna(lower_value)
                    or not isinstance(upper_value, (int, float)) or pd.isna(upper_value)):
                logger.warning(
                    "Cannot interpolate burst initial loss for duration %s min, AEP column '%s' - one of the "
                    "bracketing values (duration %s: '%s', duration %s: '%s') is non-numeric. Leaving as NaN.",
                    dur, col, lower_dur, lower_value, upper_dur, upper_value,
                )
                new_rows.loc[dur, col] = np.nan
                continue
            frac = (dur - lower_dur) / (upper_dur - lower_dur)
            new_rows.loc[dur, col] = float(lower_value) + frac * (float(upper_value) - float(lower_value))

    combined = pd.concat([known_losses, new_rows])
    return combined.sort_index()
