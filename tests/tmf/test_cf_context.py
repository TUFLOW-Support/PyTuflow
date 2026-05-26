from pathlib import Path
import sys

import pytest

from ...pytuflow._tmf.cf.cf_run_state import ControlFileRunState
from ...pytuflow._tmf.tfpathlib import TuflowPath
from ...pytuflow._tmf.cf.tcf import TCF


def test_cf_context_init_no_context():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead GIS == ../model/gis/projection.shp\nRead GRID == ../model/grid/grid.tif\n'
                'Read TIN == ../model/tin/tin.12da\nRead File == ../model/read_file.trd\n'
                'Read Materials File == ../model/materials.csv\nGeometry Control File == ../some_control_file.tgc\n')
    try:
        control_file = TCF(p)
        ctx = control_file.context()
        assert isinstance(ctx, ControlFileRunState)
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_cf_context_init_req_ctx():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead GIS == ../model/gis/projection.shp\nRead GRID == ../model/grid/grid.tif\n'
                'Read TIN == ../model/tin/tin.12da\nRead File == ../model/read_file.trd\n'
                'Read Materials File == ../model/materials.csv\n'
                'IF Scenario == DEV\n'
                '\tGeometry Control File == ../dev_control_file.tgc\n'
                'ELSE IF Scenario == DEV2\n'
                '\tGeometry Control File == ../dev2_control_file.tgc\n'
                'ELSE\n'
                '\tGeometry Control File == ../exg_control_file.tgc\n'
                'END IF\n')
    try:
        control_file = TCF(p)
        ctx = control_file.context('-s1 DEV')
        assert isinstance(ctx, ControlFileRunState)
        ctx = control_file.context('-s1 DEV2')
        assert str(ctx.find_input('geometry control file')[0]) == 'Geometry Control File == ../dev2_control_file.tgc'
        ctx = control_file.context('-s1 EXG')
        assert str(ctx.find_input('geometry control file')[0]) == 'Geometry Control File == ../exg_control_file.tgc'
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_cf_context_init_ctx_gis_files():
    p = Path(__file__).parent / 'test_control_file.tgc'
    with p.open('w') as f:
        f.write('Read GIS Z Shape == 2d_zsh_brkline_001_L.shp\nRead GRID Zpt== grid.tif\n')
    with (Path(__file__).parent / '2d_zsh_brkline_001_L.shp').open('w') as f:
        f.write('some data')
    with (Path(__file__).parent / 'grid.tif').open('w') as f:
        f.write('some data')
    try:
        control_file = TCF(p)
        ctx = control_file.context()
        assert [str(x) for x in ctx.find_input(lhs='read gis')] == ['Read GIS Z Shape == 2d_zsh_brkline_001_L.shp']
        assert [str(x) for x in ctx.find_input(lhs='read grid')] == ['Read GRID Zpt == grid.tif']
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / '2d_zsh_brkline_001_L.shp').unlink()
        (Path(__file__).parent / 'grid.tif').unlink()


def test_cf_context_resolve_variables():
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    trd = Path(__file__).parent / 'test_read_file.trd'
    tgc = Path(__file__).parent / 'test_control_file.tgc'
    with tcf.open('w') as f:
        f.write('Tutorial Model == ON\n')
        f.write('Geometry Control File == test_control_file.tgc\n')
        f.write('Read File == test_read_file.trd\n')
    with trd.open('w') as f:
        f.write('Set Variable CELL_SIZE == 1.0\n')
    with tgc.open('w') as f:
        f.write('Cell Size == <<CELL_SIZE>>\n')
        f.write('Set Code == 0\n')
    try:
        control_file = TCF(tcf)
        ctx = control_file.context()
        inp = ctx.tgc().find_input('cell size')[0]
        assert inp.value == 1.
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        trd.unlink()
        tgc.unlink()


