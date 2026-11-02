"""Areal Reduction Factor (ARF) calculations, ported from ``ARR_TUFLOW_func_lib.py``.

ARF equations are pure functions of catchment area, storm duration, AEP, and the
long-duration ARF parameters (``a``-``i``) returned by the ARR Data Hub's ``ARFParams``
layer - none of this depends on the (now removed) BOM web-scraping, so it can be ported
across largely unchanged.

Reference: ARR Book 2, Chapter 4 (Areal Reduction Factors).
"""

from __future__ import annotations

import logging
from math import log10
from typing import Iterable

import numpy as np
import pandas as pd

logger = logging.getLogger('pytuflow.arr')


def arf_eqn241(area: float, duration: float, aep: float) -> float:
    """Short duration ARF equation (ARR eqn 2.4.1).

    Parameters
    ----------
    area : float
        Catchment area (km2).
    duration : float
        Storm duration (minutes).
    aep : float
        AEP as a fraction (e.g. 0.01 for 1%), between 0.5 and 0.0005.
    """
    area = float(area)
    duration = float(duration)
    aep = float(aep)
    arf = (1.0 - 0.287 * (area ** 0.265 - 0.439 * log10(duration)) * duration ** (-0.36)
           + 2.26e-3 * area ** 0.226 * duration ** 0.125 * (0.3 + log10(aep))
           + 0.0141 * area ** 0.213 * 10.0 ** ((-0.021 * (duration - 180) ** 2.0) / 1440) * (0.3 + log10(aep)))
    return min(1.0, arf)


def arf_eqn242(area: float, duration: float, aep: float,
                a: float, b: float, c: float, d: float, e: float, f: float, g: float, h: float, i: float) -> float:
    """Long duration ARF equation (ARR eqn 2.4.2), using the catchment-specific
    parameters ``a``-``i`` from the Data Hub's ``ARFParams`` layer."""
    area = float(area)
    duration = float(duration)
    aep = float(aep)
    arf = (1.0 - a * (area ** b - c * log10(duration)) * duration ** (-d)
           + e * area ** f * duration ** g * (0.3 + log10(aep))
           + h * 10.0 ** (i * area * (duration / 1440.0)) * (0.3 + log10(aep)))
    return min(1.0, arf)


def arf_eqn243(duration: float, arf12h: float, arf24h: float) -> float:
    """Interpolates ARF between the 12 hour and 24 hour values (ARR eqn 2.4.3)."""
    duration = float(duration)
    return float(arf12h) + (float(arf24h) - float(arf12h)) * ((duration - 720.0) / 720.0)


def arf_eqn244(area: float, arf10k: float) -> float:
    """Adjusts a 10km2 ARF value to the target catchment area (ARR eqn 2.4.4)."""
    area = float(area)
    return 1.0 - 0.6614 * (1.0 - float(arf10k)) * (area ** 0.4 - 1.0)


def _arf_cell(area: float, duration: float, aep_pct: float, min_arf: float, arf_frequent: bool,
              arf_fn) -> float:
    """Applies the AEP-range check and minimum-ARF floor common to all area bands, then
    delegates to ``arf_fn(area, duration, aep_fraction)`` for the actual ARF value."""
    aep_max = 100.0 if arf_frequent else 50.0
    if not (0.05 <= aep_pct <= aep_max):
        return 1.0
    arf = arf_fn(area, duration, aep_pct / 100.0)
    return max(arf, min_arf)


def _short_arf(area, durations, aep_pcts, arf_frequent, min_arf):
    if area <= 1:
        return np.ones((len(durations), len(aep_pcts)))
    if area <= 10:
        fn = lambda a, d, p: arf_eqn244(area, arf_eqn241(10, d, p))
    else:
        if area > 1000:
            logger.warning(
                '%,.0fkm2 out of range of generalised equations for short duration ARF factors. Applying '
                'method for 1000km2, however this may not be applicable for the catchment. Please consult ARR.',
                area
            )
        fn = lambda a, d, p: arf_eqn241(area, d, p)
    return np.array([[_arf_cell(area, d, p, min_arf, arf_frequent, fn) for p in aep_pcts] for d in durations])


def _medium_arf(area, durations, aep_pcts, params, arf_frequent, min_arf):
    a, b, c, d, e, f, g, h, i = params

    def fn(area_, dur_, aep_):
        arf24h = arf_eqn242(area_, 1440, aep_, a, b, c, d, e, f, g, h, i)
        arf12h = arf_eqn241(area_, 720, aep_)
        return arf_eqn243(dur_, arf12h, arf24h)

    if area <= 1:
        return np.ones((len(durations), len(aep_pcts)))
    if area <= 10:
        wrapped = lambda a_, d_, p_: arf_eqn244(area, fn(10, d_, p_))
    else:
        if area > 30000:
            logger.warning(
                '%,.0fkm2 out of range of generalised equations for medium duration ARF factors. Applying '
                'method for 30,000km2, however this may not be applicable for the catchment. Please consult ARR.',
                area
            )
        wrapped = fn
    return np.array([[_arf_cell(area, d, p, min_arf, arf_frequent, wrapped) for p in aep_pcts] for d in durations])


