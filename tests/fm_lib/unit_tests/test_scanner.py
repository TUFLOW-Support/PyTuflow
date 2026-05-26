import unittest

from pytuflow._fm.converters.converter import Converter


class TestScanner(unittest.TestCase):

    def test_scanner_scan(self):
        class Unit:
            def __init__(self, id_, type_, TYPE):
                self.id = id_
                self.type = type_
                self.ups_units = []
                self.dns_units = []
                self.parent = None
                self.TYPE = TYPE

        units = [
            Unit('A', 'RIVER', 'unit'),
            Unit('B', 'RIVER', 'unit'),
            Unit('C', 'RIVER', 'unit'),
            Unit('D', 'RIVER', 'unit'),
            Unit('E', 'INTERPOLATE', 'unit'),
            Unit('F', 'CONDUIT', 'unit'),
            Unit('G', 'CONDUIT', 'unit'),
            Unit('H', 'ORIFICE', 'structure'),
            Unit('I', 'JUNCTION', 'junction'),
            Unit('J', 'RIVER', 'unit')
        ]
        units[0].ups_units.append(units[1])
        units[1].ups_units.append(units[2])
        units[2].ups_units.append(units[3])
        units[3].ups_units.append(units[4])
        units[4].ups_units.append(units[5])
        units[5].ups_units.append(units[6])
        units[6].ups_units.append(units[7])
        units[7].ups_units.append(units[8])
        units[8].ups_units.append(units[9])

        units[9].dns_units.append(units[8])
        units[8].dns_units.append(units[7])
        units[7].dns_units.append(units[6])
        units[6].dns_units.append(units[5])
        units[5].dns_units.append(units[4])
        units[4].dns_units.append(units[3])
        units[3].dns_units.append(units[2])
        units[2].dns_units.append(units[1])

        conv = Converter(units[0])
        ups_unit = conv.get_ups_unit(units[0])
        self.assertEqual(units[1], ups_unit)
        ups_unit = conv.get_ups_unit(units[9])
        self.assertIsNone(ups_unit)
        ups_unit = conv.get_ups_unit(units[3])
        self.assertEqual(units[5], ups_unit)
        ups_unit = conv.get_ups_unit(units[5])
        self.assertEqual(units[6], ups_unit)
        ups_unit = conv.get_ups_unit(units[6])
        self.assertEqual(units[9], ups_unit)
        ups_unit = conv.get_ups_unit(units[0], True)
        self.assertEqual(units[0], ups_unit)
        ups_unit = conv.get_ups_unit(units[1], True)
        self.assertEqual(units[1], ups_unit)
        ups_unit = conv.get_ups_unit(units[4], True)
        self.assertEqual(units[5], ups_unit)
