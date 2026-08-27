from pathlib import Path
from unittest import TestCase

from pytuflow._fm.parsers.units.crump import Crump
from pytuflow._fm.parsers.units.flat_v_weir import FlatVWeir
from pytuflow._fm.parsers.units.gated_weir import GatedWeir
from pytuflow._fm.parsers.units.labyrinth_weir import LabyrinthWeir
from pytuflow._fm.parsers.units.notweir import Notweir
from pytuflow._fm.parsers.units.qh_control import QhControl
from pytuflow._fm.parsers.units.rnweir import Rnweir
from pytuflow._fm.parsers.units.scweir import Scweir
from pytuflow._fm.parsers.units.syphon import Syphon
from pytuflow._fm.parsers.units.weir import Weir


class TestWeir(TestCase):

    def test_load_broad_crested(self):
        p = './tests/fm_lib/data/River_Sections_Broad_Crested_Weir.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'RNWEIR\n':
                    r = Rnweir(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_crump(self):
        p = './tests/fm_lib/data/River_Sections_Crump_Weir.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'CRUMP\n':
                    r = Crump(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_flat(self):
        p = './tests/fm_lib/data/River_Sections_Flat_V_Weir.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'FLAT-V WEIR\n':
                    r = FlatVWeir(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_qh(self):
        p = './tests/fm_lib/data/River_Sections_Flow_Head_Weir.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'QH CONTROL\n':
                    r = QhControl(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_gated(self):
        p = './tests/fm_lib/data/River_Sections_Gated_weir.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'GATED WEIR\n':
                    r = GatedWeir(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_labyrinth(self):
        p = './tests/fm_lib/data/River_Sections_Labyrinth_weir.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'LABYRINTH WEIR\n':
                    r = LabyrinthWeir(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_notional(self):
        p = './tests/fm_lib/data/River_Sections_Notional_weir.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'NOTWEIR\n':
                    r = Notweir(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_sharp_crested(self):
        p = './tests/fm_lib/data/River_Sections_Sharp_Crested_weir.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'SCWEIR\n':
                    r = Scweir(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_syphon(self):
        p = './tests/fm_lib/data/River_Sections_Syphon.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'SYPHON\n':
                    r = Syphon(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))

    def test_load_weir(self):
        p = './tests/fm_lib/data/River_Sections_General_weir.dat'
        rivers = []
        with Path(p).open() as f:
            i = -1
            for line in f:
                i += 1
                if line == 'WEIR\n':
                    r = Weir(p)
                    r.load(line, f, fixed_field_len=12, line_no=i)
                    rivers.append(r)
                    i = r.line_no
        self.assertEqual(1, len(rivers))