def _long_arf(area, durations, aep_pcts, params, arf_frequent, min_arf):
    a, b, c, d, e, f, g, h, i = params

    def fn(area_, dur_, aep_):
        return arf_eqn242(area_, dur_, aep_, a, b, c, d, e, f, g, h, i)

    if area <= 1:
        return np.ones((len(durations), len(aep_pcts)))
    if area <= 10:
        wrapped = lambda a_, d_, p_: arf_eqn244(area, fn(10, d_, p_))
    else:
        if area > 30000:
            logger.warning(
                '%,.0fkm2 out of range of generalised equations for long duration ARF factors. Applying '
                'method for 30,000km2, however this may not be applicable for the catchment. Please consult ARR.',
                area
            )
        wrapped = fn
    return np.array([[_arf_cell(area, d, p, min_arf, arf_frequent, wrapped) for p in aep_pcts] for d in durations])


def _aep_name_to_pct(aep_name: str) -> float:
    """Converts an AEP/ARI/EY magnitude label (e.g. ``'1%'``, ``'1 in 200'``, ``'0.5EY'``)
    to an AEP percentage (e.g. ``1.0``)."""
    aep_name = str(aep_name).strip()
    if aep_name.endswith('EY'):
        ey = float(aep_name[:-2])
        ey_to_aep = {12: 99.85, 6: 99.75, 4: 98.17, 3: 95.02, 2: 86.47, 1: 63.21, 0.5: 39.35, 0.2: 18.13}
        if ey not in ey_to_aep:
            raise ValueError(f"Unrecognised EY magnitude: '{aep_name}'")
        return ey_to_aep[ey]
    if aep_name.endswith('%'):
        return float(aep_name[:-1])
    if aep_name.lower().startswith('1 in'):
        ari = float(aep_name[4:].strip())
        return 1.0 / ari * 100.0
    # assume % if it is just an float or integer passed
    try:
        ret_aep_name = float(aep_name)
        return ret_aep_name
    except (ValueError, TypeError):
        pass
    raise ValueError(f"Unrecognised AEP/ARI/EY magnitude: '{aep_name}'")


#: Public alias for :func:`_aep_name_to_pct`, used outside this module (e.g. by the core
#: engine) to convert AEP/ARI/EY magnitude labels to AEP percentages.
aep_name_to_pct = _aep_name_to_pct


def arf_factors(
        area: float,
        durations: Iterable[float],
        aep_names: Iterable[str],
        arf_params: dict,
        arf_frequent: bool = False,
        min_arf: float = 0.2,
) -> pd.DataFrame:
    """Calculates ARR Areal Reduction Factors for every combination of duration and
    AEP magnitude.

    Durations are split into short (<= 720 min), medium (720-1440 min), and long
    (>= 1440 min) bands, each using a different combination of the ARR ARF
    equations, following the same approach as the legacy ``ARR_to_TUFLOW`` script.

    Parameters
    ----------
    area : float
        Catchment area (km2). Catchments <= 1 km2 receive an ARF of 1.0 (no reduction).
    durations : Iterable[float]
        Storm durations (minutes).
    aep_names : Iterable[str]
        AEP/ARI/EY magnitude labels (e.g. ``'1%'``, ``'1 in 200'``, ``'0.5EY'``).
    arf_params : dict
        The Data Hub's ``ARFParams`` layer contents - a dict with keys ``a``-``i``
        (long-duration ARF equation parameters).
    arf_frequent : bool
        If True, ARF is also applied to frequent events (AEP > 50%), up to 100%. ARR
        does not recommend this.
    min_arf : float
        Minimum ARF value to apply (ARF is floored at this value rather than allowed to
        reduce further).

    Returns
    -------
    pd.DataFrame
        Index = duration (minutes), columns = ``aep_names`` (as given), values = ARF
        factor (0-1).
    """
    durations = list(durations)
    aep_names = list(aep_names)
    aep_pcts = [_aep_name_to_pct(a) for a in aep_names]
    params = tuple(float(arf_params[k]) for k in ('a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'))

    short = [d for d in durations if d <= 720]
    medium = [d for d in durations if 720 < d < 1440]
    long_ = [d for d in durations if d >= 1440]

    blocks = []
    if short:
        blocks.append((short, _short_arf(area, short, aep_pcts, arf_frequent, min_arf)))
    if medium:
        blocks.append((medium, _medium_arf(area, medium, aep_pcts, params, arf_frequent, min_arf)))
    if long_:
        blocks.append((long_, _long_arf(area, long_, aep_pcts, params, arf_frequent, min_arf)))

    index = [d for durs, _ in blocks for d in durs]
    data = np.concatenate([arr for _, arr in blocks], axis=0) if blocks else np.empty((0, len(aep_pcts)))
    df = pd.DataFrame(data, index=index, columns=aep_names)
    return df.loc[durations]  # restore original duration order
