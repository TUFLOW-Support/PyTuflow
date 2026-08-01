from pathlib import Path
import io
import re
from datetime import datetime
import pytest

from ...pytuflow import FVC, FVSed, FVWQ, RunState, GridDefinitionFileBlockInput, Scope
from ...pytuflow._tmf.parsers.fvcommand import FVCommand, FVWaterQualityCommand
from ...pytuflow._tmf.settings import TCFConfig
from ...pytuflow._tmf.parsers.non_recursive_basic_parser import get_fv_commands
from ...pytuflow._tmf import const


def _strip_command(text):
    t = text
    leading_whitespace = ''
    lhs, rhs, comment = '', '', ''
    if t.strip() and not t[0] in ('!', '#'):
        if '!' in t or '#' in t:
            i = t.index('!') if '!' in t else 9e29
            j = t.index('#') if '#' in t else 9e29
            k = min(i, j)
            t, comment = t[:k], t[k:].strip()
        if '==' in t:
            lhs, rhs = t.split('==', 1)
            rhs = rhs.strip()
        else:
            lhs, rhs = t, None
        if lhs.strip():
            leading_whitespace = re.split(r'\w', lhs, flags=re.IGNORECASE)[0]
        lhs = lhs.strip(' \n\t|')

    return lhs, rhs, comment, leading_whitespace


def _compare_control_files(cf1, cf2):
    lines1 = cf1.splitlines()
    lines2 = cf2.splitlines()

    assert len(lines1) == len(lines2)

    for line1, line2 in zip(lines1, lines2):
        lhs1, rhs1, comment1, leading_whitespace1 = _strip_command(line1)
        lhs2, rhs2, comment2, leading_whitespace2 = _strip_command(line2)

        assert lhs1 == lhs2, f'LHS mismatch: "{lhs1}" != "{lhs2}"'
        assert rhs1 == rhs2, f'RHS mismatch: "{rhs1}" != "{rhs2}"'
        assert comment1 == comment2, f'Comment mismatch: "{comment1}" != "{comment2}"'
        assert leading_whitespace1 == leading_whitespace2, f'Leading whitespace mismatch: "{leading_whitespace1}" != "{leading_whitespace2}"'


def test_fv_block_detection():
    fvc = './tests/tmf/test_datasets/fv/basic_block.fvc'
    with open(fvc) as f:
        for line in f:
            cmd = FVCommand(line.strip(), TCFConfig())
            assert cmd.is_fv_block()
            break


def test_get_fv_command_parser():
    fvc = Path('./tests/tmf/test_datasets/fv/basic_block.fvc')
    commands = list(get_fv_commands(fvc, TCFConfig()))
    assert len(commands) == 3


def test_fvc_class_simple():
    p = Path('./tests/tmf/test_datasets/fv/basic_block.fvc')
    fvc = FVC(p)
    assert len(fvc.find_input('BC', recursive=False)) == 1
    assert len(fvc.find_input('BC', recursive=True)) == 2
    assert len(fvc.inputs[0].files) == 1


def test_fvc_include_file():
    p = './tests/tmf/test_datasets/fv/basic_include.fvc'
    fvc = FVC(p)
    assert len(fvc.inputs) == 1
    assert len(fvc.inputs[0].cf) == 1
    include_file = fvc.inputs[0].cf[0]
    assert len(include_file.inputs) == 10
    assert type(include_file.inputs[0].command()) == FVCommand


def test_fvc_wq_include_file():
    p = './tests/tmf/test_datasets/fv/basic_include_wq.fvc'
    fvc = FVC(p)
    
    fvwq = fvc.fvwq()
    assert fvwq is not None

    assert len(fvwq.inputs) == 1
    assert len(fvwq.inputs[0].cf) == 1

    wq_include = fvwq.inputs[0].cf[0]
    assert len(wq_include.inputs) == 8
    assert type(wq_include.inputs[0].command()) == FVWaterQualityCommand


def test_fv_nested_block_parsing():
    p = Path('./tests/tmf/test_datasets/fv/nested_blocks.fvsed')
    commands = list(get_fv_commands(p, TCFConfig()))
    assert len(commands) == 6


