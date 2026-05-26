from pathlib import Path

import pytest

from ...pytuflow._tmf.cf.cf_build_state import ControlFileBuildState
from ...pytuflow._tmf.scope import ScopeList, Scope
from ...pytuflow._tmf.context import Context
from ...pytuflow._tmf.inp.inp_run_state import InputRunState
from ...pytuflow._tmf.inp.gis import GisInputRunState
from ...pytuflow._tmf.inp.get_input_class import get_input_class
from ...pytuflow._tmf.settings import TCFConfig
from ...pytuflow._tmf.parsers.command import Command
from ...pytuflow._tmf.tfpathlib import TuflowPath


def test_input_ctx_init():
    config = TCFConfig()
    line = 'Tutorial Model == ON'
    command = Command(line, config)
    input = get_input_class(command)(None, command)
    ctx = Context()
    ctx = InputRunState(input, ctx, None)
    assert isinstance(ctx, InputRunState)
    assert repr(ctx) == '<SettingInputContext> Tutorial Model == ON'


def test_input_ctx_init_with_context_req():
    config = TCFConfig()
    line = 'SGS Approach == <<SGS_APPROACH>>'
    command = Command(line, config)
    input = get_input_class(command)(None, command)
    ctx = Context()
    ctx.load_variables({'SGS_APPROACH': 'Method C'})
    ctx = InputRunState(input, ctx, None)
    assert isinstance(ctx, InputRunState)
    assert ctx.rhs == 'Method C'


def test_input_ctx_init_with_files():
    line = 'Read File == Read_File_<<~s~>>.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'Read_File_EXG.trd').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'Read_File_DEV.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        input = get_input_class(command)(None, command)
        ctx = Context('-s DEV')
        ctx = InputRunState(input, ctx, None)
        assert ctx.files == [TuflowPath(__file__).parent / 'Read_File_DEV.trd']
        assert str(ctx) == 'Read File == Read_File_DEV.trd'
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'Read_File_EXG.trd').unlink()
        (Path(__file__).parent / 'Read_File_DEV.trd').unlink()


def test_input_ctx_init_gis_with_multi_file_line():
    line = 'Read GIS Z Shape == 2d_zsh_M01_001_L.shp | 2d_zsh_M01_001_P.shp'
    p = Path(__file__).parent / 'test_control_file.tgc'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / '2d_zsh_M01_001_L.shp').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / '2d_zsh_M01_001_P.shp').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        input = get_input_class(command)(None, command)
        ctx = Context('-s DEV')
        input_ctx = InputRunState(input, ctx, None)
        assert input_ctx.files == [TuflowPath(__file__).parent / '2d_zsh_M01_001_L.shp', TuflowPath(__file__).parent / '2d_zsh_M01_001_P.shp']
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / '2d_zsh_M01_001_L.shp').unlink()
        (Path(__file__).parent / '2d_zsh_M01_001_P.shp').unlink()


def test_input_ctx_init_gis_with_multi_file_line_column_index():
    line = 'Read GIS Mat == 3 | 2d_mat_M01_001_R.shp'
    p = Path(__file__).parent / 'test_control_file.tgc'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / '2d_mat_M01_001_R.shp').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        input = get_input_class(command)(None, command)
        ctx = Context('-s DEV')
        input_ctx = GisInputRunState(input, ctx, None)
        assert input_ctx.files == [TuflowPath(__file__).parent / '2d_mat_M01_001_R.shp']
        assert input_ctx.attr_idx == 3
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / '2d_mat_M01_001_R.shp').unlink()


