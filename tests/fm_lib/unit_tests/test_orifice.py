from pathlib import Path
from unittest import TestCase

from pytuflow._fm.parsers.units.flood_relief import FloodRelief
from pytuflow._fm.parsers.units.inverted_syphon import InvertedSyphon
from pytuflow._fm.parsers.units.orifice import Orifice
from pytuflow._fm.parsers.units.outfall import Outfall


class TestOrifice(TestCase):

    def test_load_orifice(self):
        p = './tests/fm_lib/data/River_Sections_Orifice.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'ORIFICE\n':
                    r = Orifice(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_inverted_syphon(self):
        p = './tests/fm_lib/data/River_Sections_Inverted_Syphon.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'INVERTED SYPHON\n':
                    r = InvertedSyphon(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_outfall(self):
        p = './tests/fm_lib/data/River_Sections_Outfall.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'OUTFALL\n':
                    r = Outfall(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_flood_relief_arch(self):
        p = './tests/fm_lib/data/River_Sections_Flood_Relief_Arch.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'FLOOD RELIEF\n':
                    r = FloodRelief(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))