def test_fv_isodate_format():
    p = Path('./tests/tmf/test_datasets/fv/isodate.fvc')
    fvc = FVC(p)
    assert fvc.config.time_format == 'ISODATE'
    assert fvc.find_input('start time')[0].value == datetime(2011, 5, 1)
    assert fvc.find_input('end time')[0].value == datetime(2011, 5, 7)


def test_FLD000_2d_001_fvc():
    p = Path('./tests/tmf/test_datasets/fv/FLD000_2D_001.fvc')
    fvc = FVC(p)
    assert str(fvc) == 'FLD000_2D_001.fvc'
    assert len(fvc.find_input(lhs='^BC$', regex=True)) == 3
    assert len(fvc.find_input(lhs='material')) == 5
    assert len(fvc.find_input(lhs='^Output$', regex=True)) == 5
    
    assert fvc.find_input('bc')[0].files[0] == Path('tests/tmf/test_datasets/fv/../model/gis/2d_ns_Open_BCs_001_L.shp')
    
    start_time = fvc.find_input('start time')[0].value
    assert isinstance(start_time, float)

    wet_dry = fvc.find_input('cell wet/dry')[0].value
    assert isinstance(wet_dry[0], float)
    assert isinstance(wet_dry[1], float)

    ups = fvc.find_input(lhs='bc', recursive=True)[0]
    assert isinstance(ups.value, tuple)
    assert isinstance(ups.value[2], Path)

    dns = fvc.find_input(lhs='bc')[2]
    assert isinstance(dns.value, tuple)
    assert isinstance(dns.value[2], float)


def test_FLD000_2d_001_fvc_write():
    p = Path('./tests/tmf/test_datasets/fv/FLD000_2D_001.fvc')
    fvc = FVC(p)
    buf = io.StringIO()
    fvc.preview(buf)

    output = buf.getvalue()
    with p.open() as f:
        original = f.read()
    _compare_control_files(output, original)


# def test_FMA2_SED_003_nested_block_write():
#     p = Path('./tests/tmf/test_datasets/fv/nested_blocks.fvsed')
#     fvsed = FVSed(p)
#     buf = io.StringIO()
#     fvsed.preview(buf)

#     output = buf.getvalue()
#     with p.open() as f:
#         original = f.read()
#     _compare_control_files(output, original)


# def test_FMA2_SED_003_nested_block_write_2():
#     p = Path('./tests/tmf/test_datasets/fv/nested_blocks_2.fvsed')
#     fvsed = FVSed(p)
#     buf = io.StringIO()
#     fvsed.preview(buf)

#     output = buf.getvalue()
#     with p.open() as f:
#         original = f.read()
#     _compare_control_files(output, original)


def test_nested_block_inside_if():
    p = Path('./tests/tmf/test_datasets/fv/nested_block_inside_if.fvc')
    fvc = FVC(p)

    inp = fvc.find_input('material')[0]
    assert inp.scope == [Scope('Scenario')]

    inp = fvc.find_input('roughness')[0]
    assert inp.scope == [Scope('global')]


# def test_nested_block_inside_if_write():
#     p = Path('./tests/tmf/test_datasets/fv/nested_block_inside_if.fvc')
#     fvc = FVC(p)
#     buf = io.StringIO()
#     fvc.preview(buf)

#     output = buf.getvalue()
#     with p.open() as f:
#         original = f.read()
#     _compare_control_files(output, original)


def test_simple_wq_fvc():
    p = Path('./tests/tmf/test_datasets/fv/basic_wq.fvc')
    fvc = FVC(p)
    assert Path(fvc.config.wq_model_directories[0].value_expanded_path).resolve() == Path('tests/tmf/test_datasets/fv/simple_wqm').resolve()
    assert fvc.find_input('water quality control file')[0].cf[0].fpath.exists()


def test_simple_wq_fvc_in_scenario_block():
    p = './tests/tmf/test_datasets/fv/basic_~s~_wq.fvc'
    fvc = FVC(p)

    assert len(fvc.find_input('water quality control file')) == 2, f'Expected exactly two water quality control files in {p}'
    for wq_cf_inp in fvc.find_input('water quality control file'):
        assert len(wq_cf_inp.files) == 1, f'Expected exactly one file for water quality control file input in {wq_cf_inp}'
        assert wq_cf_inp.cf[0].fpath.exists(), f'Expected water quality control file to exist for {wq_cf_inp}'