def test_input_ctx_init_grid_with_multi_file_line():
    line = 'Read GRID Zpt == DEM_M01_1m.tif | 2d_polygon_clip.shp'
    p = Path(__file__).parent / 'test_control_file.tgc'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'DEM_M01_1m.tif').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / '2d_polygon_clip.shp').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        input = get_input_class(command)(None, command)
        ctx = Context('-s DEV')
        input_ctx = InputRunState(input, ctx, None)
        assert input_ctx.files == [Path(__file__).parent / 'DEM_M01_1m.tif', Path(__file__).parent / '2d_polygon_clip.shp']
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'DEM_M01_1m.tif').unlink()
        (Path(__file__).parent / '2d_polygon_clip.shp').unlink()


def test_input_ctx_init_tin_with_multi_file_line():
    line = 'Read GRID Zpt == tin_M01.12da | 2d_polygon_clip.shp'
    p = Path(__file__).parent / 'test_control_file.tgc'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'tin_M01.12da').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / '2d_polygon_clip.shp').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        input = get_input_class(command)(None, command)
        ctx = Context('-s DEV')
        input_ctx = InputRunState(input, ctx, None)
        assert input_ctx.files == [Path(__file__).parent / 'tin_M01.12da', Path(__file__).parent / '2d_polygon_clip.shp']
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'tin_M01.12da').unlink()
        (Path(__file__).parent / '2d_polygon_clip.shp').unlink()


def test_input_get_files_2():
    line = 'Read GIS Z Shape == 2d_zsh_brkline_<<~s1~>><<~s2~>>_001_P.shp | 2d_zsh_brkline_<<~s1~>><<~s2~>>_001_L.shp\n'
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write(line)
    file1 = Path(__file__).parent / '2d_zsh_brkline_scen15m_001_P.shp'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_scen15m_001_L.shp'
    with file2.open('w') as f:
        f.write('banana')
    file3 = Path(__file__).parent / '2d_zsh_brkline_scen25m_001_P.shp'
    with file3.open('w') as f:
        f.write('banana')
    file4 = Path(__file__).parent / '2d_zsh_brkline_scen25m_001_L.shp'
    with file4.open('w') as f:
        f.write('banana')
    file5 = Path(__file__).parent / '2d_zsh_brkline_scen22.5m_001_P.shp'
    with file5.open('w') as f:
        f.write('banana')
    file6 = Path(__file__).parent / '2d_zsh_brkline_scen22.5m_001_L.shp'
    with file6.open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(tcf)
        command = Command(line, config)
        input = get_input_class(command)(None, command)
        ctx = input.context('-s1 scen1 -s2 5m')
        files = ctx.files
        assert sorted(files) == sorted([file1, file2])
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


def test_input_get_files_grid():
    line = 'Read GRID Zpts == 2d_zsh_brkline_<<~s1~>><<~s2~>>_001_P.tif | 2d_zsh_brkline_<<~s1~>><<~s2~>>_001_L.shp\n'
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write(line)
    file1 = Path(__file__).parent / '2d_zsh_brkline_scen15m_001_P.tif'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_scen15m_001_L.shp'
    with file2.open('w') as f:
        f.write('banana')
    file3 = Path(__file__).parent / '2d_zsh_brkline_scen25m_001_P.tif'
    with file3.open('w') as f:
        f.write('banana')
    file4 = Path(__file__).parent / '2d_zsh_brkline_scen25m_001_L.shp'
    with file4.open('w') as f:
        f.write('banana')
    file5 = Path(__file__).parent / '2d_zsh_brkline_scen22.5m_001_P.tif'
    with file5.open('w') as f:
        f.write('banana')
    file6 = Path(__file__).parent / '2d_zsh_brkline_scen22.5m_001_L.shp'
    with file6.open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(tcf)
        command = Command(line, config)
        input = get_input_class(command)(None, command)
        ctx = input.context('-s1 scen2 -s2 2.5m')
        files = ctx.files
        assert sorted(files) == sorted([file5, file6])
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


