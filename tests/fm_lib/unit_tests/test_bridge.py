from pathlib import Path
from unittest import TestCase

from pytuflow._fm.parsers.units.bridge import Bridge


class TestBridge(TestCase):

    def test_load_arch(self):
        p = './tests/fm_lib/data/River_Sections_w_Arch_Bridge.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'BRIDGE\n':
                    r = Bridge(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_pier_loss(self):
        p = './tests/fm_lib/data/River_Sections_w_Pier_Loss_Bridge.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'BRIDGE\n':
                    r = Bridge(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_usbpr(self):
        p = './tests/fm_lib/data/River_Sections_w_USBPR_Bridge.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'BRIDGE\n':
                    r = Bridge(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))