def test_simple_wq_fvc_in_separate_scenario_blocks():
    p = './tests/tmf/test_datasets/fv/basic_~s~_wq_002.fvc'
    fvc = FVC(p)

    assert len(fvc.find_input('water quality control file')) == 2, f'Expected exactly two water quality control files in {p}'
    for wq_cf_inp in fvc.find_input('water quality control file'):
        assert len(wq_cf_inp.files) == 1, f'Expected exactly one file for water quality control file input in {wq_cf_inp}'
        assert wq_cf_inp.cf[0].fpath.exists(), f'Expected water quality control file to exist for {wq_cf_inp}'


def test_simple_wq_fvc_in_nested_scenario_blocks():
    p = './tests/tmf/test_datasets/fv/basic_~s~_wq_003.fvc'
    fvc = FVC(p)

    assert len(fvc.find_input('water quality control file')) == 2, f'Expected exactly two water quality control files in {p}'
    for wq_cf_inp in fvc.find_input('water quality control file'):
        assert len(wq_cf_inp.files) == 1, f'Expected exactly one file for water quality control file input in {wq_cf_inp}'
        assert wq_cf_inp.cf[0].fpath.exists(), f'Expected water quality control file to exist for {wq_cf_inp}'


def test_fv_wq_tutorials_loading():
    paths = [
        './tests/tmf/test_datasets/fv/wq/runs/WQ_000.fvc',
        './tests/tmf/test_datasets/fv/wq/runs/WQ_001.fvc',
        './tests/tmf/test_datasets/fv/wq/runs/WQ_002.fvc',
    ]
    for p in paths:
        fvc = FVC(p)

        assert len(fvc.find_input('water quality control file')) == 1, f'Expected exactly one water quality control file in {p}'
        assert len(fvc.find_input('water quality control file')[0].cf) == 1, f'Expected sediment control file to be loaded for {p}'

        fvwq = fvc.find_input('water quality control file')[0].cf[0]
        assert fvwq is not None
        assert fvwq.fpath.exists()


        assert len(fvc.find_input('sediment control file')) == 1, f'Expected exactly one sediment control file in {p}'
        assert len(fvc.find_input('sediment control file')[0].cf) == 1, f'Expected sediment control file to be loaded for {p}'

        fvsed = fvc.find_input('sediment control file')[0].cf[0]
        assert fvsed is not None
        assert fvsed.fpath.exists()


def test_fv_sed_tutorial_001():
    p = './tests/tmf/test_datasets/fv/sed/FMA2_SED_001.fvc'
    fvc = FVC(p)

    assert len(fvc.find_input('sediment control file')) == 1, f'Expected exactly one sediment control file in {p}'
    assert len(fvc.find_input('sediment control file')[0].cf) == 1, f'Expected sediment control file to be loaded for {p}'

    sed_cf = fvc.find_input('sediment control file')[0].cf[0]
    assert sed_cf.fpath.exists()
    p_sed = sed_cf.fpath

    assert len(sed_cf.find_input('material == 0')) == 1, f'Expected exactly one material with ID 0 in sediment control file for {p_sed}'
    assert len(sed_cf.find_input('material == 0')[0].cf) == 1, f'Expected material block to be loaded as control file for {p_sed}'

    material_block = sed_cf.find_input('material == 0')[0].cf[0]
    
    assert len(material_block.find_input('layer == 1')) == 1, f'Expected exactly one layer with ID 1 in material block for {p_sed}'
    assert len(material_block.find_input('layer == 1')[0].cf) == 1, f'Expected layer block to be loaded as control file for {p_sed}'

    layer_block = material_block.find_input('layer == 1')[0].cf[0]
    assert len(layer_block.find_input('dry density')) == 1, f'Expected exactly one dry density input in layer block for {p_sed}'


