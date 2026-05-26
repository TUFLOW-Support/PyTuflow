from pathlib import Path
from unittest import TestCase

from pytuflow._fm.parsers.units.interpolate import Interpolate


class TestInterpolate(TestCase):

    def test_load(self):
        p = './tests/fm_lib/data/River_Sections_w_interpolates.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'INTERPOLATE\n':
                    r = Interpolate(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(2, len(rivers))
