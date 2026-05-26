from ...pytuflow._tmf.db.xs import CrossSectionDatabase


def test_cross_section_database_tuflow():
    p = './tests/tmf/test_datasets/1d_xs_EG14_001_L.shp'
    db = CrossSectionDatabase(p)
    assert db.df.shape == (55, 9)
    val = db.value(r'../test_datasets/csv/1d_xs_M14_C99.csv')
    assert val.shape == (29, 1)
    assert len(sum([x.files for x in db.entries.values()], [])) == 55
    assert not any([x.has_missing_files for x in db.entries.values()])


def test_cross_section_database_tuflow_wildcard():
    p = './tests/tmf/test_datasets/1d_xs_EG14_002_L.shp'
    db = CrossSectionDatabase(p)
    assert db.df.shape == (55, 9)
    assert len(sum([x.files for x in db.entries.values()], [])) == 55
    assert not any([x.has_missing_files for x in db.entries.values()])


def test_cross_section_database_fm():
    p = './tests/tmf/test_datasets/FMT_M01_001.dat'
    db = CrossSectionDatabase(p)
    assert db.df.shape == (51, 2)
    val = db.value('FC01.39')
    assert val.shape == (25, 10)
