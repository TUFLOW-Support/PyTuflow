import sys
from pathlib import Path
import os

import pytest

from ...pytuflow._tmf import set_prefer_gdal
from ...pytuflow._tmf.inp.db import DatabaseInput
from ...pytuflow._tmf.inp.mat import MatDatabaseInput
from ...pytuflow._tmf.inp.file import FileInput
from ...pytuflow._tmf.inp.gis import GisInput
from ...pytuflow._tmf.inp.grid import GridInput
from ...pytuflow._tmf.inp.setting import SettingInput
from ...pytuflow._tmf.inp.tin import TinInput
from ...pytuflow._tmf.tfpathlib import TuflowPath
from ...pytuflow._tmf import const
from ...pytuflow._tmf.settings import TCFConfig
from ...pytuflow._tmf.parsers.command import Command
from ...pytuflow._tmf.parsers.block import DefineBlock
from ...pytuflow._tmf.inp.get_input_class import get_input_class
from ...pytuflow._tmf.scope import Scope, ScopeList
from ...pytuflow._tmf.cf.tcf import TCF


def test_input_init_blank():
    config = TCFConfig()
    line = ''
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.lhs == ''
    assert inp.rhs == ''
    assert inp.files == []


def test_input_init_setting():
    config = TCFConfig()
    line = 'Tutorial Model == ON'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert isinstance(inp, SettingInput)
    assert inp.lhs == 'Tutorial Model'
    assert inp.rhs == 'ON'
    assert repr(inp) == '<SettingInput> Tutorial Model == ON'
    assert inp.TUFLOW_TYPE == const.INPUT.SETTING


def test_input_init_gis():
    config = TCFConfig()
    line = 'Read GIS Z Shape == gis/2d_zsh_brkline_001_L.shp'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert isinstance(inp, GisInput)
    assert inp.lhs == 'Read GIS Z Shape'
    assert inp.rhs == 'gis/2d_zsh_brkline_001_L.shp'
    assert repr(inp) == '<GisInput> Read GIS Z Shape == gis/2d_zsh_brkline_001_L.shp'
    assert inp.TUFLOW_TYPE == const.INPUT.GIS


def test_input_init_grid():
    config = TCFConfig()
    line = 'Read GRID Zpts == grid/DEM_5m.tif'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert isinstance(inp, GridInput)
    assert inp.lhs == 'Read GRID Zpts'
    assert inp.rhs == 'grid/DEM_5m.tif'
    assert repr(inp) == '<GridInput> Read GRID Zpts == grid/DEM_5m.tif'
    assert inp.TUFLOW_TYPE == const.INPUT.GRID


def test_input_init_tin():
    config = TCFConfig()
    line = 'Read TIN Zpts == tin/survey.12da'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert isinstance(inp, TinInput)
    assert inp.lhs == 'Read TIN Zpts'
    assert inp.rhs == 'tin/survey.12da'
    assert repr(inp) == '<TinInput> Read TIN Zpts == tin/survey.12da'
    assert inp.TUFLOW_TYPE == const.INPUT.TIN


def test_input_init_database():
    config = TCFConfig()
    line = 'Read Material File == ../model/materials.csv'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert isinstance(inp, MatDatabaseInput)
    assert inp.lhs == 'Read Material File'
    assert inp.rhs == '../model/materials.csv'
    assert repr(inp) == '<MatDatabaseInput> Read Material File == ../model/materials.csv'
    assert inp.TUFLOW_TYPE == const.INPUT.DB_MAT


def test_input_init_file():
    config = TCFConfig()
    line = 'Read File == ../model/read_grids.trd'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert isinstance(inp, FileInput)
    assert inp.lhs == 'Read File'
    assert inp.rhs == '../model/read_grids.trd'
    assert repr(inp) == '<TuflowReadFileInput> Read File == ../model/read_grids.trd'
    assert inp.TUFLOW_TYPE == const.INPUT.TRD


def test_input_str_no_value():
    config = TCFConfig()
    line = 'Tutorial Model'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert str(inp) == 'Tutorial Model'


def test_input_float_tuple_value():
    config = TCFConfig()
    line = 'Model Origin (X,Y) == 0.0, 0.0'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.value == (0.0, 0.0)
    assert inp.rhs == '0.0, 0.0'


def test_input_str():
    config = TCFConfig()
    line = 'Tutorial Model == ON'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert str(inp) == 'Tutorial Model == ON'


def test_input_str_blank():
    config = TCFConfig()
    line = ''
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert str(inp) == ''


def test_input_is_start_block():
    config = TCFConfig()
    line = 'If Scenario == EXG'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.is_start_block() is True

    line = 'Tutorial Model == ON'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.is_start_block() is False


def test_input_is_end_block():
    config = TCFConfig()
    line = 'End If'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.is_end_block() is True

    line = 'Tutorial Model == ON'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.is_end_block() is False


def test_input_scope_global():
    config = TCFConfig()
    line = 'Tutorial Model == ON'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp._scope == [Scope('GLOBAL', '')]


def test_input_scope_scenario():
    config = TCFConfig()
    line = 'Tutorial Model == ON'
    command = Command(line, config)
    define_blocks = [DefineBlock('SCENARIO', 'EXG')]
    command.define_blocks = define_blocks
    inp = get_input_class(command)(None, command)
    assert inp._scope == [Scope('SCENARIO', 'EXG')]


def test_input_scope_scenario_else_replacement():
    config = TCFConfig()
    line = 'Tutorial Model == ON'
    command = Command(line, config)
    define_blocks = [DefineBlock('SCENARIO', 'EXG'), DefineBlock('SCENARIO (ELSE)', 'EXG')]
    command.define_blocks = define_blocks
    inp = get_input_class(command)(None, command)
    assert inp._scope == [Scope('SCENARIO', 'EXG')]