def test_fv_ptm_tutorial_001():
    p = './tests/tmf/test_datasets/fv/ptm/PT_001.fvc'
    fvc = FVC(p)

    assert len(fvc.find_input('particle tracking control file')) == 1, f'Expected exactly one particle tracking control file in {p}'
    assert len(fvc.find_input('particle tracking control file')[0].cf) == 1, f'Expected particle tracking control file to be loaded for {p}'

    ptm_cf = fvc.find_input('particle tracking control file')[0].cf[0]
    assert ptm_cf.fpath.exists()
    ptm_fpath = ptm_cf.fpath

    assert len(ptm_cf.find_input('group == microplastics')) == 1, f'Expected exactly one group with ID "microplastics" in particle tracking control file for {ptm_fpath}'

def test_fvc_context_generation_no_context_required():
    p = Path('./tests/tmf/test_datasets/fv/basic_wq.fvc')
    fvc = FVC(p)
    fvc_run = fvc.context()
    assert fvc_run is not None


def test_fvc_context_generation_scenario_block():
    p = Path('./tests/tmf/test_datasets/fv/basic_~s~_wq.fvc')
    fvc = FVC(p)

    fvc_run = fvc.context('-s WQ1')
    assert len(fvc_run.find_input('water quality control file')) == 1, f'Expected exactly one water quality control file in "WQ1" scenario context'

    fvc_run = fvc.context('-s HYD')
    assert len(fvc_run.find_input('water quality control file')) == 0, f'Expected no water quality control file in "HYD" scenario context'

    with pytest.raises(ValueError):
        fvc.context('-s NOT_A_SCENARIO')


def test_fv_wl_bc_block_to_bc_dbase():
    p = './tests/tmf/test_datasets/fv/bc/bc_wl.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('2')
    assert df.shape == (744, 1)


def test_fv_wl_block_with_sal_temp_to_bc_dbase():
    p = './tests/tmf/test_datasets/fv/bc/bc_wl_sal_temp.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (3, 7)
    df = bc_dbase.value('2')
    assert df.shape == (744, 1)
    df = bc_dbase.value('2_TEMP')
    assert df.shape == (744, 1)
    df = bc_dbase.value('2_SAL')
    assert df.shape == (744, 1)


def test_fv_sediment_fractions():
    p = './tests/tmf/test_datasets/fv/FMA2_SED_003.fvsed'
    fvsed = FVSed(p)
    fractions = fvsed.sediment_fractions()
    assert fractions == ['fineSed', 'Gravel']


def test_fv_tracer_count():
    p = './tests/tmf/test_datasets/fv/CST006_2D_010.fvc'
    fvc = FVC(p)
    ntracer = fvc.tracer_count()
    assert ntracer == 1


def test_fv_wq_constiutents_sim_class_DO():
    p = './tests/tmf/test_datasets/fv/wq/wqm/WQ_000.fvwq'
    fvwq = FVWQ(p)
    constituents = fvwq.wq_constituents()
    assert constituents == ['DO']


def test_fv_wq_constiutents_sim_class_inorganics():
    p = './tests/tmf/test_datasets/fv/wq/wqm/WQ_001.fvwq'
    fvwq = FVWQ(p)
    constituents = fvwq.wq_constituents()
    assert constituents == ['DO', 'Si', 'Amm', 'Nit', 'FRP', 'FRPads', 'PHYTO_green']


def test_fv_wq_constiutents_sim_class_organics():
    p = './tests/tmf/test_datasets/fv/wq/wqm/WQ_002.fvwq'
    fvwq = FVWQ(p)
    constituents = fvwq.wq_constituents()
    assert constituents == ['DO', 'Si', 'Amm', 'Nit', 'FRP', 'FRPads', 'DOC', 'POC', 'DON', 'PON', 'DOP', 'POP', 'RDOC', 'RDON', 'RDOP', 'RPOM', 'PHYTO_green']