def test_cf_context_resolve_variables_with_scope():
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    trd = Path(__file__).parent / 'test_read_file.trd'
    tgc = Path(__file__).parent / 'test_control_file.tgc'
    with tcf.open('w') as f:
        f.write('Tutorial Model == ON\n')
        f.write('Geometry Control File == test_control_file.tgc\n')
        f.write('Read File == test_read_file.trd\n')
    with trd.open('w') as f:
        f.write('If Scenario == 5m\n')
        f.write('\tSet Variable CELL_SIZE == 5\n')
        f.write('Else If Scenario == 10m\n')
        f.write('\tSet Variable CELL_SIZE == 10\n')
        f.write('End If\n')
    with tgc.open('w') as f:
        f.write('Cell Size == <<CELL_SIZE>>\n')
        f.write('Set Code == 0\n')
    try:
        control_file = TCF(tcf)
        ctx = control_file.context('-s 5m')
        assert ctx.tgc().find_input('cell size')[0].value == 5.
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        trd.unlink()
        tgc.unlink()


def test_cf_context_resolve_events():
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    tef = Path(__file__).parent / 'event_file.tef'
    bc_dbase = Path(__file__).parent / 'bc_dbase.csv'
    bndry = Path(__file__).parent / '100yr2hr_001.csv'
    with tcf.open('w') as f:
        f.write('Event File == event_file.tef\n')
        f.write('BC Database == bc_dbase.csv\n')
    with tef.open('w') as f:
        f.write('Define Event == Q100\n')
        f.write('\tBC Event Source == _event1_ | 100yr\n')
        f.write('End Define\n')
        f.write('Define Event == QPMF\n')
        f.write('\tBC Event Source == _event1_ | PMFyr\n')
        f.write('End Define\n')
        f.write('Define Event == 2hr\n')
        f.write('\tBC Event Source == _event2_ | 2hr\n')
        f.write('\tEnd Time == 3\n')
        f.write('End Define\n')
        f.write('Define Event == 4hr\n')
        f.write('\tBC Event Source == _event2_ | 4hr\n')
        f.write('\tEnd Time == 5\n')
        f.write('End Define\n')
        f.write('Define Event == TP01\n')
        f.write('\tBC Event Source == _TP_ | TP01\n')
        f.write('End Define\n')
    with bc_dbase.open('w') as f:
        f.write('Name,Source,Column 1,Column 2,Add Col 1,Mult Col 2,Add Col 2,Column 3,Column 4\n'
                'FC01,_event1__event2__001.csv,inflow_time_hr,inflow__TP_,,,,,')
    with bndry.open('w') as f:
        f.write(
            'inflow_time_hr,inflow_FC01\n0.000,0\n0.083,0.84\n0.167,3.31\n0.250,4.6\n0.333,7.03\n0.417,12.39\n0.500,22.63')
    try:
        control_file = TCF(tcf)
        ctx = control_file.context('-e1 Q100 -e2 2hr -e3 TP01')
        assert ctx.bc_dbase().df.loc['FC01'].tolist()[:3] == ['100yr2hr_001.csv', 'inflow_time_hr', 'inflow_TP01']
        assert ctx.bc_dbase()['fc01'].files[0].exists()
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        tef.unlink()
        bc_dbase.unlink()
        bndry.unlink()


