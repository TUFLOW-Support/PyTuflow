"""Tests for :mod:`pytuflow.arr.arf`, including a byte-for-byte cross-check against the
legacy ``ARR_TUFLOW_func_lib.arf_factors`` implementation.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

from pytuflow.arr.arf import aep_name_to_pct, arf_factors

LEGACY_LIB_PATH = Path(__file__).parent / 'arr_legacy' / 'ARR_TUFLOW_func_lib.py'


@pytest.fixture(scope='module')
def legacy_func_lib():
    """Dynamically imports the legacy ``ARR_TUFLOW_func_lib`` module (untouched,
    read-only reference) so its ``arf_factors`` can be directly compared against."""
    if not LEGACY_LIB_PATH.exists():
        pytest.skip('ARR_legacy/ARR_TUFLOW_func_lib.py not available in this checkout.')
    spec = importlib.util.spec_from_file_location('legacy_arr_func_lib', LEGACY_LIB_PATH)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError as e:
        pytest.skip(f'Legacy module could not be imported (missing dependency): {e}')
    return module


ARF_PARAMS = {'a': 0.324, 'b': 0.241, 'c': 0.448, 'd': 0.36, 'e': 0.00404,
              'f': 0.213, 'g': 0.13, 'h': 0.0141, 'i': -0.021}
AREA = 11.4
DURATIONS = [15, 60, 180, 360, 720, 1080, 1440, 2880]
AEP_NAMES = ['1%', '5%', '20%', '50%', '0.5EY', '1 in 200']


def test_aep_name_to_pct():
    assert aep_name_to_pct('1%') == 1.0
    assert aep_name_to_pct('0.5EY') == 39.35
    assert aep_name_to_pct('1 in 200') == 0.5


def test_aep_name_to_pct_unrecognised_raises():
    with pytest.raises(ValueError):
        aep_name_to_pct('not an aep')


def test_arf_factors_matches_legacy(legacy_func_lib):
    ours = arf_factors(AREA, DURATIONS, AEP_NAMES, ARF_PARAMS, arf_frequent=False, min_arf=0.2)
    legacy = legacy_func_lib.arf_factors(
        AREA, DURATIONS, AEP_NAMES,
        ARF_PARAMS['a'], ARF_PARAMS['b'], ARF_PARAMS['c'], ARF_PARAMS['d'], ARF_PARAMS['e'],
        ARF_PARAMS['f'], ARF_PARAMS['g'], ARF_PARAMS['h'], ARF_PARAMS['i'],
        ARF_frequent=False, min_ARF=0.2,
    )
    np.testing.assert_allclose(ours.values, legacy, rtol=0, atol=1e-12)


def test_arf_factors_matches_legacy_frequent_and_min_arf(legacy_func_lib):
    ours = arf_factors(AREA, DURATIONS, AEP_NAMES, ARF_PARAMS, arf_frequent=True, min_arf=0.5)
    legacy = legacy_func_lib.arf_factors(
        AREA, DURATIONS, AEP_NAMES,
        ARF_PARAMS['a'], ARF_PARAMS['b'], ARF_PARAMS['c'], ARF_PARAMS['d'], ARF_PARAMS['e'],
        ARF_PARAMS['f'], ARF_PARAMS['g'], ARF_PARAMS['h'], ARF_PARAMS['i'],
        ARF_frequent=True, min_ARF=0.5,
    )
    np.testing.assert_allclose(ours.values, legacy, rtol=0, atol=1e-12)


def test_arf_never_exceeds_1():
    df = arf_factors(AREA, DURATIONS, AEP_NAMES, ARF_PARAMS)
    assert (df.values <= 1.0).all()


def test_small_catchment_gets_full_arf():
    df = arf_factors(0.5, [1440], ['1%'], ARF_PARAMS)
    assert df.iloc[0, 0] == pytest.approx(1.0)
