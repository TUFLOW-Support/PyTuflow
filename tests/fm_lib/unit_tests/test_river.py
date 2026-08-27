from pathlib import Path
from unittest import TestCase

from pytuflow._fm.parsers.units.river import River


class TestRiver(TestCase):

    def test_load(self):
        p = './tests/fm_lib/data/River_Sections_Only.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'RIVER\n':
                    r = River(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(7, len(rivers))
