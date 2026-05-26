from pathlib import Path
from unittest import TestCase

from pytuflow._fm.parsers.units.conduit import Conduit


class TestConduit(TestCase):

    def test_load_asymmetrical(self):
        p = './tests/fm_lib/data/River_Sections_w_Asymmetrical_Conduit.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'CONDUIT\n':
                    r = Conduit(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(2, len(rivers))

    def test_load_circular(self):
        p = './tests/fm_lib/data/River_Sections_w_Circular_Conduit.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'CONDUIT\n':
                    r = Conduit(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(2, len(rivers))

    def test_load_full_arch(self):
        p = './tests/fm_lib/data/River_Sections_w_Full_Arch_Conduit.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'CONDUIT\n':
                    r = Conduit(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(2, len(rivers))

    def test_load_rectangular(self):
        p = './tests/fm_lib/data/River_Sections_w_Rectangular_Conduit.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'CONDUIT\n':
                    r = Conduit(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(2, len(rivers))

    def test_load_sprung_arch(self):
        p = './tests/fm_lib/data/River_Sections_w_Sprung_Arch_Conduit.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'CONDUIT\n':
                    r = Conduit(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(2, len(rivers))

    def test_load_symmetrical(self):
        p = './tests/fm_lib/data/River_Sections_w_Symmetrical_Conduit.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'CONDUIT\n':
                    r = Conduit(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(2, len(rivers))