def test_input_scope_1d_domain():
    config = TCFConfig()
    line = 'Tutorial Model == ON'
    command = Command(line, config)
    define_blocks = [DefineBlock('1D DOMAIN', '')]
    command.define_blocks = define_blocks
    inp = get_input_class(command)(None, command)
    assert inp._scope == [Scope('GLOBAL', ''), Scope('1D DOMAIN', '')]


def test_input_scope_event():
    config = TCFConfig()
    line = 'BC Event Source == ARI | 100yr'
    command = Command(line, config)
    define_blocks = [DefineBlock('EVENT', '100yr')]
    command.define_blocks = define_blocks
    inp = get_input_class(command)(None, command)
    assert inp._scope == [Scope('EVENT', '100yr')]


def test_input_multi_file():
    line = 'Read File == scenario_<<~s1~>>_test.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'scenario_exg_test.trd').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'scenario_dev_test.trd').open('w') as f:
        f.write('pineapple')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([x.name for x in inp.files]) == sorted(['scenario_dev_test.trd', 'scenario_exg_test.trd'])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'scenario_exg_test.trd').unlink()
        (Path(__file__).parent / 'scenario_dev_test.trd').unlink()


def test_input_multi_gis_file_scenarios():
    line = 'Read GIS Z Shape == <<~s1~>>_zsh_brkline_001_L.shp'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'dev_zsh_brkline_001_L.shp').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').open('w') as f:
        f.write('pineapple')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([x.name for x in inp.files]) == sorted(['dev_zsh_brkline_001_L.shp', 'exg_zsh_brkline_001_L.shp'])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'dev_zsh_brkline_001_L.shp').unlink()
        (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').unlink()

def test_input_multi_gis_file_pipe():
    line = 'Read GIS Z Shape == exg_zsh_brkline_001_L.shp | exg_zsh_brkline_001_P.shp'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'exg_zsh_brkline_001_P.shp').open('w') as f:
        f.write('pineapple')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([x.name for x in inp.files]) == sorted(['exg_zsh_brkline_001_L.shp', 'exg_zsh_brkline_001_P.shp'])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').unlink()
        (Path(__file__).parent / 'exg_zsh_brkline_001_P.shp').unlink()

def test_input_multi_gis_file_pipe_scenarios():
    line = 'Read GIS Z Shape == exg_zsh_brkline_001_P.shp | <<~s1~>>_zsh_brkline_001_L.shp'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'exg_zsh_brkline_001_P.shp').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'dev_zsh_brkline_001_L.shp').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').open('w') as f:
        f.write('pineapple')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([x.name for x in inp.files]) == sorted(['exg_zsh_brkline_001_P.shp',
                                                 'dev_zsh_brkline_001_L.shp',
                                                 'exg_zsh_brkline_001_L.shp'])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'exg_zsh_brkline_001_P.shp').unlink()
        (Path(__file__).parent / 'dev_zsh_brkline_001_L.shp').unlink()
        (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').unlink()


def test_input_multi_gis_file_pipe_value():
    line = 'Read GIS Z Shape == 10 | exg_zsh_brkline_001_L.shp'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([x.name for x in inp.files]) == sorted(['exg_zsh_brkline_001_L.shp'])
        assert inp.attr_idx == 10
        assert inp.value == [10, Path(__file__).parent / 'exg_zsh_brkline_001_L.shp']
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').unlink()


def test_input_multi_grid_file_scenarios():
    line = 'Read Grid Zpts == <<~s1~>>_grid_001.tif'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'dev_grid_001.tif').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'exg_grid_001.tif').open('w') as f:
        f.write('pineapple')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([x.name for x in inp.files]) == sorted(['dev_grid_001.tif', 'exg_grid_001.tif'])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'dev_grid_001.tif').unlink()
        (Path(__file__).parent / 'exg_grid_001.tif').unlink()

def test_input_multi_grid_file_pipe():
    line = 'Read Grid Zpts == exg_grid_001.tif | polygon.shp'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'exg_grid_001.tif').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'polygon.shp').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([x.name for x in inp.files]) == sorted(['exg_grid_001.tif', 'polygon.shp'])
        assert inp.value == [Path(__file__).parent / 'exg_grid_001.tif', Path(__file__).parent / 'polygon.shp']
        assert inp.clip_layer.name == 'polygon.shp'
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'exg_grid_001.tif').unlink()
        (Path(__file__).parent / 'polygon.shp').unlink()

def test_input_multi_grid_file_pipe_scenario():
    line = 'Read Grid Zpts == exg_grid_001.tif | polygon_<<~s1~>>.shp'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'exg_grid_001.tif').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'polygon_exg.shp').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'polygon_dev.shp').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([x.name for x in inp.files]) == sorted(['exg_grid_001.tif',
                                                 'polygon_dev.shp',
                                                 'polygon_exg.shp'])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'exg_grid_001.tif').unlink()
        (Path(__file__).parent / 'polygon_exg.shp').unlink()
        (Path(__file__).parent / 'polygon_dev.shp').unlink()


def test_input_multi_tin_file_scenarios():
    line = 'Read Tin Zpts == <<~s1~>>_tin_001.12da'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'dev_tin_001.12da').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'exg_tin_001.12da').open('w') as f:
        f.write('pineapple')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([x.name for x in inp.files]) == sorted(['dev_tin_001.12da', 'exg_tin_001.12da'])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'dev_tin_001.12da').unlink()
        (Path(__file__).parent / 'exg_tin_001.12da').unlink()

def test_input_multi_tin_file_pipe():
    line = 'Read Tin Zpts == exg_tin_001.12da | polygon.shp'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'exg_tin_001.12da').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'polygon.shp').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([x.name for x in inp.files]) == sorted(['exg_tin_001.12da', 'polygon.shp'])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'exg_tin_001.12da').unlink()
        (Path(__file__).parent / 'polygon.shp').unlink()