def test_cf_context_resolve_if_or():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('IF Scenario == D01 | D02\n'
                '\tGeometry Control File == ../dev_control_file.tgc\n'
                'ELSE IF Scenario == D03\n'
                '\tGeometry Control File == ../100y_control_file.tgc\n'
                'ELSE\n'
                '\tGeometry Control File == ../exg_control_file.tgc\n'
                'END IF\n')
    try:
        control_file = TCF(p)
        ctx = control_file.context('-s D01')
        assert str(ctx.find_input('geometry control file')[0].cf[0]) == 'dev_control_file.tgc (not found)'
        ctx = control_file.context('-s D02')
        assert str(ctx.find_input('geometry control file')[0].cf[0]) == 'dev_control_file.tgc (not found)'
        ctx = control_file.context('-s D03')
        assert str(ctx.find_input('geometry control file')[0].cf[0]) == '100y_control_file.tgc (not found)'
        ctx = control_file.context('-s EXG')
        assert str(ctx.find_input('geometry control file')[0].cf[0]) == 'exg_control_file.tgc (not found)'
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_cf_context_get_files_if_block():
    line = 'Read GIS Z Shape == 2d_zsh_brkline_exg_001_P.shp | 2d_zsh_brkline_exg_001_L.shp\n' \
           'If Scenario == SCEN_1\n' \
           '\tRead GIS Z Shape == 2d_zsh_brkline_scen1_001_P.shp | 2d_zsh_brkline_scen1_001_L.shp\n' \
           'Else IF Scenario == SCEN_2\n' \
           '\tRead GIS Z Shape == 2d_zsh_brkline_scen2_001_P.shp | 2d_zsh_brkline_scen2_001_L.shp\n' \
           'Else\n' \
           '\tRead GIS Z Shape == 2d_zsh_brkline_scen3_001_P.shp | 2d_zsh_brkline_scen3_001_L.shp\n' \
           'End If\n'
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write(line)
    file1 = Path(__file__).parent / '2d_zsh_brkline_exg_001_P.shp'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_exg_001_L.shp'
    with file2.open('w') as f:
        f.write('banana')
    file3 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_P.shp'
    with file3.open('w') as f:
        f.write('banana')
    file4 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_L.shp'
    with file4.open('w') as f:
        f.write('banana')
    file5 = Path(__file__).parent / '2d_zsh_brkline_scen2_001_P.shp'
    with file5.open('w') as f:
        f.write('banana')
    file6 = Path(__file__).parent / '2d_zsh_brkline_scen2_001_L.shp'
    with file6.open('w') as f:
        f.write('banana')
    file7 = Path(__file__).parent / '2d_zsh_brkline_scen3_001_P.shp'
    with file7.open('w') as f:
        f.write('banana')
    file8 = Path(__file__).parent / '2d_zsh_brkline_scen3_001_L.shp'
    with file8.open('w') as f:
        f.write('banana')
    try:
        control_file = TCF(tcf)
        ctx = control_file.context('-s1 SCEN_1')
        inp = ctx.find_input()[0]
        _ = inp.files
        files = sum([x.files for x in ctx.find_input()], [])
        assert sorted(files) == sorted([file1, file2, file3, file4])
        ctx = control_file.context('-s1 SCEN_2')
        files = sum([x.files for x in ctx.find_input()], [])
        assert sorted(files) == sorted([file1, file2, file5, file6])
        ctx = control_file.context('-s1 SCEN_3')
        files = sum([x.files for x in ctx.find_input()], [])
        assert sorted(files) == sorted([file1, file2, file7, file8])
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        file1.unlink()
        file2.unlink()
        file3.unlink()
        file4.unlink()
        file5.unlink()
        file6.unlink()
        file7.unlink()
        file8.unlink()


def test_cf_context_get_files_if_block_variables():
    if sys.platform == 'linux':
        line = 'If Scenario == SCENARIO_1\n' \
            '\tSet Variable SCEN == scen1\n' \
            'Else IF Scenario == SCENARIO_2\n' \
            '\tSet Variable SCEN == scen2\n' \
            'Else\n' \
            '\tSet Variable SCEN == scen3\n' \
            'End If\n' \
            'Read GIS Z Shape == 2d_zsh_brkline_<<SCEN>>_001_P.shp | 2d_zsh_brkline_<<SCEN>>_001_L.shp\n'
    else:
        line = 'If Scenario == SCENARIO_1\n' \
            '\tSet Variable SCEN == SCEN1\n' \
            'Else IF Scenario == SCENARIO_2\n' \
            '\tSet Variable SCEN == SCEN2\n' \
            'Else\n' \
            '\tSet Variable SCEN == SCEN3\n' \
            'End If\n' \
            'Read GIS Z Shape == 2d_zsh_brkline_<<SCEN>>_001_P.shp | 2d_zsh_brkline_<<SCEN>>_001_L.shp\n'
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write(line)
    file1 = Path(__file__).parent / '2d_zsh_brkline_exg_001_P.shp'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_exg_001_L.shp'
    with file2.open('w') as f:
        f.write('banana')
    file3 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_P.shp'
    with file3.open('w') as f:
        f.write('banana')
    file4 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_L.shp'
    with file4.open('w') as f:
        f.write('banana')
    file5 = Path(__file__).parent / '2d_zsh_brkline_scen2_001_P.shp'
    with file5.open('w') as f:
        f.write('banana')
    file6 = Path(__file__).parent / '2d_zsh_brkline_scen2_001_L.shp'
    with file6.open('w') as f:
        f.write('banana')
    file7 = Path(__file__).parent / '2d_zsh_brkline_scen3_001_P.shp'
    with file7.open('w') as f:
        f.write('banana')
    file8 = Path(__file__).parent / '2d_zsh_brkline_scen3_001_L.shp'
    with file8.open('w') as f:
        f.write('banana')
    try:
        control_file = TCF(tcf)
        ctx = control_file.context('-s1 SCENARIO_1')
        files = sum([x.files for x in ctx.find_input()], [])
        assert sorted(files) == sorted([file3, file4])
        ctx = control_file.context('-s1 SCENARIO_2')
        files = sum([x.files for x in ctx.find_input()], [])
        assert sorted(files) == sorted([file5, file6])
        ctx = control_file.context('-s1 SCENARIO_3')
        files = sum([x.files for x in ctx.find_input()], [])
        assert sorted(files) == sorted([file7, file8])
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        file1.unlink()
        file2.unlink()
        file3.unlink()
        file4.unlink()
        file5.unlink()
        file6.unlink()
        file7.unlink()
        file8.unlink()


