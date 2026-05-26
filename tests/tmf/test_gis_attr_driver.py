from ...pytuflow._tmf.gis import GISAttributes


def test_dbf_attr_driver():
    p = './tests/tmf/test_datasets/1d_nwk_EG11_001_L.dbf'
    with GISAttributes(p) as gis_attr:
        attrs = list(gis_attr)
        assert len(attrs) == 5


def test_mid_attr_driver():
    p = './tests/tmf/test_datasets/2d_zsh_EG03_Rd_Crest_001.mid'
    with GISAttributes(p) as gis_attr:
        attrs = list(gis_attr)
        assert len(attrs) == 70
        assert len(attrs[0]) == 6


def test_mid_attr_driver_2():
    p = './tests/tmf/test_datasets/2d_zsh_EG03_Rd_Crest_001.mif'
    with GISAttributes(p) as gis_attr:
        attrs = list(gis_attr)
        assert len(attrs) == 70
        assert len(attrs[0]) == 6


def test_gpkg_attr_driver():
    p = './tests/tmf/test_datasets/EG00_001_TGC.gpkg >> 2d_ZSH_EG00_Rd_Crest_001_L'
    with GISAttributes(p) as gis_attr:
        attrs = list(gis_attr)
        assert len(attrs) == 3
        assert len(attrs[0]) == 4