def test_input_multi_tin_file_pipe_scenario():
    line = 'Read Tin Zpts == exg_tin_001.12da | polygon_<<~s1~>>.shp'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'exg_tin_001.12da').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'polygon_exg.shp').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'polygon_dev.shp').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([x.name for x in inp.files]) == sorted(['exg_tin_001.12da',
                                                 'polygon_dev.shp',
                                                 'polygon_exg.shp'])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'exg_tin_001.12da').unlink()
        (Path(__file__).parent / 'polygon_exg.shp').unlink()
        (Path(__file__).parent / 'polygon_dev.shp').unlink()


def test_input_file_scope_scenarios_simple():
    line = 'Read File == <<~s1~>>_001.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'test_001.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('SCENARIO', 'test')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'test_001.trd').unlink()


def test_input_file_scope_scenarios_simple_2():
    line = 'Read GIS Z Shape == <<~s1~>>_zsh_brkline_001_L.shp'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'dev_zsh_brkline_001_L.shp').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').open('w') as f:
        f.write('pineapple')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('SCENARIO', 'dev')], [Scope('SCENARIO', 'exg')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'dev_zsh_brkline_001_L.shp').unlink()
        (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').unlink()


def test_input_file_scope_scenarios_ambiguous():
    line = 'Read File == <<~s1~>><<~s2~>>_001.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'testexample_001.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('SCENARIO', '<<~s1~>>'), Scope('SCENARIO', '<<~s2~>>')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'testexample_001.trd').unlink()

def test_input_file_scope_scenarios_ambiguous_2():
    line = 'Read File == <<~s1~>><<~s2~>>_<<~s1~>>_001.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'testexample_test_001.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('SCENARIO', 'test'), Scope('SCENARIO', '<<~s2~>>')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'testexample_test_001.trd').unlink()

def test_input_file_scope_scenarios_ambiguous_3():
    line = 'Read File == <<~s1~>><<~s2~>>_<<~s2~>>_002.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'testexample_example_002.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('SCENARIO', '<<~s1~>>'), Scope('SCENARIO', 'example')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'testexample_example_002.trd').unlink()

def test_input_file_scope_scenarios_ambiguous_4():
    line = 'Read File == <<~s1~>>_<<~s1~>><<~s2~>>_002.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'test_testexample_002.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('SCENARIO', 'test'), Scope('SCENARIO', '<<~s2~>>')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'test_testexample_002.trd').unlink()

def test_input_file_scope_scenarios_ambiguous_5():
    line = 'Read File == <<~s2~>>_<<~s1~>><<~s2~>>_002.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'example_testexample_002.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('SCENARIO', 'example'), Scope('SCENARIO', '<<~s1~>>')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'example_testexample_002.trd').unlink()


def test_input_file_scope_scenarios_ambiguous_6():
    line = 'Read File == <<~s1~>><<~s2~>>_<<~s1~>><<~s2~>>_002.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'testexample_testexample_002.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('SCENARIO', '<<~s1~>>'), Scope('SCENARIO', '<<~s2~>>')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'testexample_testexample_002.trd').unlink()


def test_input_file_scope_scenario_no_file():
    line = 'Read File == <<~s1~>>_001.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('SCENARIO', '<<~s1~>>')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_input_file_scope_events_simple():
    line = 'Read File == <<~e1~>>_001.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'test_001.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('EVENT', 'test')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'test_001.trd').unlink()


def test_input_file_scope_events_simple_2():
    line = 'Read GIS Z Shape == <<~e1~>>_zsh_brkline_001_L.shp'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'dev_zsh_brkline_001_L.shp').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').open('w') as f:
        f.write('pineapple')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('EVENT', 'dev')], [Scope('EVENT', 'exg')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'dev_zsh_brkline_001_L.shp').unlink()
        (Path(__file__).parent / 'exg_zsh_brkline_001_L.shp').unlink()


def test_input_file_scope_events_ambiguous():
    line = 'Read File == <<~e1~>><<~e2~>>_001.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'testexample_001.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('EVENT', '<<~e1~>>'), Scope('EVENT', '<<~e2~>>')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'testexample_001.trd').unlink()

def test_input_file_scope_events_ambiguous_2():
    line = 'Read File == <<~e1~>><<~e2~>>_<<~e1~>>_001.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'testexample_test_001.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('EVENT', 'test'), Scope('EVENT', '<<~e2~>>')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'testexample_test_001.trd').unlink()

def test_input_file_scope_events_ambiguous_3():
    line = 'Read File == <<~e1~>><<~e2~>>_<<~e2~>>_002.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'testexample_example_002.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('EVENT', '<<~e1~>>'), Scope('EVENT', 'example')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'testexample_example_002.trd').unlink()

def test_input_file_scope_events_ambiguous_4():
    line = 'Read File == <<~e1~>>_<<~e1~>><<~e2~>>_002.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'test_testexample_002.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('EVENT', 'test'), Scope('EVENT', '<<~e2~>>')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'test_testexample_002.trd').unlink()

def test_input_file_scope_events_ambiguous_5():
    line = 'Read File == <<~e2~>>_<<~e1~>><<~e2~>>_002.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'example_testexample_002.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted([inp.file_scope(x) for x in inp.files]) == sorted([[Scope('EVENT', 'example'), Scope('EVENT', '<<~e1~>>')]])
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'example_testexample_002.trd').unlink()


def test_input_file_scope_event_no_file():
    line = 'Read File == <<~e1~>>_001.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert [inp.file_scope(x) for x in inp.files] == [[Scope('EVENT', '<<~e1~>>')]]
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_input_file_scope_variables_simple():
    line = 'Read File == <<CELL_SIZE>>_<<CELL_SIZE>>_001.trd'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / '10m_10m_001.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert [inp.file_scope(x) for x in inp.files] == [[Scope('VARIABLE', '<<CELL_SIZE>>')]]
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / '10m_10m_001.trd').unlink()