def test_cf_context_get_files_if_block_nested_variables():
    line = 'If Scenario == SCENARIO_1\n' \
        '\tSet Variable SCEN == scen1\n' \
        '\tIf Scenario == SCENARIO_1a\n' \
        '\t\tSet Variable SCEN_2 == scen1a\n' \
        '\tElse IF Scenario == SCENARIO_1b\n' \
        '\t\tSet Variable SCEN_2 == scen1b\n' \
        '\tElse\n' \
        '\t\tSet Variable SCEN_2 == scen1c\n' \
        '\tEnd If\n' \
        'Else IF Scenario == SCENARIO_2\n' \
        '\tSet Variable SCEN == scen2\n' \
        '\tIf Scenario == SCENARIO_2a\n' \
        '\t\tSet Variable SCEN_2 == scen2a\n' \
        '\tElse IF Scenario == SCENARIO_2b\n' \
        '\t\tSet Variable SCEN_2 == scen2b\n' \
        '\tElse\n' \
        '\t\tSet Variable SCEN_2 == scen2c\n' \
        '\tEnd If\n' \
        'Else\n' \
        '\tSet Variable SCEN == scen3\n' \
        '\tIf Scenario == SCENARIO_3a\n' \
        '\t\tSet Variable SCEN_2 == scen3a\n' \
        '\tElse IF Scenario == SCENARIO_3b\n' \
        '\t\tSet Variable SCEN_2 == scen3b\n' \
        '\tElse\n' \
        '\t\tSet Variable SCEN_2 == scen3c\n' \
        '\tEnd If\n' \
        'End If\n' \
        'Read GIS Z Shape == 2d_zsh_brkline_<<SCEN>>_001_P.shp | 2d_zsh_brkline_<<SCEN>>_001_L.shp\n' \
        'Read GIS Z Shape == 2d_zsh_brkline_<<SCEN_2>>_001_P.shp | 2d_zsh_brkline_<<SCEN_2>>_001_L.shp\n'

    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write(line)
    file1 = Path(__file__).parent / '2d_zsh_brkline_exg_001_P.shp'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_exg_001_L.shp'
    with file2.open('w') as f:
        f.write('banana')
    file3 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_P.shp'
    with file3.open('w') as f:
        f.write('banana')
    file4 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_L.shp'
    with file4.open('w') as f:
        f.write('banana')
    file5 = Path(__file__).parent / '2d_zsh_brkline_scen2_001_P.shp'
    with file5.open('w') as f:
        f.write('banana')
    file6 = Path(__file__).parent / '2d_zsh_brkline_scen2_001_L.shp'
    with file6.open('w') as f:
        f.write('banana')
    file7 = Path(__file__).parent / '2d_zsh_brkline_scen3_001_P.shp'
    with file7.open('w') as f:
        f.write('banana')
    file8 = Path(__file__).parent / '2d_zsh_brkline_scen3_001_L.shp'
    with file8.open('w') as f:
        f.write('banana')
    file9 = Path(__file__).parent / '2d_zsh_brkline_scen1a_001_P.shp'
    with file9.open('w') as f:
        f.write('banana')
    file10 = Path(__file__).parent / '2d_zsh_brkline_scen1a_001_L.shp'
    with file10.open('w') as f:
        f.write('banana')
    file11 = Path(__file__).parent / '2d_zsh_brkline_scen1b_001_P.shp'
    with file11.open('w') as f:
        f.write('banana')
    file12 = Path(__file__).parent / '2d_zsh_brkline_scen1b_001_L.shp'
    with file12.open('w') as f:
        f.write('banana')
    file13 = Path(__file__).parent / '2d_zsh_brkline_scen1c_001_P.shp'
    with file13.open('w') as f:
        f.write('banana')
    file14 = Path(__file__).parent / '2d_zsh_brkline_scen1c_001_L.shp'
    with file14.open('w') as f:
        f.write('banana')
    file15 = Path(__file__).parent / '2d_zsh_brkline_scen2a_001_P.shp'
    with file15.open('w') as f:
        f.write('banana')
    file16 = Path(__file__).parent / '2d_zsh_brkline_scen2a_001_L.shp'
    with file16.open('w') as f:
        f.write('banana')
    file17 = Path(__file__).parent / '2d_zsh_brkline_scen2b_001_P.shp'
    with file17.open('w') as f:
        f.write('banana')
    file18 = Path(__file__).parent / '2d_zsh_brkline_scen2b_001_L.shp'
    with file18.open('w') as f:
        f.write('banana')
    file19 = Path(__file__).parent / '2d_zsh_brkline_scen2c_001_P.shp'
    with file19.open('w') as f:
        f.write('banana')
    file20 = Path(__file__).parent / '2d_zsh_brkline_scen2c_001_L.shp'
    with file20.open('w') as f:
        f.write('banana')
    file21 = Path(__file__).parent / '2d_zsh_brkline_scen3a_001_P.shp'
    with file21.open('w') as f:
        f.write('banana')
    file22 = Path(__file__).parent / '2d_zsh_brkline_scen3a_001_L.shp'
    with file22.open('w') as f:
        f.write('banana')
    file23 = Path(__file__).parent / '2d_zsh_brkline_scen3b_001_P.shp'
    with file23.open('w') as f:
        f.write('banana')
    file24 = Path(__file__).parent / '2d_zsh_brkline_scen3b_001_L.shp'
    with file24.open('w') as f:
        f.write('banana')
    file25 = Path(__file__).parent / '2d_zsh_brkline_scen3c_001_P.shp'
    with file25.open('w') as f:
        f.write('banana')
    file26 = Path(__file__).parent / '2d_zsh_brkline_scen3c_001_L.shp'
    with file26.open('w') as f:
        f.write('banana')
    try:
        control_file = TCF(tcf)
        ctx = control_file.context('-s1 SCENARIO_1 -s2 SCENARIO_1b')
        files = sum([x.files for x in ctx.find_input()], [])
        assert sorted(files) == sorted([file3, file4, file11, file12])
        ctx = control_file.context('-s1 SCENARIO_3 -s2 SCENARIO_3c')
        files = sum([x.files for x in ctx.find_input()], [])
        assert sorted(files) == sorted([file7, file8, file25, file26])
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        file1.unlink()
        file2.unlink()
        file3.unlink()
        file4.unlink()
        file5.unlink()
        file6.unlink()
        file7.unlink()
        file8.unlink()
        file9.unlink()
        file10.unlink()
        file11.unlink()
        file12.unlink()
        file13.unlink()
        file14.unlink()
        file15.unlink()
        file16.unlink()
        file17.unlink()
        file18.unlink()
        file19.unlink()
        file20.unlink()
        file21.unlink()
        file22.unlink()
        file23.unlink()
        file24.unlink()
        file25.unlink()
        file26.unlink()