def test_fv_fma2_sed_001_to_bc_dbase():
    p = './tests/tmf/test_datasets/fv/bc/FMA2_SED_001.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (8, 7)

    q_1 = bc_dbase.value('1')
    assert q_1.shape == (73, 1)
    assert (q_1['Main_Inflow'] == 250).all()
    q_1_sed = bc_dbase.value('1_SED1')
    assert q_1_sed.shape == (73, 1)
    assert q_1_sed[q_1_sed['fineSed'] == 500].shape == (11, 1)

    wl_2 = bc_dbase.value('2')
    assert wl_2.shape == (745, 1)
    wl_2_sed = bc_dbase.value('2_SED1') 
    assert wl_2.shape == (745, 1)
    assert wl_2_sed['SED_1'].isna().all()

    q_3 = bc_dbase.value('3')
    assert q_3.shape == (73, 1)
    assert (q_3['Tributary_Inflow'] == 50).all()
    q_3_sed = bc_dbase.value('3_SED1')
    assert q_3_sed.shape == (73, 1)
    assert q_3_sed['SED_1'].isna().all()

    wl_4 = bc_dbase.value('4')
    assert (wl_4 == wl_2).iloc[:,0].all()
    wl_4_sed = bc_dbase.value('4_SED1')
    assert wl_4.shape == (745, 1)
    assert wl_4_sed['SED_1'].isna().all()


def test_bc_qc():
    p = './tests/tmf/test_datasets/fv/bc/bc_qc.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('1')
    assert df.shape == (73, 1)
    assert not bc_dbase.is_piecewise_constant('1')


def test_bc_qc_poly():
    p = './tests/tmf/test_datasets/fv/bc/bc_qc_poly.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('1')
    assert df.shape == (73, 1)


def test_bc_qg():
    p = './tests/tmf/test_datasets/fv/bc/bc_qg.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('qg')
    assert df.shape == (73, 1)


def test_bc_qcm():
    p = './tests/tmf/test_datasets/fv/bc/bc_qcm.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('qcm_1')
    assert df.shape == (7, 3)


def test_bc_hq():
    p = './tests/tmf/test_datasets/fv/bc/bc_hq.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('Downstream')
    assert df.shape == (102, 1)


def test_bc_wls():
    p = './tests/tmf/test_datasets/fv/bc/bc_wls.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('2')
    assert df.shape == (744, 2)


def test_bc_wl_curt():
    p = './tests/tmf/test_datasets/fv/bc/bc_wl_curt.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    assert bc_dbase.df.loc['Eastern_Boundary', 'Column 2'] == 'nsEastern_Boundary_wl'
    with pytest.raises(NotImplementedError):
        df = bc_dbase.value('Eastern_Boundary')


def test_bc_qc_grid():
    p = './tests/tmf/test_datasets/fv/bc/bc_qc_grid.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    assert bc_dbase.df.loc['diffuser_grid', 'Column 2'] == 'flow'
    with pytest.raises(NotImplementedError):
        df = bc_dbase.value('diffuser_grid')


def test_bc_qn():
    p = './tests/tmf/test_datasets/fv/bc/bc_qn.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    val = bc_dbase.value('Downstream')
    assert val == 0.01


def test_bc_w10():
    p = './tests/tmf/test_datasets/fv/bc/bc_w10.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('W10')
    assert df.shape == (372, 2)
    assert bc_dbase.is_piecewise_constant('W10')


def test_bc_wl_with_events():
    p = './tests/tmf/test_datasets/fv/bc/bc_wl_events.fvc'
    fvc = FVC(p)

    bc_dbase = fvc.bc_dbase()
    with pytest.raises(ValueError):
        df = bc_dbase.value('2')

    bc_dbase = fvc.bc_dbase().context('-e1 TEST_WL_EVENT')
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('2')
    assert df.shape == (744, 1)


def test_bc_w10_with_events():
    p = './tests/tmf/test_datasets/fv/bc/bc_w10_events.fvc'
    fvc = FVC(p)

    bc_dbase = fvc.bc_dbase()
    with pytest.raises(ValueError):
        df = bc_dbase.value('W10')

    bc_dbase = fvc.bc_dbase().context('-e1 TEST_WIND_EVENT')
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('W10')
    assert df.shape == (372, 2)
    assert bc_dbase.is_piecewise_constant('W10')


