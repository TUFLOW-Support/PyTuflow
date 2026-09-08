"""Short-duration initial loss extrapolation methods.

The ARR Data Hub's probability-neutral burst initial loss table (``BurstIL`` /
``BurstLossesNew`` layers) is now only provided down to a 30 minute duration (it used to
be limited to 60 minutes in the legacy BOM-based workflow). For durations shorter than
whatever the Data Hub actually provides, one of the methods below can be used to
extrapolate/estimate an initial loss value, exactly as the legacy ``ARR_to_TUFLOW``
script did (ported from ``ARR_TUFLOW_func_lib.py``).

Continuing loss is not duration-dependent and is not extrapolated by these methods - the
Data Hub's storm continuing loss value is used as-is for all durations.

These methods are only relevant when ``losses.method`` in the config is set to something
other than ``"datahub"`` - i.e. the user has explicitly opted to extrapolate/override
rather than just using the Data Hub's own (including climate-change-adjusted) design
losses directly.
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
        One of ``'interpolate'``, ``'rahman'``, ``'hill'``, ``'static'``.
    ils : float, optional
        Representative storm initial loss (mm). Required for ``'rahman'``/``'hill'``.
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
    elif method == 'interpolate':
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
            new_rows[col] = linear_interp_loss(short_durations, threshold, float(ref_value))
    else:
        raise ArrError(f"Unknown loss extrapolation method: '{method}'")

    combined = pd.concat([known_losses, new_rows])
    return combined.sort_index()