def test_context_str_repr():
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    cf = TCF(tcf)
    ctx = cf.context()
    assert str(ctx) == 'test_control_file.tcf (not found)'
    assert repr(ctx) == '<TCFContext> test_control_file.tcf (not found)'


def test_context_str_repr_empty():
    cf = TCF()
    ctx = cf.context()
    assert str(ctx) == 'Empty Control File'
    assert repr(ctx) == '<TCFContext> Empty Control File'


def test_context_str_repr_file_exists():
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write('banana')
    try:
        cf = TCF(tcf)
        ctx = cf.context()
        assert str(ctx) == 'test_control_file.tcf'
        assert repr(ctx) == '<TCFContext> test_control_file.tcf'
    except Exception as e:
        raise e
    finally:
        tcf.unlink()


def test_resolve_by_commands():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('IF Scenario == D01 | D02\n'
                '\tGeometry Control File == dev_control_file.tgc\n'
                'ELSE IF Scenario == D03\n'
                '\tGeometry Control File == 100y_control_file.tgc\n'
                'ELSE\n'
                '\tGeometry Control File == exg_control_file.tgc\n'
                'END IF\n'
                '\n'
                'Model Scenario == D01\n'
                'Model Events == Q100')
    try:
        control_file = TCF(p)
        ctx = control_file.context()
        assert ctx.tgc().fpath.name == 'dev_control_file.tgc'
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_pause():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('IF Scenario == D01 | D02\n'
                '\tGeometry Control File == dev_control_file.tgc\n'
                'ELSE IF Scenario == D03\n'
                '\tGeometry Control File == 100y_control_file.tgc\n'
                'ELSE\n'
                '\tPause == Should not be here\n'
                'END IF\n')
    try:
        with pytest.raises(ValueError):
            control_file = TCF(p)
            ctx = control_file.context('-s1 D04')
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_get_files():
    tcf = Path(__file__).parent / 'test.tcf'
    line = 'Geometry Control File == M01_5m_001.tgc'
    with tcf.open('w') as f:
        f.write(line)
    tgc = Path(__file__).parent / 'M01_5m_001.tgc'
    with tgc.open('w') as f:
        f.write('Read GIS Code == 2d_code_M01_001_R.shp')
    code = TuflowPath(__file__).parent / '2d_code_M01_001_R.shp'
    with code.open('w') as f:
        f.write('banana')
    try:
        cf = TCF(tcf)
        ctx = cf.context()
        files = sum([x.files for x in ctx.find_input()], [])
        assert files == [tgc, code]
        files = sum([x.files for x in ctx.find_input(recursive=False)], [])
        assert files == [tgc]
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        tgc.unlink()
        code.unlink()