def test_bc_wl_with_scenarios():
    p = './tests/tmf/test_datasets/fv/bc/bc_wl_scenarios.fvc'
    fvc = FVC(p)

    bc_dbase = fvc.bc_dbase()
    with pytest.raises(ValueError):
        df = bc_dbase.value('2')

    bc_dbase = fvc.context('-s1 SCENA').bc_dbase()
    assert isinstance(bc_dbase, RunState)
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('2')
    assert df.shape == (744, 1)
    assert df.columns[0] == 'tidelevel_m'

    bc_dbase = fvc.bc_dbase().context('-s1 SCENA')
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('2')
    assert df.shape == (744, 1)
    assert df.columns[0] == 'tidelevel_m'

def test_bc_w10_with_scenarios():
    p = './tests/tmf/test_datasets/fv/bc/bc_w10_scenarios.fvc'
    fvc = FVC(p)

    bc_dbase = fvc.bc_dbase()
    with pytest.raises(ValueError):
        df = bc_dbase.value('W10')

    bc_dbase = fvc.context('-s1 SCENB').bc_dbase()
    assert isinstance(bc_dbase, RunState)
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('W10')
    assert df.shape == (372, 2)
    assert df.columns[0] == 'WIND_X'
    assert df.columns[1] == 'WIND_Y'

    bc_dbase = fvc.bc_dbase().context('-s1 SCENB')
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('W10')
    assert df.shape == (372, 2)
    assert df.columns[0] == 'WIND_X'
    assert df.columns[1] == 'WIND_Y'


def test_fv_grid_definition_file():
    p = './tests/tmf/test_datasets/fv/bc/bc_qc_grid.fvc'
    fvc = FVC(p)
    inp = fvc.find_input('grid definition file')

    assert len(inp) == 1

    inp = inp[0]
    assert isinstance(inp, GridDefinitionFileBlockInput)
    assert inp.files[0] == Path('./tests/tmf/test_datasets/fv/bc/example_diffuser.nc')


def test_bc_precip():
    p = './tests/tmf/test_datasets/fv/bc/bc_precip.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('PRECIP')
    assert df.shape == (41, 1)
    assert bc_dbase.is_piecewise_constant('PRECIP')


def test_bc_atmos_grids():
    p = './tests/tmf/test_datasets/fv/bc/bc_atmos_grids.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (7, 7)

    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('ncep_SW_RAD')
    
    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('ncep_LW_RAD')

    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('ncep_W10')

    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('ncep_AIR_TEMP')

    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('ncep_PRECIP')

    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('rhumgrid_REL_HUM')

    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('mslpgrid_MSLP')


def test_bc_cyc_holland():
    p = './tests/tmf/test_datasets/fv/bc/bc_cyc_holland.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('CYC_HOLLAND')
    assert df.shape == (2, 12)


def test_bc_wave_coupled():
    p = './tests/tmf/test_datasets/fv/bc/bc_wave_coupled.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)

    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('WAVE_COUPLED')


def test_bc_force():
    p = './tests/tmf/test_datasets/fv/bc/bc_force.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('Pipe_Outlet_001')
    assert df.shape == (2, 2)


def test_bc_force_poly():
    p = './tests/tmf/test_datasets/fv/bc/bc_force_poly.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('Inflow_Region_001')
    assert df.shape == (2, 2)


def test_bc_forcem():
    p = './tests/tmf/test_datasets/fv/bc/bc_forcem.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('FORCEM_1')
    assert df.shape == (24, 4)


def test_bc_zg():
    p = './tests/tmf/test_datasets/fv/bc/bc_zg.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    assert not bc_dbase.df.loc['Eastern_Boundary', :].empty
    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('Eastern_Boundary')


def test_bc_wl_subtype_5():
    p = './tests/tmf/test_datasets/fv/bc/bc_wl_subtype_5.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('2')
    assert df.shape == (6, 1)
    assert df['tidelevel_m'].max() > 5


def test_bc_atmos():
    p = './tests/tmf/test_datasets/fv/bc/bc_atmos.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (5, 7)

    df = bc_dbase.value('W10')
    assert df.shape == (2184, 2)

    df = bc_dbase.value('LW_RAD')
    assert df.shape == (2184, 1)

    df = bc_dbase.value('SW_RAD')
    assert df.shape == (2184, 1)

    df = bc_dbase.value('AIR_TEMP')
    assert df.shape == (2184, 1)

    df = bc_dbase.value('REL_HUM')
    assert df.shape == (2184, 1)


