from unittest import TestCase

import numpy as np

from pytuflow._fm.parsers.dat import DAT
from pytuflow._fm.parsers.gxy import GXY


class TestDat(TestCase):

    def test_load(self):
        p = './tests/fm_lib/data/FMT_M01_001.dat'
        dat = DAT(p)
        self.assertEqual(115, len(dat.units))
        self.assertTrue(np.isclose(dat.unit('INTERPOLATE__FC01.14a').bed_level, 38.8775))
        self.assertTrue(np.isclose(dat.unit('INTERPOLATE__FC01.12a').bed_level, 38.122))
        self.assertTrue(np.isclose(dat.unit('INTERPOLATE__FC01.12b').bed_level, 37.952))
        self.assertTrue(np.isclose(dat.unit('INTERPOLATE__FC01.12c').bed_level, 37.782))

    def test_add_gxy(self):
        datpath = './tests/fm_lib/data/FMT_M01_001.dat'
        gxypath = './tests/fm_lib/data/FMT_M01_001.gxy'
        dat = DAT(datpath)
        gxy = GXY(gxypath)
        dat.add_gxy(gxy)
        self.assertEqual(1, 1)


class TestGXY(TestCase):

    def test_load(self):
        p = './tests/fm_lib/data/FMT_M01_001.gxy'
        gxy = GXY(p)
        self.assertEqual(1, 1)
