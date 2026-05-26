from ...pytuflow._tmf.db.drivers.dat import Dat
from ...pytuflow._tmf.db.drivers.river_unit_handler import RiverUnit
from ...pytuflow._tmf.db.drivers.xsdat import FmCrossSection, FmCrossSectionDatabaseDriver


def test_xs_dat_load():
    p = './tests/tmf/test_datasets/FMT_M01_001.dat'
    dat = Dat()
    dat.add_handler(RiverUnit)
    dat.load(p)
    assert len(dat.units(RiverUnit)) == 51


def test_fm_dat_load():
    p = './tests/tmf/test_datasets/FMT_M01_001.dat'
    dat = Dat()
    dat.add_handler(FmCrossSection)
    dat.load(p)
    assert len(dat.units(FmCrossSection)) == 51


def test_fm_database_driver():
    p = './tests/tmf/test_datasets/FMT_M01_001.dat'
    fmdb_driver = FmCrossSectionDatabaseDriver()
    df = fmdb_driver.load(p)
    assert df.shape == (51, 2)