def test_bc_fc():
    p = './tests/tmf/test_datasets/fv/bc/bc_fc.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (3, 7)

    df = bc_dbase.value('Outfall_001_SAL')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Outfall_001_TEMP')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Outfall_001_TRACE1')
    assert df.shape == (2, 1)


def test_bc_fc_poly():
    p = './tests/tmf/test_datasets/fv/bc/bc_fc_poly.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (3, 7)

    df = bc_dbase.value('Inflow_Region_001_SAL')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Region_001_TEMP')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Region_001_TRACE1')
    assert df.shape == (2, 1)
    

def test_bc_fcm():
    p = './tests/tmf/test_datasets/fv/bc/bc_fcm.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (3, 7)

    df = bc_dbase.value('FCM_1_SAL')
    assert df.shape == (24, 3)

    df = bc_dbase.value('FCM_1_TEMP')
    assert df.shape == (24, 3)

    df = bc_dbase.value('FCM_1_TRACE1')
    assert df.shape == (24, 3)


def test_bc_fc_grid():
    p = './tests/tmf/test_datasets/fv/bc/bc_fc_grid.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (3, 7)

    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('diffuser_grid_SAL')

    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('diffuser_grid_TEMP')

    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('diffuser_grid_TRACE1')


def test_bc_fc_scalar():
    p = './tests/tmf/test_datasets/fv/bc/bc_scalar.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (4, 7)

    df = bc_dbase.value('Eastern_Boundary_SAL')
    assert df.shape == (9031, 1)
    assert bc_dbase.is_piecewise_constant('Eastern_Boundary_SAL')

    df = bc_dbase.value('Western_Boundary_SAL')
    assert df.shape == (9031, 1)
    assert bc_dbase.is_piecewise_constant('Western_Boundary_SAL')


def test_bc_cp():
    p = './tests/tmf/test_datasets/fv/bc/bc_cp.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (20, 7)

    df = bc_dbase.value('Inflow_Point_001_SAL')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Point_001_TEMP')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Point_001_TRACE1')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Point_002_SAL')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Point_002_TEMP')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Point_002_TRACE1')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Point_003_SAL')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Point_003_TEMP')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Point_003_TRACE1')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Point_004_SAL')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Point_004_TEMP')
    assert df.shape == (2, 1)

    df = bc_dbase.value('Inflow_Point_004_TRACE1')
    assert df.shape == (2, 1)


def test_bc_transport():
    p = './tests/tmf/test_datasets/fv/bc/bc_transport.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)

    with pytest.raises(NotImplementedError):
        _ = bc_dbase.value('TRANSPORT')


def test_bc_fb():
    p = './tests/tmf/test_datasets/fv/bc/bc_fb.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('DredgeHead1_SED1')
    assert df.shape == (577, 1)


def test_bc_fbm():
    p = './tests/tmf/test_datasets/fv/bc/bc_fbm.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.df.shape == (1, 7)
    df = bc_dbase.value('FBM_1_SED1')
    assert df.shape == (577, 3)


def test_mat_2d_hd():
    p = './tests/tmf/test_datasets/fv/mat/mat_2d_hd.fvc'
    fvc = FVC(p)
    mat = fvc.mat_file()
    assert mat.df.shape == (2, 5)
    assert mat.value(1) == 0.05
    assert mat.df.loc['DEFAULT', 'Horiz Visc'] == 0.5


def test_mat_2d_hd_include_file():
    p = './tests/tmf/test_datasets/fv/mat/mat_2d_hd_include_file.fvc'
    fvc = FVC(p)
    mat = fvc.mat_file()
    assert mat.df.shape == (6, 5)
    assert mat.value(1) == 0.04
    assert mat.value(2) == 0.02
    assert mat.value(3) == 0.1
    assert mat.value(4) == 0.03
    assert mat.value(10) == 0.08


def test_mat_3d_with_ad():
    p = './tests/tmf/test_datasets/fv/mat/mat_3d_with_ad.fvc'
    fvc = FVC(p)
    mat = fvc.mat_file()
    assert mat.df.shape == (4, 10)
    assert mat.value(1) == 0.02
    assert mat.value(2) == 0.75
    assert mat.value(3) == 1.3