def test_logic_inside_1d_domain_block():
    p = './tests/tmf/test_datasets/1d_domain_scope.tcf'
    tcf = TCF(p)
    tcf_ = tcf.context('-s1 D02')
    inps = tcf_.find_input('timestep')
    assert len(inps) == 1
    assert inps[0].value == 0.25


def test_logic_inside_1d_domain_block_2():
    p = './tests/tmf/test_datasets/1d_domain_scope_reversed.tcf'
    tcf = TCF(p)
    tcf_ = tcf.context('-s1 D02')
    inps = tcf_.find_input('timestep')
    assert len(inps) == 1
    assert inps[0].value == 0.25


def test_if_logic_redundant_scenario():
    p = Path(__file__).parent / 'test_datasets' / 'redundant_scenario_logic.tcf'
    tcf = TCF(p)
    inp1 = tcf.find_input('2d_zsh_D01')[0]
    inp2 = tcf.find_input('2d_zsh_D02')[0]
    inp3 = tcf.find_input('2d_zsh_EXG')[0]
    tcf_ctx = tcf.context('-s1 D02')
    inp1_ctx = tcf_ctx.input(inp1.uuid)
    assert inp1_ctx is not None
    with pytest.raises(KeyError):
        inp2_ctx = tcf_ctx.input(inp2.uuid)
    with pytest.raises(KeyError):
        inp3_ctx = tcf_ctx.input(inp3.uuid)


def test_variable_in_db_and_lyr():
    p = './tests/tmf/test_datasets/var_in_db_and_lyr.tcf'
    tcf = TCF(p)
    ctx = tcf.context('-s EG02')
    assert ctx.find_input('read gis po')[0].rhs == '2d_po_EG02_010a_L.gpkg >> 2d_po_EG02_010a_L'