def test_input_resolve_scope():
    line = 'Read File == <<~s1~>><<~s2~>>_001.trd\n'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'testexample_001.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        scopes = [Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example')]
        inp.figure_out_file_scopes(scopes)
        assert [inp.file_scope(x) for x in inp.files] == [scopes]
    except Exception as e:
        raise e
    finally:
        while p.exists():
            # Ensure the test control file is deleted
            p.unlink()
        p = (Path(__file__).parent / 'testexample_001.trd')
        while p.exists():
            # Ensure the test file is deleted
            p.unlink()


def test_input_resolve_scope_known():
    line = 'Read File == <<~s1~>>_001.trd\n'
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write(line)
    with (Path(__file__).parent / 'test_001.trd').open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(p)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        scopes = [Scope('SCENARIO', 'test')]
        inp.figure_out_file_scopes(scopes)
        assert [inp.file_scope(x) for x in inp.files] == [[Scope('SCENARIO', 'test')]]
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'test_001.trd').unlink()


def test_input_get_files_basic():
    line = 'Read GIS Z Shape == 2d_zsh_brkline_scen1_001_P.shp\n'
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write(line)
    file = Path(__file__).parent / '2d_zsh_brkline_scen1_001_P.shp'
    with file.open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(tcf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        files = inp.files
        assert files == [file]
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        file.unlink()


def test_input_get_files_basic_2():
    line = 'Read GIS Z Shape == 2d_zsh_brkline_scen1_001_P.shp | 2d_zsh_brkline_scen1_001_L.shp\n'
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write(line)
    file1 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_P.shp'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_L.shp'
    with file2.open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(tcf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        files = inp.files
        assert files == [file1, file2]
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        file1.unlink()
        file2.unlink()


def test_input_get_files():
    line = 'Read GIS Z Shape == 2d_zsh_brkline_<<~s~>>_001_P.shp | 2d_zsh_brkline_<<~s~>>_001_L.shp\n'
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write(line)
    file1 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_P.shp'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_L.shp'
    with file2.open('w') as f:
        f.write('banana')
    file3 = Path(__file__).parent / '2d_zsh_brkline_scen2_001_P.shp'
    with file3.open('w') as f:
        f.write('banana')
    file4 = Path(__file__).parent / '2d_zsh_brkline_scen2_001_L.shp'
    with file4.open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(tcf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        files = inp.files
        assert sorted(files) == sorted([file1, file2, file3, file4])
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        file1.unlink()
        file2.unlink()
        file3.unlink()
        file4.unlink()


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
        inp = get_input_class(command)(None, command)
        files = inp.files
        assert sorted(files) == sorted([file1, file2, file3, file4, file5, file6])
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


def test_input_get_files_basic_grid():
    line = 'Read GRID Zpts == 2d_zsh_brkline_scen1_001_P.tif | 2d_zsh_brkline_scen1_001_R.shp\n'
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write(line)
    file1 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_P.tif'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_R.shp'
    with file2.open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(tcf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        files = inp.files
        assert sorted(files) == sorted([file1, file2])
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        file1.unlink()
        file2.unlink()


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
        inp = get_input_class(command)(None, command)
        files = inp.files
        assert sorted(files) == sorted([file1, file2, file3, file4, file5, file6])
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


def test_input_get_files_basic_tin():
    line = 'Read TIN Zpts == 2d_zsh_brkline_scen1_001_P.12da | 2d_zsh_brkline_scen1_001_R.shp\n'
    tcf = Path(__file__).parent / 'test_control_file.tcf'
    with tcf.open('w') as f:
        f.write(line)
    file1 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_P.12da'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_scen1_001_R.shp'
    with file2.open('w') as f:
        f.write('banana')
    try:
        config = TCFConfig(tcf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        files = inp.files
        assert sorted(files) == sorted([file1, file2])
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        file1.unlink()
        file2.unlink()


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
        inp = get_input_class(command)(None, command)
        files = inp.files
        assert sorted(files) == sorted([file1, file2, file3, file4, file5, file6])
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
        inp = get_input_class(command)(None, command)
        files = [x.resolve() for x in inp.files]
        assert sorted(files) == sorted([file0, file1, file2, file3, file4, file5, file6])
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


def test_input_file():
    config = TCFConfig()
    line = 'Is a file == file.txt'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert isinstance(inp, FileInput)
    assert inp.lhs == 'Is a file'
    assert inp.rhs == 'file.txt'
    assert repr(inp) == '<FileInput> Is a file == file.txt'


def test_input_path_no_control_file():
    config = TCFConfig()
    line = 'Is a file == file.txt'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.files == [TuflowPath('file.txt')]


def test_input_path_cf_exists_file_doesnt():
    cf = Path(__file__).parent / 'test_control_file.tcf'
    line = 'Is a file == file.txt'
    with cf.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(cf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert inp.files == [cf.parent / 'file.txt']
    except Exception as e:
        raise e
    finally:
        cf.unlink()


def test_input_path_no_control_file_gis():
    config = TCFConfig()
    line = 'Read GIS Code == 2d_code.shp'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.files == [TuflowPath('2d_code.shp')]


def test_input_path_no_control_file_gis_multi():
    config = TCFConfig()
    line = 'Read GIS Code == 2d_code.shp | 2d_trim.shp'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert sorted(inp.files) == sorted([TuflowPath('2d_code.shp'), TuflowPath('2d_trim.shp')])
    assert inp.attr_idx == 0


def test_input_path_no_control_file_gis_multi_with_value():
    config = TCFConfig()
    line = 'Read GIS Code == 5 | 2d_code.shp'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.files == [TuflowPath('2d_code.shp')]
    assert inp.value == [5, TuflowPath('2d_code.shp')]


def test_input_path_cf_exists_file_doesnt_gis():
    cf = TuflowPath(__file__).parent / 'test_control_file.tcf'
    line = 'Read GIS Code == 2d_code.shp'
    with cf.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(cf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert inp.files == [cf.parent / '2d_code.shp']
    except Exception as e:
        raise e
    finally:
        cf.unlink()


def test_input_path_cf_exists_file_doesnt_gis_multi():
    cf = TuflowPath(__file__).parent / 'test_control_file.tcf'
    line = 'Read GIS Code == 2d_code.shp | 2d_trim.shp'
    with cf.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(cf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted(inp.files) == sorted([cf.parent / '2d_code.shp', cf.parent / '2d_trim.shp'])
    except Exception as e:
        raise e
    finally:
        cf.unlink()


def test_input_path_cf_exists_file_doesnt_gis_multi_with_value():
    cf = Path(__file__).parent / 'test_control_file.tcf'
    line = 'Read GIS Code == 5 | 2d_code.shp'
    with cf.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(cf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert inp.files == [cf.parent / '2d_code.shp']
        assert inp.attr_idx == 5
    except Exception as e:
        raise e
    finally:
        cf.unlink()


def test_input_path_no_control_file_grid():
    config = TCFConfig()
    line = 'Read GRID Zpts == dem.tif'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.files == [TuflowPath('dem.tif')]


def test_input_path_no_control_file_grid_multi():
    config = TCFConfig()
    line = 'Read GRID Zpts == dem.tif | 2d_trim.shp'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert sorted(inp.files) == sorted([TuflowPath('dem.tif'), TuflowPath('2d_trim.shp')])


def test_input_path_no_control_file_grid_multi_with_value():
    config = TCFConfig()
    line = 'Read GRID Zpts == dem.tif | 5'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.files == [TuflowPath('dem.tif')]


def test_input_path_cf_exists_file_doesnt_grid():
    cf = Path(__file__).parent / 'test_control_file.tcf'
    line = 'Read GRID Zpts == dem.tif'
    with cf.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(cf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert inp.files == [cf.parent / 'dem.tif']
    except Exception as e:
        raise e
    finally:
        cf.unlink()


def test_input_path_cf_exists_file_doesnt_grid_multi():
    cf = Path(__file__).parent / 'test_control_file.tcf'
    line = 'Read GRID Zpts == dem.tif | 2d_trim.shp'
    with cf.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(cf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted(inp.files) == sorted([cf.parent / 'dem.tif', cf.parent / '2d_trim.shp'])
    except Exception as e:
        raise e
    finally:
        cf.unlink()


def test_input_path_cf_exists_file_doesnt_grid_multi_with_value():
    cf = Path(__file__).parent / 'test_control_file.tcf'
    line = 'Read GRID Zpts == dem.tif | 5'
    with cf.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(cf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert inp.files == [cf.parent / 'dem.tif']
    except Exception as e:
        raise e
    finally:
        cf.unlink()


def test_input_path_no_control_file_tin():
    config = TCFConfig()
    line = 'Read TIN Zpts == dem.12da'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.files == [TuflowPath('dem.12da')]


def test_input_path_no_control_file_tin_multi():
    config = TCFConfig()
    line = 'Read TIN Zpts == dem.12da | 2d_trim.shp'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert sorted(inp.files) == sorted([TuflowPath('dem.12da'), TuflowPath('2d_trim.shp')])


def test_input_path_no_control_file_tin_multi_with_value():
    config = TCFConfig()
    line = 'Read TIN Zpts == dem.12da | 5'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.files == [TuflowPath('dem.12da')]


def test_input_path_cf_exists_file_doesnt_tin():
    cf = Path(__file__).parent / 'test_control_file.tcf'
    line = 'Read TIN Zpts == dem.12da'
    with cf.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(cf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert inp.files == [cf.parent / 'dem.12da']
    except Exception as e:
        raise e
    finally:
        cf.unlink()


def test_input_path_cf_exists_file_doesnt_tin_multi():
    cf = Path(__file__).parent / 'test_control_file.tcf'
    line = 'Read TIN Zpts == dem.12da | 2d_trim.shp'
    with cf.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(cf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted(inp.files) == sorted([cf.parent / 'dem.12da', cf.parent / '2d_trim.shp'])
    except Exception as e:
        raise e
    finally:
        cf.unlink()


def test_input_path_cf_exists_file_doesnt_tin_multi_with_value():
    cf = Path(__file__).parent / 'test_control_file.tcf'
    line = 'Read TIN Zpts == dem.12da | 5'
    with cf.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(cf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert inp.files == [cf.parent / 'dem.12da']
    except Exception as e:
        raise e
    finally:
        cf.unlink()


def test_input_path_no_control_file_gis_conveyance():
    config = TCFConfig()
    line = 'Read GIS Zpts Modify Conveyance == shapefile.shp | 12.4 | grid.tif'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert sorted(inp.files) == sorted([TuflowPath('shapefile.shp'), TuflowPath('grid.tif')])


def test_input_path_control_file_gis_conveyance_2():
    cf = Path(__file__).parent / 'test_control_file.tcf'
    line = 'Read GIS Zpts Modify Conveyance == shapefile.shp | 12.4 | grid.tif'
    with cf.open('w') as f:
        f.write(line)
    try:
        config = TCFConfig(cf)
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        assert sorted(inp.files) == sorted([cf.parent / 'shapefile.shp', cf.parent / 'grid.tif'])
    except Exception as e:
        raise e
    finally:
        cf.unlink()


def test_input_path_variable_index():
    line = 'Read GIS Code == <<index>> | shapefile.shp'
    command = Command(line, TCFConfig())
    inp = get_input_class(command)(None, command)
    assert inp.files == [TuflowPath('shapefile.shp')]


def test_input_figure_out_file_scopes():
    cf = TuflowPath(__file__).parent / 'test_control_file.tcf'
    txt = Path(__file__).parent / 'test_file_testexample.txt'
    with txt.open('w') as f:
        f.write('banana')
    try:
        line = 'Read Text == test_file_<<~s1~>><<~s2~>>.txt'
        config = TCFConfig()
        config.control_file = cf
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        scope_list = ScopeList([Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example')])
        inp.figure_out_file_scopes(scope_list)
        inp._files_loaded = True  # FileInput is abstract, so we need to set this manually
        assert sorted(inp.file_scope(inp.files[0])) == sorted([x for x in scope_list])
    except Exception as e:
        raise e
    finally:
        txt.unlink()


def test_input_figure_out_file_scopes_gis():
    cf = TuflowPath(__file__).parent / 'test_control_file.tcf'
    txt = Path(__file__).parent / '2d_zsh_brkline_testexample_001_P.shp'
    with txt.open('w') as f:
        f.write('banana')
    try:
        line = 'Read GIS Z Shape == 2d_zsh_brkline_<<~s1~>><<~s2~>>_001_P.shp'
        config = TCFConfig()
        config.control_file = cf
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        scope_list = ScopeList([Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example')])
        inp.figure_out_file_scopes(scope_list)
        assert sorted(inp.file_scope(inp.files[0])) == sorted([x for x in scope_list])
    except Exception as e:
        raise e
    finally:
        txt.unlink()


def test_input_figure_out_file_scopes_grid():
    cf = TuflowPath(__file__).parent / 'test_control_file.tcf'
    txt = Path(__file__).parent / 'DEM_testexample.asc'
    with txt.open('w') as f:
        f.write('banana')
    try:
        line = 'Read GRID Zpts == DEM_<<~s1~>><<~s2~>>.asc'
        config = TCFConfig()
        config.control_file = cf
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        scope_list = ScopeList([Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example')])
        inp.figure_out_file_scopes(scope_list)
        assert sorted(inp.file_scope(inp.files[0])) == sorted([x for x in scope_list])
    except Exception as e:
        raise e
    finally:
        txt.unlink()


def test_input_figure_out_file_scopes_tin():
    cf = TuflowPath(__file__).parent / 'test_control_file.tcf'
    txt = Path(__file__).parent / 'DEM_testexample.12da'
    with txt.open('w') as f:
        f.write('banana')
    try:
        line = 'Read TIN Zpts == DEM_<<~s1~>><<~s2~>>.12da'
        config = TCFConfig()
        config.control_file = cf
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        scope_list = ScopeList([Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example')])
        inp.figure_out_file_scopes(scope_list)
        assert sorted(inp.file_scope(inp.files[0])) == sorted([x for x in scope_list])
    except Exception as e:
        raise e
    finally:
        txt.unlink()


def test_input_figure_out_file_scopes_gis_multi():
    cf = TuflowPath(__file__).parent / 'test_control_file.tcf'
    file1 = Path(__file__).parent / '2d_zsh_brkline_testexample_001_P.shp'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_helloexample_001_R.shp'
    with file2.open('w') as f:
        f.write('banana')
    try:
        line = 'Read GIS Z Shape == 2d_zsh_brkline_<<~s1~>><<~s2~>>_001_P.shp | 2d_zsh_brkline_<<~s3~>><<~s2~>>_001_R.shp'
        config = TCFConfig()
        config.control_file = cf
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        scope_list = ScopeList([Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example'), Scope('SCENARIO', 'hello')])
        inp.figure_out_file_scopes(scope_list)
        assert sorted(inp.file_scope(inp.files[0])) == sorted([x for x in scope_list[:2]])
        assert sorted(inp.file_scope(inp.files[1])) == sorted([x for x in scope_list[1:]])
    except Exception as e:
        raise e
    finally:
        file1.unlink()
        file2.unlink()


def test_input_figure_out_file_scopes_gis_multi_2():
    cf = TuflowPath(__file__).parent / 'test_control_file.tcf'
    file1 = Path(__file__).parent / '2d_zsh_brkline_testexample_001_P.shp'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_helloexample_001_R.shp'
    with file2.open('w') as f:
        f.write('banana')
    try:
        line = 'Read GIS Z Shape == <<cell_size>> | 2d_zsh_brkline_<<~s1~>><<~s2~>>_001_P.shp'
        config = TCFConfig()
        config.control_file = cf
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        scope_list = ScopeList([Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example')])
        inp.figure_out_file_scopes(scope_list)
        assert sorted(inp.file_scope(inp.files[0])) == sorted([x for x in scope_list[:2]])
    except Exception as e:
        raise e
    finally:
        file1.unlink()
        file2.unlink()


def test_input_figure_out_file_scopes_grid_multi():
    cf = TuflowPath(__file__).parent / 'test_control_file.tcf'
    file1 = Path(__file__).parent / 'DEM_testexample.asc'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_helloexample_001_R.shp'
    with file2.open('w') as f:
        f.write('banana')
    try:
        line = 'Read GRID Zpts == DEM_<<~s1~>><<~s2~>>.asc | 2d_zsh_brkline_<<~s3~>><<~s2~>>_001_R.shp'
        config = TCFConfig()
        config.control_file = cf
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        scope_list = ScopeList([Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example'), Scope('SCENARIO', 'hello')])
        inp.figure_out_file_scopes(scope_list)
        assert sorted(inp.file_scope(inp.files[0])) == sorted([x for x in scope_list[:2]])
        assert sorted(inp.file_scope(inp.files[1])) == sorted([x for x in scope_list[1:]])
    except Exception as e:
        raise e
    finally:
        file1.unlink()
        file2.unlink()


def test_input_figure_out_file_scopes_tin_multi():
    cf = TuflowPath(__file__).parent / 'test_control_file.tcf'
    file1 = Path(__file__).parent / 'DEM_testexample.12da'
    with file1.open('w') as f:
        f.write('banana')
    file2 = Path(__file__).parent / '2d_zsh_brkline_helloexample_001_R.shp'
    with file2.open('w') as f:
        f.write('banana')
    try:
        line = 'Read TIN Zpts == DEM_<<~s1~>><<~s2~>>.12da | 2d_zsh_brkline_<<~s3~>><<~s2~>>_001_R.shp'
        config = TCFConfig()
        config.control_file = cf
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
        scope_list = ScopeList([Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example'), Scope('SCENARIO', 'hello')])
        inp.figure_out_file_scopes(scope_list)
        assert sorted(inp.file_scope(inp.files[0])) == sorted([x for x in scope_list[:2]])
        assert sorted(inp.file_scope(inp.files[1])) == sorted([x for x in scope_list[1:]])
    except Exception as e:
        raise e
    finally:
        file1.unlink()
        file2.unlink()


def test_input_feat_iter_not_exist_error():
    line = 'Read GIS Network == test_datasets/1d_nwk_EG11_001_L_not_exist.shp'
    config = TCFConfig()
    config.control_file = TuflowPath(__file__).parent / 'test_control_file.tcf'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)


def test_input_feat_iter_file_ogr_error():
    file = Path(__file__).parent / '1d_nwk_not_a_vector_file.shp'
    with file.open('w') as f:
        f.write('banana')
    line = 'Read GIS Network == 1d_nwk_not_a_vector_file.shp'
    try:
        config = TCFConfig()
        config.control_file = TuflowPath(__file__).parent / 'test_control_file.tcf'
        command = Command(line, config)
        inp = get_input_class(command)(None, command)
    except Exception as e:
        raise e
    finally:
        file.unlink()


def test_input_update_value():
    tcf = TCF()
    inp = tcf.append_input('Hardware == GPU    ! controls the hardware used for the simulation')
    inp.rhs = 'CPU'
    assert inp.rhs == 'CPU'
    assert inp.comment == '! controls the hardware used for the simulation'
    assert inp._command.original_text == 'Hardware == CPU    ! controls the hardware used for the simulation\n'
    assert inp.dirty


def test_input_update_map_output_format():
    tcf = TCF()
    inp = tcf.append_input('Map Output Format == XMDF TIF    ! output format')
    inp.rhs = 'NC HRNC'
    assert inp.rhs == 'NC HRNC'
    assert inp.comment == '! output format'
    assert inp._command.original_text == 'Map Output Format == NC HRNC    ! output format\n'
    assert inp.dirty


def test_input_update_file_no_cf():
    tcf = TCF()
    inp = tcf.append_input('Geometry Control File == geom_cf.tgc')
    inp.rhs = 'geom_cf2.tgc'
    assert inp.rhs == 'geom_cf2.tgc'
    assert inp.dirty


def test_input_update_file():
    tcf_ = Path(__file__).parent / 'test_001.tcf'
    tcf = TCF()
    tcf.path = TuflowPath(tcf_)
    inp = tcf.append_input('Geometry Control File == geom_cf.tgc  ! geometry control file')
    inp.rhs = 'geom_cf2.tgc'
    assert inp.rhs == 'geom_cf2.tgc'
    assert inp.comment == '! geometry control file'
    assert inp._command.original_text == 'Geometry Control File == geom_cf2.tgc  ! geometry control file\n'
    assert inp.dirty


def test_input_update_gis():
    tcf_ = Path(__file__).parent / 'test_001.tcf'
    tcf = TCF()
    tcf.fpath = TuflowPath(tcf_)
    inp = tcf.append_input(r'Read GIS PO == ..\model\gis\2d_po_001.shp   ! time series output object')
    if sys.platform == 'win32':
        new_path = r'..\model\gis\2d_po_002.shp'
    else:
        new_path = '../model/gis/2d_po_002.shp'
    inp.rhs = new_path
    assert inp.rhs == new_path
    assert inp.value.resolve() == (tcf.fpath.parent / inp.rhs).resolve()
    assert inp.comment == '! time series output object'
    if sys.platform == 'win32':
        assert inp._command.original_text == 'Read GIS PO == ..\\model\\gis\\2d_po_002.shp   ! time series output object\n'
    else:
        assert inp._command.original_text == 'Read GIS PO == ../model/gis/2d_po_002.shp   ! time series output object\n'
    assert inp.dirty


def test_input_update_gis_2():
    tcf_ = Path(__file__).parent / 'test_001.tcf'
    tcf = TCF()
    tcf.path = TuflowPath(tcf_)
    inp = tcf.append_input(r'Read GIS Z Shape == ..\model\gis\2d_zsh_001_L.shp   ! zshape modifier')
    new_path1 = r'..\model\gis\2d_zsh_002_L.shp'
    new_path2 = r'..\model\gis\2d_zsh_002_P.shp'
    inp.rhs = ' | '.join([new_path1, new_path2])
    assert inp.rhs == ' | '.join([new_path1, new_path2])
    assert inp.comment == '! zshape modifier'
    assert inp._command.original_text == 'Read GIS Z Shape == ' + ' | '.join([new_path1, new_path2]) + '   ! zshape modifier\n'
    assert inp.dirty


def test_input_number_log_folder():
    config = TCFConfig()
    line = 'Log Folder == 001'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.rhs == '001'


def test_input_number_log_folder_2():
    config = TCFConfig()
    line = r'Log Folder == log\001'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.rhs == r'log\001'


def test_input_number_log_folder_3():
    config = TCFConfig()
    config.variables = {'VERSION': '001'}
    line = r'Log Folder == log/<<VERSION>>'
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.rhs == r'log/<<VERSION>>'
    assert Path(inp.value) == Path(r'log/001')


def test_input_attrs():
    p = './tests/tmf/test_datasets/models/shp/runs/EG00_001.tcf'
    set_prefer_gdal(True)
    tcf = TCF(p)
    inp = tcf.find_input('Read Gis Z Shape')[0]
    assert inp.part_count == 2
    assert inp.geoms == ['LineString', 'Point']
    set_prefer_gdal(False)
    tcf = TCF(p)
    inp = tcf.find_input('Read Gis Z Shape')[0]
    assert inp.part_count == 2
    assert inp.geoms == ['LineString', 'Point']


def test_input_attrs_2():
    p = './tests/tmf/test_datasets/models/shp/runs/EG00_001.tcf'
    set_prefer_gdal(True)
    tcf = TCF(p)
    inp = tcf.find_input('Modify Conveyance')[0]
    assert inp.geoms == ['Polygon']
    assert inp.part_count == 3
    set_prefer_gdal(False)
    tcf = TCF(p)
    inp = tcf.find_input('Modify Conveyance')[0]
    assert inp.geoms == ['Polygon']
    assert inp.part_count == 3


def test_input_attrs_3():
    p = './tests/tmf/test_datasets/models/mif/runs/EG00_001.tcf'
    set_prefer_gdal(True)
    try:
        from osgeo import ogr
    except ImportError:
        return  # skip test if osgeo not available
    tcf = TCF(p)
    inp = tcf.find_input('Read Gis Z Shape')[0]
    assert inp.geoms == ['Point', 'LineString']
    assert inp.part_count == 1
    set_prefer_gdal(False)
    tcf = TCF(p)
    inp = tcf.find_input('Read Gis Z Shape')[0]
    assert inp.geoms == ['LineString', 'Point']
    assert inp.part_count == 1


def test_input_attrs_4():
    p = './tests/tmf/test_datasets/models/scenarios/runs/test_scenarios_in_fname.tcf'
    set_prefer_gdal(True)
    tcf = TCF(p)
    inp = tcf.find_input('Read Gis PO')[1]
    assert inp.geoms == ['Point']
    assert inp.part_count == 1
    set_prefer_gdal(False)
    tcf = TCF(p)
    inp = tcf.find_input('Read Gis PO')[1]
    assert inp.geoms == ['Point']
    assert inp.part_count == 1


def test_input_attrs_5():
    p = './tests/tmf/test_datasets/models/shp/runs/EG00_001.tcf'
    tcf = TCF(p)
    inp = tcf.find_input('Read Grid')[0]
    assert inp.part_count == 2


def test_input_attrs_6():
    p = './tests/tmf/test_datasets/models/tins/runs/tin_copy_test.tcf'
    tcf = TCF(p)
    inp = tcf.find_input('Read Tin')[0]
    assert inp.part_count == 2


def test_input_match():
    line = r'Read GIS Network == ../model/gis/1d_nwk_EG15_001_L.shp'
    config = TCFConfig()
    config.control_file = TuflowPath('./tests/tmf/test_datasets/models/shp/runs/EG00_001.tcf')
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.is_match('Read GIS')
    assert inp.is_match(lhs='Read GIS')
    assert inp.is_match(rhs='1d_nwk')
    assert inp.is_match('^Read GIS (Network|Table)?', regex=True)
    assert inp.is_match(attrs=('has_missing_files', False))
    assert inp.is_match(attrs=('part_count', 1))
    assert inp.is_match('Read GRID') == False
    assert inp.is_match(lhs='Read GRID') == False
    assert inp.is_match(rhs='1d_nd') == False
    assert inp.is_match('^Read grid Zpts', regex=True) == False
    assert inp.is_match(attrs=('has_missing_files', True)) == False
    f = lambda x: 'LineString' in x
    assert inp.is_match(attrs=('geoms', f))
    f = lambda x: 'Point' in x
    assert inp.is_match(attrs=('geoms', f)) == False
    assert inp.is_match(attrs=('geoms', ['LineString']))

    def callback(inp):
        return inp.part_count == 1
    assert inp.is_match(callback=callback)

    def callback(inp):
        return inp.has_missing_files
    assert inp.is_match(callback=callback) == False


def test_pit_reference():
    line = r'Read GIS Network == ./1d_nwk_EG15_001_P.shp'
    config = TCFConfig()
    config.control_file = TuflowPath('./tests/tmf/test_datasets/1d_domain_scope.tcf')  # any tcf in this dir works
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert len(inp.files) == 1
    assert not inp.has_missing_files


def test_mi_proj_string():
    line = 'MI Projection == CoordSys Earth Projection 8, 104, "m", 177, 0, 0.9996, 500000, 10000000'
    config = TCFConfig()
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.rhs == 'CoordSys Earth Projection 8, 104, "m", 177, 0, 0.9996, 500000, 10000000'
    assert not inp.has_missing_files


def test_uk_hazard_formula():
    line = 'UK Hazard Formula == D*(V+1.5)'
    config = TCFConfig()
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.rhs == 'D*(V+1.5)'
    assert not inp.has_missing_files


def test_case_insensitive_path():
    line = r'Event File == tests\tmf\Test_datasets\Event_File.tef'
    config = TCFConfig()
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.value == TuflowPath('tests/tmf/test_datasets/event_file.tef')


def test_case_insensitive_path_from_cf():
    line = r'Event File == ..\Test_datasets\Event_File.tef'
    config = TCFConfig()
    config.control_file = TuflowPath('tests/tmf/test_datasets/event_tcf.tcf')
    command = Command(line, config)
    inp = get_input_class(command)(None, command)
    assert inp.value.resolve() == (TuflowPath() / 'tests/tmf/test_datasets/event_file.tef').resolve()