def test_mat_2d_with_st():
    p = './tests/tmf/test_datasets/fv/mat/mat_2d_with_st.fvc'
    fvc = FVC(p)
    mat = fvc.mat_file()
    assert mat.df.shape == (10, 7)
    assert mat.value(1) == 0.02
    assert mat.value(2) == 0.04
    assert mat.value(3) == 0.05
    assert mat.value(4) == 0.05
    assert mat.value(5) == 0.07
    assert mat.value(6) == 0.07
    assert mat.value(7) == 0.07
    assert mat.value(8) == 0.1
    assert mat.value(9) == 0.2
    assert mat.df.loc['DEFAULT', 'Sed Nlayer'] == 1


def test_mat_3d_with_wq():
    p = './tests/tmf/test_datasets/fv/mat/mat_3d_with_wq.fvc'
    fvc = FVC(p)
    mat = fvc.mat_file()
    assert mat.df.shape == (5, 20)
    assert mat.value(1) == 0.04
    assert mat.value(2) == 0.05
    assert mat.value(3) == 0.02
    assert mat.value(4) == 0.02

    assert mat.df.loc[1, 'Sed Nlayer'] == 1
    assert mat.df.loc[2, 'Sed Nlayer'] == 1
    assert mat.df.loc[3, 'Sed Nlayer'] == 1
    assert mat.df.loc[4, 'Sed Nlayer'] == 1

    assert mat.df.loc['DEFAULT', 'Oxygen Flux'] == -10.
    assert mat.df.loc[1, 'Oxygen Flux'] == -550.
    assert mat.df.loc[2, 'Oxygen Flux'] == 0.
    assert mat.df.loc[4, 'Oxygen Flux'] == -3500.


def test_add_mat_block_to_black_fvc():
    fvc = FVC()
    inp = fvc.append_input('Material == 1')
    assert inp.TUFLOW_TYPE == const.INPUT.BLOCK
    assert len(inp.cf) == 1


def test_add_bc_block_to_black_fvc():
    fvc = FVC()
    inp = fvc.append_input('BC == QN, Downstream, 0.01')
    assert inp.TUFLOW_TYPE == const.INPUT.BC_BLOCK
    assert len(inp.cf) == 1


def test_add_mat_block_to_existing_fvc():
    p = './tests/tmf/test_datasets/fv/basic_wq.fvc'
    fvc = FVC(p)
    inp = fvc.append_input('Material == 1')
    assert inp.TUFLOW_TYPE == const.INPUT.BLOCK
    assert len(inp.cf) == 1


def test_file_list():
    p = './tests/tmf/test_datasets/fv/wq/runs/WQ_000.fvc'
    fvc = FVC(p)

    def get_files(cf):
        files = []
        for inp in cf.find_input():
            files.extend(inp.files)
            if inp.trd:
                files.append(inp.trd)
            for cf_ in inp.cf:
                files.extend(get_files(cf_))
        return files

    model_files = set(get_files(fvc))
    assert len(model_files) == 18


def test_bc_dbase_file_list():
    p = './tests/tmf/test_datasets/fv/wq/runs/WQ_000.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    files = []
    for _, entry in bc_dbase.entries.items():
        files.extend(entry.files)
    model_files = set(files)
    assert len(model_files) == 9


def test_event_database():
    p = './tests/tmf/test_datasets/fv/events/FLD008_2D_~e1~_~e2~_005.fvc'
    fvc = FVC(p)
    event_db = fvc.event_database()
    assert event_db is not None
    assert len(event_db) == 4


def test_bc_is_plottable():
    p = './tests/tmf/test_datasets/fv/bc/bc_qc.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert bc_dbase.is_plottable('1')


def test_bc_is_not_plottable():
    p = './tests/tmf/test_datasets/fv/bc/bc_qn.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    assert not bc_dbase.is_plottable('Downstream')


def test_bc_include_file():
    p = './tests/tmf/test_datasets/fv/bc/bc_wl_include.fvc'
    fvc = FVC(p)
    bc_dbase = fvc.bc_dbase()
    df = bc_dbase.value('2')
    assert df.shape == (744, 1)
