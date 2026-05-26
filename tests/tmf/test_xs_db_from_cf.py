from ...pytuflow._tmf.cf.get_control_file_class import get_control_file_class
from ...pytuflow._tmf.settings import TCFConfig


def test_xs_db_from_cf():
    p = './tests/tmf/test_datasets/example_tuflow_cross_sections.ecf'
    cf = get_control_file_class(p)(p, TCFConfig(), None)
    inp = cf.find_input('read gis table links')[0]
    db = inp.cf[0]
    assert db.df.shape == (55, 9)


def test_xs_db_ctx():
    p = './tests/tmf/test_datasets/example_tuflow_cross_sections.ecf'
    cf = get_control_file_class(p)(p)
    ctx = cf.context()
    inp = ctx.find_input('read gis table links')[0]
    db = inp.cf[0]
    assert db.df.shape == (55, 9)


def test_fmxs_from_cf():
    p = './tests/tmf/test_datasets/example_fm_cross_sections.ecf'
    cf = get_control_file_class(p)(p, TCFConfig(), None)
    inp = cf.find_input('xs database')[0]
    db = inp.cf[0]
    assert db.df.shape == (51, 2)


def test_fmxs_from_cf_ctx():
    p = './tests/tmf/test_datasets/example_fm_cross_sections.ecf'
    cf = get_control_file_class(p)(p, TCFConfig(), None)
    ctx = cf.context()
    inp = ctx.find_input('xs database')[0]
    db = inp.cf[0]
    assert db.df.shape == (51, 2)