def test_input_get_files_tin():
    line = 'Read TIN Zpts == 2d_zsh_brkline_<<~s1~>><<~s2~>>_001_P.12da | 2d_zsh_brkline_<<~s1~>><<~s2~>>_001_L.shp\n'
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write(line)
    file1 = Path(__file__).parent / '2d_zsh_brkline_scen15m_001_P.12da'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_scen15m_001_L.shp'
    with file2.open('w') as f:
        f.write('banana')
    file3 = Path(__file__).parent / '2d_zsh_brkline_scen25m_001_P.12da'
    with file3.open('w') as f:
        f.write('banana')
    file4 = Path(__file__).parent / '2d_zsh_brkline_scen25m_001_L.shp'
    with file4.open('w') as f:
        f.write('banana')
    file5 = Path(__file__).parent / '2d_zsh_brkline_scen22.5m_001_P.12da'
    with file5.open('w') as f:
        f.write('banana')
    file6 = Path(__file__).parent / '2d_zsh_brkline_scen22.5m_001_L.shp'
    with file6.open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(tcf)
        command = Command(line, config)
        input = get_input_class(command)(None, command)
        ctx = input.context('-s1 scen2 -s2 5m')
        files = ctx.files
        assert sorted(files) == sorted([file3, file4])
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


def test_input_files_ref_in_gis():
    line = 'Read GIS Network == test_datasets/1d_nwk_EG11_001_L.shp'
    ecf = Path(__file__).parent / 'test_control_file.ecf'
    file0 = Path(__file__).parent / 'test_datasets/1d_nwk_EG11_001_L.shp'
    file1 = Path(__file__).parent / 'matrix.csv'
    file2 = Path(__file__).parent / 'flow.csv'
    file3 = Path(__file__).parent / 'area.csv'
    file4 = Path(__file__).parent / 'q_flow.csv'
    file5 = Path(__file__).parent / 'scen1_matrix.csv'
    file6 = Path(__file__).parent / 'scen2_matrix.csv'
    with ecf.open('w') as f:
        f.write(line)
    with file1.open('w') as f:
        f.write('banana')
    with file2.open('w') as f:
        f.write('banana')
    with file3.open('w') as f:
        f.write('banana')
    with file4.open('w') as f:
        f.write('banana')
    with file5.open('w') as f:
        f.write('banana')
    with file6.open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(ecf)
        command = Command(line, config)
        input = get_input_class(command)(None, command)
        ctx = Context()
        ctx.load_variables({'var': 'scen1'})
        input_ctx = input.context(context=ctx)
        files = [x.resolve() for x in input_ctx.files]
        assert sorted(files) == sorted([file0, file1, file2, file3, file4, file5])
    except Exception as e:
        raise e
    finally:
        ecf.unlink()
        file1.unlink()
        file2.unlink()
        file3.unlink()
        file4.unlink()
        file5.unlink()
        file6.unlink()


def test_input_ctx_not_resolved_error():
    config = TCFConfig()
    line = 'Read TIN Zpts == <<~s1~>>_<<~s2~>>.12da'
    command = Command(line, config)
    input = get_input_class(command)(None, command)
    with pytest.raises(ValueError):
        input.context('-s1 DEM')


def test_input_get_files_setting_input():
    config = TCFConfig()
    line = 'Tutorial Model == ON'
    command = Command(line, config)
    input = get_input_class(command)(None, command)
    ctx = Context()
    ctx = input.context(context=ctx)
    assert ctx.files == []


def test_input_with_retained_scope():
    p = './tests/tmf/test_datasets/1d_domain_scope.tcf'
    tcf = ControlFileBuildState(p)
    inp = tcf.find_input('timestep')[0]
    inp_ = inp.context('s1 D01')
    assert inp_.scope == ScopeList([Scope('1D DOMAIN')])


def test_input_with_retained_scope_else():
    p = './tests/tmf/test_datasets/1d_domain_scope.tcf'
    tcf = ControlFileBuildState(p)
    inp = tcf.find_input('timestep')[1]
    inp_ = inp.context('s1 D02')
    assert inp_.scope == ScopeList([Scope('1D DOMAIN')])
