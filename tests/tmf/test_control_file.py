import io
import os
from pathlib import Path
import pytest
import sys

from ...pytuflow._tmf.cf.tcf import TCF
from ...pytuflow._tmf.cf.ecf import ECF
from ...pytuflow._tmf.cf.tef import TEF
from ...pytuflow._tmf.cf.adcf import ADCF
from ...pytuflow._tmf.cf.qcf import QCF
from ...pytuflow._tmf.cf.trd import TRD
from ...pytuflow._tmf.cf.trfc import TRFC
from ...pytuflow._tmf.cf.tgc import TGC
from ...pytuflow._tmf.cf.tbc import TBC
from ...pytuflow._tmf.cf.toc import TOC
from ...pytuflow._tmf.cf.tesf import TESF
from ...pytuflow._tmf.scope import Scope, ScopeList
from ...pytuflow._tmf.db.pit_inlet import PitInletDatabase
from ...pytuflow._tmf.db.rf import RainfallDatabase
from ...pytuflow._tmf.db.soil import SoilDatabase
from ...pytuflow._tmf.utils.commands import Command
from ...pytuflow._tmf.context import Context
from ...pytuflow._tmf.settings import TCFConfig
from ...pytuflow._tmf.tfpathlib import TuflowPath
from ...pytuflow._tmf import const
from ...pytuflow._tmf.inp.get_input_class import get_input_class


def test_control_file_init_blank():
    control_file = TCF()
    assert control_file is not None
    assert control_file.fpath is None
    assert len(control_file.inputs) == 0
    assert str(control_file) == 'Empty Control File'


def test_control_init_error():
    with pytest.raises(TypeError):
        TCF(1)


def test_control_init_not_found():
    control_file = TCF('not_found.tcf')
    assert control_file.loaded is False
    assert str(control_file) == 'not_found.tcf (not found)'


def test_control_file_init():
    p = Path(__file__).parent / 'test_control_file.2cf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TCF(p)
        assert control_file is not None
        assert str(control_file.fpath) == str(p)
        assert len(control_file.inputs) == 2
        assert str(control_file) == 'test_control_file.2cf'
        assert repr(control_file) == '<TuflowControlFile> test_control_file.2cf'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.TCF
    except Exception as e:
        raise e
    finally:
        p.unlink()


def ftest_control_file_load_with_config():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead GIS == ../model/gis/projection.shp\nRead GRID == ../model/grid/grid.tif\n'
                'Read TIN == ../model/tin/tin.12da\nRead Soils File == ../model/read_file.trd\n'
                'Read Materials File == ../model/materials.csv\nRead Control File == ../some_control_file.2cf\n')
    with (Path(__file__).parent / 'read_file.trd').open('w') as f:
        f.write('banana')
    try:
        control_file = TCF()
        assert control_file is not None
        config = TCFConfig(p)
        config.read_tcf()
        control_file._load(p, config)
        assert str(control_file.fpath) == str(p)
        assert len(control_file.inputs) == 7
        assert len(control_file.commands()) == 7
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'read_file.trd').unlink()


def test_control_file_load_with_input():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON')
    try:
        line = 'Tutorial Model == ON'
        command = Command(line, TCFConfig())
        input_ = get_input_class(command)(None, command)
        control_file = TCF(p, scope=input_._scope)
        assert control_file._scope == [Scope('GLOBAL')]
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_inputs():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TCF(p)
        assert control_file is not None
        assert len(control_file.inputs) == 2
        assert str(control_file.inputs[0]) == 'Tutorial Model == ON'
        assert str(control_file.inputs[1]) == 'Read GIS == ../model/gis/projection.shp'
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_commands():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TCF(p)
        assert control_file is not None
        assert control_file.inputs[0].lhs == 'Tutorial Model'
        assert control_file.inputs[1].lhs == 'Read GIS'
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_gis_inputs():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TCF(p)
        assert control_file is not None
        assert len(control_file.find_input(lhs='Read GIS')) == 1
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_grid_inputs():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead Grid Zpts == ../model/gis/projection.shp\n')
    try:
        control_file = TCF(p)
        assert control_file is not None
        assert len(control_file.find_input(lhs='Read GRID')) == 1
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_tin_inputs():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead Tin Zpts == ../model/gis/projection.shp\n')
    try:
        control_file = TCF(p)
        assert control_file is not None
        assert len(control_file.find_input(lhs='Read TIN')) == 1
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_scenario_block():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TCF(p)
        assert control_file is not None
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_scenario_multiple():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL | DEMO\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TCF(p)
        assert control_file.inputs[0]._scope == [Scope('SCENARIO', 'TUTORIAL | DEMO')]
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_tcf():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TCF(p)
        assert repr(control_file) == '<TuflowControlFile> test_control_file.tcf'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.TCF
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_tgc():
    p = Path(__file__).parent / 'test_control_file.tgc'
    with p.open('w') as f:
        f.write('Set Code == 0\nSet Mat == 0\nSet Soil == 0\n')
    try:
        control_file = TGC(p)
        assert repr(control_file) == '<TuflowGeometryControl> test_control_file.tgc'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.TGC
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_tbc():
    p = Path(__file__).parent / 'test_control_file.tbc'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TBC(p)
        assert repr(control_file) == '<TuflowBoundaryControl> test_control_file.tbc'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.TBC
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_ecf():
    p = Path(__file__).parent / 'test_control_file.ecf'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = ECF(p)
        assert repr(control_file) == '<EstryControlFile> test_control_file.ecf'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.ECF
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_tef():
    p = Path(__file__).parent / 'test_control_file.tef'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TEF(p)
        assert repr(control_file) == '<TuflowEventFile> test_control_file.tef'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.TEF
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_adcf():
    p = Path(__file__).parent / 'test_control_file.adcf'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = ADCF(p)
        assert repr(control_file) == '<ADControlFile> test_control_file.adcf'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.ADCF
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_qcf():
    p = Path(__file__).parent / 'test_control_file.qcf'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = QCF(p)
        assert repr(control_file) == '<QuadtreeControlFile> test_control_file.qcf'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.QCF
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_tesf():
    p = Path(__file__).parent / 'test_control_file.tesf'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TESF(p)
        assert repr(control_file) == '<TuflowExternalStressFile> test_control_file.tesf'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.TESF
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_toc():
    p = Path(__file__).parent / 'test_control_file.toc'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TOC(p)
        assert repr(control_file) == '<TuflowOperatingControl> test_control_file.toc'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.TOC
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_trd():
    p = Path(__file__).parent / 'test_control_file.trd'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TRD(p)
        assert repr(control_file) == '<TuflowReadFile> test_control_file.trd'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.TRD
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_trfc():
    p = Path(__file__).parent / 'test_control_file.trfc'
    with p.open('w') as f:
        f.write('If Scenario == TUTORIAL\nTutorial Model == ON\nEnd If\nRead GIS == ../model/gis/projection.shp\n')
    try:
        control_file = TRFC(p)
        assert repr(control_file) == '<TuflowRainfallControl> test_control_file.trfc'
        assert control_file.TUFLOW_TYPE == const.CONTROLFILE.TRFC
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_else_scope():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('IF Scenario == DEV\n'
                '\tGeometry Control File == ../dev_control_file.tgc\n'
                'ELSE IF Event == 100y\n'
                '\tGeometry Control File == ../100y_control_file.tgc\n'
                'ELSE\n'
                '\tGeometry Control File == ../exg_control_file.tgc\n'
                'END IF\n')
    try:
        control_file = TCF(p)
        assert [str(x) for x in control_file.inputs[0]._scope] == [str(x) for x in [Scope('SCENARIO', 'DEV')]]
        assert [str(x) for x in control_file.inputs[1]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('EVENT', '100y')]]
        assert [str(x) for x in control_file.inputs[2]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('EVENT', '!100y')]]
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_nested_else_scope():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('IF Scenario == DEV\n'
                '\tIF Scenario == DEV2\n'
                '\t\tGeometry Control File == ../dev2_control_file.tgc\n'
                '\tELSE\n'
                '\t\tGeometry Control File == ../dev3_control_file.tgc\n'
                '\tEND IF\n'
                'ELSE IF Event == 100y\n'
                '\tIF Event == 60m\n'
                '\t\tGeometry Control File == ../100y60m_control_file.tgc\n'
                '\tELSE\n'
                '\t\tGeometry Control File == ../100y30m_control_file.tgc\n'
                '\tEND IF\n'
                'ELSE\n'
                '\tGeometry Control File == ../exg_control_file.tgc\n'
                'END IF\n')
    try:
        control_file = TCF(p)
        assert [str(x) for x in control_file.inputs[0]._scope] == [str(x) for x in [Scope('SCENARIO', 'DEV'), Scope('SCENARIO', 'DEV2')]]
        assert [str(x) for x in control_file.inputs[1]._scope] == [str(x) for x in [Scope('SCENARIO', 'DEV'), Scope('SCENARIO', '!DEV2')]]
        assert [str(x) for x in control_file.inputs[2]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('EVENT', '100y'), Scope('EVENT', '60m')]]
        assert [str(x) for x in control_file.inputs[3]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('EVENT', '100y'), Scope('EVENT', '!60m')]]
        assert [str(x) for x in control_file.inputs[4]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('EVENT', '!100y')]]
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_multi_if_blocks():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('IF Scenario == 5m\n'
                '\tCELL SIZE == 5\n'
                'Else If Scenario == 2.5m\n'
                '\tCELL SIZE == 2.5\n'
                'Else If Scenario == 1m\n'
                '\tCELL SIZE == 1\n'
                'ELSE\n'
                '\tPAUSE == Not a valid cell size selection\n'
                'END IF\n'
                '\n'
                'IF Scenario == EXG\n'
                '\t! No additonal commands \n'
                'ELSE IF Scenario == D01\n'
                '\tRead GIS Z Shape == gis\\2d_zsh_EG07_006_R.shp\n'
                'ELSE IF Scenario == D02\n'
                '\tCreate TIN Zpts == gis\\2d_ztin_EG07_010_R.shp\n'
                'ELSE\n'
                '\tPause == Not Valid Development Scenario\n'
                'END IF\n'
                '\n'
                'IF Scenario == DEV\n'
                '\tRead GIS Z Shape == gis\\2d_zsh_EG07_006_R.shp\n'
                'ELSE IF Scenario == DEV2\n'
                '\tCreate TIN Zpts == gis\\2d_ztin_EG07_010_R.shp\n'
                'ELSE\n'
                '\tPause == Not Valid Development Scenario\n'
                'END IF\n')
    try:
        control_file = TCF(p)
        assert [str(x) for x in control_file.inputs[0]._scope] == [str(x) for x in [Scope('SCENARIO', '5m')]]
        assert [str(x) for x in control_file.inputs[1]._scope] == [str(x) for x in [Scope('SCENARIO', '!5m'), Scope('SCENARIO', '2.5m')]]
        assert [str(x) for x in control_file.inputs[2]._scope] == [str(x) for x in [Scope('SCENARIO', '!5m'), Scope('SCENARIO', '!2.5m'), Scope('SCENARIO', '1m')]]
        assert [str(x) for x in control_file.inputs[3]._scope] == [str(x) for x in [Scope('SCENARIO', '!5m'), Scope('SCENARIO', '!2.5m'), Scope('SCENARIO', '!1m')]]
        assert [str(x) for x in control_file.inputs[4]._scope] == [str(x) for x in [Scope('SCENARIO', '!EXG'), Scope('SCENARIO', 'D01')]]
        assert [str(x) for x in control_file.inputs[5]._scope] == [str(x) for x in [Scope('SCENARIO', '!EXG'), Scope('SCENARIO', '!D01'), Scope('SCENARIO', 'D02')]]
        assert [str(x) for x in control_file.inputs[6]._scope] == [str(x) for x in [Scope('SCENARIO', '!EXG'), Scope('SCENARIO', '!D01'), Scope('SCENARIO', '!D02')]]
        assert [str(x) for x in control_file.inputs[7]._scope] == [str(x) for x in [Scope('SCENARIO', 'DEV')]]
        assert [str(x) for x in control_file.inputs[8]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('SCENARIO', 'DEV2')]]
        assert [str(x) for x in control_file.inputs[9]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('SCENARIO', '!DEV2')]]
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_multi_if_blocks_with_nesting():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('IF Scenario == DEV\n'
                '\tRead GIS Z Shape == gis\\2d_zsh_EG07_006_R.shp\n'
                '\tIF Scenario == DEV2\n'
                '\t\tGeometry Control File == ../dev2_control_file.tgc\n'
                '\tELSE IF Scenario == DEV3\n'
                '\t\tGeometry Control File == ../dev3_control_file.tgc\n'
                '\tELSE\n'
                '\t\tGeometry Control File == ../dev4_control_file.tgc\n'
                '\tEND IF\n'
                'ELSE IF Event == 100y\n'
                '\tRead GIS Z Shape == gis\\2d_zsh_EG07_010_R.shp\n'
                '\tIF Event == 60m\n'
                '\t\tGeometry Control File == ../100y60m_control_file.tgc\n'
                '\tELSE IF Event == 30m\n'
                '\t\tGeometry Control File == ../100y30m_control_file.tgc\n'
                '\tELSE IF Event == 15m\n'
                '\t\tGeometry Control File == ../100y15m_control_file.tgc\n'
                '\tELSE\n'
                '\t\tGeometry Control File == ../100y10m_control_file.tgc\n'
                '\tEND IF\n'
                'ELSE\n'
                '\tGeometry Control File == ../exg_control_file.tgc\n'
                'END IF\n'
                '\n'
                'IF Scenario == 5m\n'
                '\tCELL SIZE == 5\n'
                'Else If Scenario == 2.5m\n'
                '\tCELL SIZE == 2.5\n'
                'Else If Scenario == 1m\n'
                '\tCELL SIZE == 1\n'
                'ELSE\n'
                '\tPAUSE == Not a valid cell size selection\n'
                'END IF\n')
    try:
        control_file = TCF(p)
        assert [str(x) for x in control_file.inputs[0]._scope] == [str(x) for x in [Scope('SCENARIO', 'DEV')]]
        assert [str(x) for x in control_file.inputs[1]._scope] == [str(x) for x in [Scope('SCENARIO', 'DEV'), Scope('SCENARIO', 'DEV2')]]
        assert [str(x) for x in control_file.inputs[2]._scope] == [str(x) for x in [Scope('SCENARIO', 'DEV'), Scope('SCENARIO', '!DEV2'), Scope('SCENARIO', 'DEV3')]]
        assert [str(x) for x in control_file.inputs[3]._scope] == [str(x) for x in [Scope('SCENARIO', 'DEV'), Scope('SCENARIO', '!DEV2'), Scope('SCENARIO', '!DEV3')]]
        assert [str(x) for x in control_file.inputs[4]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('EVENT', '100y')]]
        assert [str(x) for x in control_file.inputs[5]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('EVENT', '100y'), Scope('EVENT', '60m')]]
        assert [str(x) for x in control_file.inputs[6]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('EVENT', '100y'), Scope('EVENT', '!60m'), Scope('EVENT', '30m')]]
        assert [str(x) for x in control_file.inputs[7]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('EVENT', '100y'), Scope('EVENT', '!60m'), Scope('EVENT', '!30m'), Scope('EVENT', '15m')]]
        assert [str(x) for x in control_file.inputs[8]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('EVENT', '100y'), Scope('EVENT', '!60m'), Scope('EVENT', '!30m'), Scope('EVENT', '!15m')]]
        assert [str(x) for x in control_file.inputs[9]._scope] == [str(x) for x in [Scope('SCENARIO', '!DEV'), Scope('EVENT', '!100y')]]
        assert [str(x) for x in control_file.inputs[10]._scope] == [str(x) for x in [Scope('SCENARIO', '5m')]]
        assert [str(x) for x in control_file.inputs[11]._scope] == [str(x) for x in [Scope('SCENARIO', '!5m'), Scope('SCENARIO', '2.5m')]]
        assert [str(x) for x in control_file.inputs[12]._scope] == [str(x) for x in [Scope('SCENARIO', '!5m'), Scope('SCENARIO', '!2.5m'), Scope('SCENARIO', '1m')]]
        assert [str(x) for x in control_file.inputs[13]._scope] == [str(x) for x in [Scope('SCENARIO', '!5m'), Scope('SCENARIO', '!2.5m'), Scope('SCENARIO', '!1m')]]
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_if_or():
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
        assert [str(x) for x in control_file.inputs[0]._scope] == [str(x) for x in [Scope('SCENARIO', 'D01 | D02')]]
        assert [str(x) for x in control_file.inputs[1]._scope] == [str(x) for x in
                                                                   [Scope('SCENARIO', '!D01 | !D02'), Scope('SCENARIO', 'D03')]]
        assert [str(x) for x in control_file.inputs[2]._scope] == [str(x) for x in
                                                                   [Scope('SCENARIO', '!D01 | !D02'), Scope('SCENARIO', '!D03')]]
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_control_file_find_inputs():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Tutorial Model == ON\nRead GIS == ../model/gis/projection.shp\n'
                'Read GIS PO == 2d_po_EG07_010_R.shp\n'
                'Read GIS PO == 2d_po_EG07_010_L.shp\n'
                'Geometry Control File == ../model/geometry_control_file.tgc\n')
    with (Path(__file__).parent / 'test_control_file.tgc').open('w') as f:
        f.write('Read GIS == ../model/gis/projection.shp\n')
    with (Path(__file__).parent / '2d_po_EG07_010_R.shp').open('w') as f:
        f.write('banana')
    with (Path(__file__).parent / '2d_po_EG07_010_L.shp').open('w') as f:
        f.write('banana')
    try:
        control_file = TCF(p)
        assert [str(x) for x in control_file.find_input('Read GIS')] == ['Read GIS == ../model/gis/projection.shp', 'Read GIS PO == 2d_po_EG07_010_R.shp', 'Read GIS PO == 2d_po_EG07_010_L.shp']
        assert str(control_file.find_input(lhs='Geometry Control File')[0]) == 'Geometry Control File == ../model/geometry_control_file.tgc'
        assert str(control_file.find_input('Read GIS', lhs='PO', rhs='_L.shp')[0]) == 'Read GIS PO == 2d_po_EG07_010_L.shp'
    except Exception as e:
        raise e
    finally:
        p.unlink()
        (Path(__file__).parent / 'test_control_file.tgc').unlink()
        (Path(__file__).parent / '2d_po_EG07_010_R.shp').unlink()
        (Path(__file__).parent / '2d_po_EG07_010_L.shp').unlink()


def test_control_file_load_event_database():
    p = Path(__file__).parent / 'test_control_file.tcf'
    with p.open('w') as f:
        f.write('Event File == tuflow_event_file.tef\n')
    tef = Path(__file__).parent / 'tuflow_event_file.tef'
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
    try:
        control_file = TCF(p)
        event_db = control_file.event_database()
        assert event_db['Q100'] == {'_event1_': '100yr'}
        assert event_db['QPMF'] == {'_event1_': 'PMFyr'}
        assert event_db['2hr'] == {'_event2_': '2hr'}
        assert event_db['4hr'] == {'_event2_': '4hr'}
    except Exception as e:
        raise e
    finally:
        p.unlink()
        tef.unlink()


def test_control_file_trd_treatment():
    tgc = Path(__file__).parent / 'test_control_file.tgc'
    with tgc.open('w') as f:
        f.write('Set Code == 0\n')
        f.write('Read File == model/read_file.trd\n')
        f.write('Set Zpts == 75\n')
    trd = Path(__file__).parent / 'model' / 'read_file.trd'
    trd.parent.mkdir(exist_ok=True, parents=True)
    with trd.open('w') as f:
        f.write('Read GIS Code == 2d_code_M01_001.shp\n')
    with (Path(__file__).parent / '2d_code_M01_001.shp').open('w') as f:
        f.write('banana')
    try:
        control_file = TCF(tgc)
        assert len(control_file.inputs) == 3
    except Exception as e:
        raise e
    finally:
        tgc.unlink()
        trd.unlink()
        trd.parent.rmdir()
        (Path(__file__).parent / '2d_code_M01_001.shp').unlink()


def test_cf_get_files_if_block():
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
        files = sum([x.files for x in control_file.find_input()], [])
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


def test_cf_get_files_if_block_variables():
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
        files = sum([x.files for x in control_file.inputs], [])
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


def test_cf_get_files_if_block_nested_variables():
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
        files = list(set(sum([x.files for x in control_file.find_input()], [])))
        assert sorted(files) == sorted([file1, file2, file3, file4, file5, file6, file7, file8, file9, file10, file11,
                                        file12, file13, file14, file15, file16, file17, file18, file19, file20, file21,
                                        file22, file23, file24, file25, file26])
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


def test_load_soil_database():
    tcf = Path(__file__).parent / 'test.tcf'
    with tcf.open('w') as f:
        f.write('Read Soils File == soils.tsoilf')
    try:
        cf = TCF(tcf)
        assert isinstance(cf.soils_file(), SoilDatabase)
        assert cf.soils_file().TUFLOW_TYPE == const.DB.SOIL
    except Exception as e:
        raise e
    finally:
        tcf.unlink()


def test_load_pit_inlet_database():
    ecf = Path(__file__).parent / 'test.ecf'
    with ecf.open('w') as f:
        f.write('Pit Inlet Database == pit_dbase.csv')
    try:
        cf = ECF(ecf)
        assert isinstance(cf.pit_dbase(), PitInletDatabase)
        assert cf.pit_dbase().TUFLOW_TYPE == const.DB.PIT
    except Exception as e:
        raise e
    finally:
        ecf.unlink()


def test_load_rainfall_database():
    tcf = Path(__file__).parent / 'test.tcf'
    with tcf.open('w') as f:
        f.write('READ GRID RF == rainfall.nc')
    try:
        cf = TCF(tcf)
        assert isinstance(cf.rainfall_dbase(), RainfallDatabase)
        assert cf.rainfall_dbase().TUFLOW_TYPE == const.DB.RAINFALL
    except Exception as e:
        raise e
    finally:
        tcf.unlink()


def test_figure_out_file_scopes():
    tcf = Path(__file__).parent / 'test.tcf'
    line = 'Geometry Control File == <<~s1~>><<~s2~>>_001.tgc'
    with tcf.open('w') as f:
        f.write(line)
    tgc = Path(__file__).parent / 'M015m_001.tgc'
    with tgc.open('w') as f:
        f.write('Set Code == 1')
    try:
        cf = TCF(tcf)
        assert cf.inputs[0].file_scope(cf.inputs[0].files[0]) == ScopeList([Scope('SCENARIO', '<<~s1~>>'), Scope('SCENARIO', '<<~s2~>>')])
        cf.figure_out_file_scopes(ScopeList([Scope('SCENARIO', '5m'), Scope('SCENARIO', 'M01')]))
        assert cf.inputs[0].file_scope(cf.inputs[0].files[0]) == ScopeList([Scope('SCENARIO', 'M01'), Scope('SCENARIO', '5m')])
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        tgc.unlink()


def test_get_files():
    tcf = Path(__file__).parent / 'test.tcf'
    line = 'Geometry Control File == <<~s1~>><<~s2~>>_001.tgc'
    with tcf.open('w') as f:
        f.write(line)
    tgc = Path(__file__).parent / 'M015m_001.tgc'
    with tgc.open('w') as f:
        f.write('Read GIS Code == 2d_code_M01_001_R.shp')
    code = TuflowPath(__file__).parent / '2d_code_M01_001_R.shp'
    with code.open('w') as f:
        f.write('banana')
    try:
        cf = TCF(tcf)
        files = sum([inp.files for inp in cf.find_input()], [])
        assert files == [tgc, code]
        files = sum([inp.files for inp in cf.find_input(recursive=False)], [])
        assert files == [tgc]
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        tgc.unlink()
        code.unlink()


def test_init_adcf():
    adcf = Path(__file__).parent / 'test.tcf'
    with adcf.open('w') as f:
        f.write('banana')
    try:
        cf = ADCF(adcf)
        assert isinstance(cf, ADCF)
        assert cf.TUFLOW_TYPE == const.CONTROLFILE.ADCF
    except Exception as e:
        raise e
    finally:
        adcf.unlink()


def test_init_ecf():
    ecf = Path(__file__).parent / 'test.tcf'
    with ecf.open('w') as f:
        f.write('banana')
    try:
        cf = ECF(ecf)
        assert isinstance(cf, ECF)
        assert cf.TUFLOW_TYPE == const.CONTROLFILE.ECF
    except Exception as e:
        raise e
    finally:
        ecf.unlink()


def test_init_qcf():
    qcf = Path(__file__).parent / 'test.tcf'
    with qcf.open('w') as f:
        f.write('banana')
    try:
        cf = QCF(qcf)
        assert isinstance(cf, QCF)
        assert cf.TUFLOW_TYPE == const.CONTROLFILE.QCF
    except Exception as e:
        raise e
    finally:
        qcf.unlink()


def test_init_tbc():
    tbc = Path(__file__).parent / 'test.tcf'
    with tbc.open('w') as f:
        f.write('banana')
    try:
        cf = TBC(tbc)
        assert isinstance(cf, TBC)
        assert cf.TUFLOW_TYPE == const.CONTROLFILE.TBC
    except Exception as e:
        raise e
    finally:
        tbc.unlink()


def test_init_tcf():
    tcf = Path(__file__).parent / 'test.ecf'
    with tcf.open('w') as f:
        f.write('banana')
    try:
        cf = TCF(tcf)
        assert isinstance(cf, TCF)
        assert cf.TUFLOW_TYPE == const.CONTROLFILE.TCF
    except Exception as e:
        raise e
    finally:
        tcf.unlink()


def test_init_tef():
    tef = Path(__file__).parent / 'test.tcf'
    with tef.open('w') as f:
        f.write('banana')
    try:
        cf = TEF(tef)
        assert isinstance(cf, TEF)
        assert cf.TUFLOW_TYPE == const.CONTROLFILE.TEF
    except Exception as e:
        raise e
    finally:
        tef.unlink()


def test_init_tesf():
    tesf = Path(__file__).parent / 'test.tesf'
    with tesf.open('w') as f:
        f.write('banana')
    try:
        cf = TESF(tesf)
        assert isinstance(cf, TESF)
        assert cf.TUFLOW_TYPE == const.CONTROLFILE.TESF
    except Exception as e:
        raise e
    finally:
        tesf.unlink()


def test_init_tgc():
    tgc = Path(__file__).parent / 'test.tcf'
    with tgc.open('w') as f:
        f.write('banana')
    try:
        cf = TGC(tgc)
        assert isinstance(cf, TGC)
        assert cf.TUFLOW_TYPE == const.CONTROLFILE.TGC
    except Exception as e:
        raise e
    finally:
        tgc.unlink()


def test_init_toc():
    toc = Path(__file__).parent / 'test.tcf'
    with toc.open('w') as f:
        f.write('banana')
    try:
        cf = TOC(toc)
        assert isinstance(cf, TOC)
        assert cf.TUFLOW_TYPE == const.CONTROLFILE.TOC
    except Exception as e:
        raise e
    finally:
        toc.unlink()


def test_init_trd():
    trd = Path(__file__).parent / 'test.trd'
    with trd.open('w') as f:
        f.write('banana')
    try:
        cf = TRD(trd)
        assert isinstance(cf, TRD)
        assert cf.TUFLOW_TYPE == const.CONTROLFILE.TRD
    except Exception as e:
        raise e
    finally:
        trd.unlink()


def test_init_trfc():
    trfc = Path(__file__).parent / 'test.trfc'
    with trfc.open('w') as f:
        f.write('banana')
    try:
        cf = TRFC(trfc)
        assert isinstance(cf, TRFC)
        assert cf.TUFLOW_TYPE == const.CONTROLFILE.TRFC
    except Exception as e:
        raise e
    finally:
        trfc.unlink()


def test_no_tef():
    tcf = Path(__file__).parent / 'test.tcf'
    with tcf.open('w') as f:
        f.write('TUFLOW Event File == event_file.tef')
    try:
        cf = TCF(tcf)
        cf.inputs[0].cf = None
        with pytest.raises(ValueError):
            event_db = cf.event_database()
    except Exception as e:
        raise e
    finally:
        tcf.unlink()


def test_no_tef_2():
    tcf = Path(__file__).parent / 'test.tcf'
    with tcf.open('w') as f:
        f.write('Geometry Control File == geometry_control_file.tgc')
    try:
        cf = TCF(tcf)
        with pytest.raises(KeyError):
            event_db = cf.event_database()
    except Exception as e:
        raise e
    finally:
        tcf.unlink()


def test_no_tef_3():
    tcf = Path(__file__).parent / 'test.tcf'
    with tcf.open('w') as f:
        f.write('If Scenario == Climate_Change\n')
        f.write('\tEvent File == event_file_cc.tef\n')
        f.write('End If\n')
    try:
        cf = TCF(tcf)
        ctx = Context({'s': 'Baseline'})
        with pytest.raises(KeyError):
            event_db = cf.event_database(context=ctx)
    except Exception as e:
        raise e
    finally:
        tcf.unlink()


def test_no_tef_4():
    tcf = Path(__file__).parent / 'test.tcf'
    with tcf.open('w') as f:
        f.write('If Scenario == Climate_Change\n')
        f.write('\tEvent File == event_file_cc.tef\n')
        f.write('End If\n')
    try:
        cf = TCF(tcf)
        ctx = Context({'s': 'Climate_Change'})
        event_db = cf.event_database(context=ctx)
        assert not event_db
    except Exception as e:
        raise e
    finally:
        tcf.unlink()


def test_tef_req_context_err():
    tcf = Path(__file__).parent / 'test.tcf'
    with tcf.open('w') as f:
        f.write('If Scenario == Climate_Change\n')
        f.write('\tTUFLOW Event File == event_file_cc.tef\n')
        f.write('Else\n')
        f.write('\tTUFLOW Event File == event_file.tef\n')
        f.write('End If\n')
    try:
        with pytest.raises(ValueError):
            cf = TCF(tcf)
            cf.event_database()
    except Exception as e:
        raise e
    finally:
        tcf.unlink()


def test_tef_req_context_err2():
    tcf = Path(__file__).parent / 'test.tcf'
    with tcf.open('w') as f:
        f.write('If Scenario == Climate_Change\n')
        f.write('\tTUFLOW Event File == event_file_cc.tef\n')
        f.write('Else\n')
        f.write('\tTUFLOW Event File == event_file.tef\n')
        f.write('End If\n')
        f.write('If Scenario == Climate_Change\n')
        f.write('\tTUFLOW Event File == event_file_cc2.tef\n')
        f.write('End if\n')
    try:
        cf = TCF(tcf)
        ctx = Context({'s': 'Climate_Change'})
        with pytest.raises(ValueError):
            event_db = cf.event_database(context=ctx)
    except Exception as e:
        raise e
    finally:
        tcf.unlink()



def test_control_file_get_inputs():
    tcf = Path(__file__).parent / 'test.tcf'
    tgc = Path(__file__).parent / 'test.tgc'
    with tcf.open('w') as f:
        f.write('Geometry Control File == test.tgc')
    with tgc.open('w') as f:
        f.write('Read GIS Code == 2d_code_M01_R.shp')
    try:
        cf = TCF(tcf)
        inputs = cf.find_input()
        assert len(inputs) == 2
        ctx = cf.context()
        inputs = ctx.find_input()
        assert len(inputs) == 2
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        tgc.unlink()


def test_control_file_find_inputs_2():
    tcf = Path(__file__).parent / 'test.tcf'
    tgc = Path(__file__).parent / 'test.tgc'
    with tcf.open('w') as f:
        f.write('Geometry Control File == test.tgc')
    with tgc.open('w') as f:
        f.write('Read GIS Code == 2d_code_M01_R.shp')
    try:
        cf = TCF(tcf)
        inputs = cf.find_input(recursive=True)
        assert len(inputs) == 2
        ctx = cf.context()
        inputs = ctx.find_input(recursive=True)
        assert len(inputs) == 2
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        tgc.unlink()


def test_control_file_gis_inputs_2():
    tcf = Path(__file__).parent / 'test.tcf'
    tgc = Path(__file__).parent / 'test.tgc'
    with tcf.open('w') as f:
        f.write('Geometry Control File == test.tgc')
    with tgc.open('w') as f:
        f.write('Read GIS Code == 2d_code_M01_R.shp')
    try:
        cf = TCF(tcf)
        inputs = cf.find_input(lhs='read gis')
        assert len(inputs) == 1
        ctx = cf.context()
        inputs = ctx.find_input(lhs='read gis')
        assert len(inputs) == 1
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        tgc.unlink()


def test_control_file_grid_inputs_2():
    tcf = Path(__file__).parent / 'test.tcf'
    tgc = Path(__file__).parent / 'test.tgc'
    with tcf.open('w') as f:
        f.write('Geometry Control File == test.tgc')
    with tgc.open('w') as f:
        f.write('Read GRID Zpts == DEM_5m.tif')
    try:
        cf = TCF(tcf)
        inputs = cf.find_input(lhs='read grid')
        assert len(inputs) == 1
        ctx = cf.context()
        inputs = ctx.find_input(lhs='read grid')
        assert len(inputs) == 1
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        tgc.unlink()


def test_control_file_tin_inputs_2():
    tcf = Path(__file__).parent / 'test.tcf'
    tgc = Path(__file__).parent / 'test.tgc'
    with tcf.open('w') as f:
        f.write('Geometry Control File == test.tgc')
    with tgc.open('w') as f:
        f.write('Read TIN Zpts == survey.12da')
    try:
        cf = TCF(tcf)
        inputs = cf.find_input(lhs='read tin')
        assert len(inputs) == 1
        ctx = cf.context()
        inputs = ctx.find_input(lhs='read tin')
        assert len(inputs) == 1
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        tgc.unlink()


def test_control_file_append_input():
    tcf = TCF()
    tcf.append_input('Tutorial Model == ON')
    assert len(tcf.inputs) == 1
    tcf.append_input('GIS Format == SHP', gap=2)
    cmd = Command('\n', TCFConfig())
    assert len(tcf.inputs) == 2
    assert tcf.inputs[1].lhs == 'GIS Format'
    assert len(tcf.inputs._inputs) == 4
    assert tcf.inputs._inputs[1] == get_input_class(cmd)(tcf, cmd)
    assert tcf.inputs._inputs[2] == get_input_class(cmd)(tcf, cmd)


def test_control_file_insert_input():
    tcf = TCF()
    inp = tcf.append_input('Tutorial Model == ON')
    tcf.insert_input(inp, 'GIS Format == SHP')
    assert len(tcf.inputs) == 2
    assert tcf.inputs[0].lhs == 'GIS Format'
    inp_ = tcf.insert_input(inp, 'SGS == ON', gap=2)
    cmd = Command('\n', TCFConfig())
    assert len(tcf.inputs) == 3
    assert len(tcf.inputs._inputs) == 5
    assert tcf.inputs._inputs[1] == inp_
    assert tcf.inputs._inputs[2] == get_input_class(cmd)(tcf, cmd)
    assert tcf.inputs._inputs[3] == get_input_class(cmd)(tcf, cmd)
    inp_ = tcf.insert_input(inp, 'Hardware == GPU', True, gap=2)
    assert len(tcf.inputs) == 4
    assert tcf.inputs._inputs[5] == get_input_class(cmd)(tcf, cmd)
    assert tcf.inputs._inputs[6] == get_input_class(cmd)(tcf, cmd)
    assert tcf.inputs._inputs[7] == inp_


def test_control_file_remove_input():
    tcf = TCF()
    inp1 = tcf.append_input('Tutorial Model == ON')
    inp2 = tcf.append_input('GIS Format == SHP')
    tcf.remove_input(inp1)
    assert len(tcf.inputs) == 1
    tcf.remove_input(inp2)
    assert len(tcf.inputs) == 0


def test_undo_add_input():
    tcf = TCF()
    inp1 = tcf.append_input('Tutorial Model == ON')
    inp2 = tcf.append_input('GIS Format == SHP')
    tcf.undo()
    assert len(tcf.inputs) == 1
    tcf.undo()
    assert len(tcf.inputs) == 0


def test_undo_remove_input():
    tcf = TCF()
    inp1 = tcf.append_input('Tutorial Model == ON')
    inp2 = tcf.append_input('GIS Format == SHP')
    tcf.remove_input(inp1)
    assert len(tcf.inputs) == 1
    tcf.undo()
    assert len(tcf.inputs) == 2


def test_reset():
    tcf = TCF()
    inp1 = tcf.append_input('Tutorial Model == ON')
    inp2 = tcf.append_input('GIS Format == SHP')
    tcf.reset()
    assert len(tcf.inputs) == 0


def test_write():
    tcf_ = None
    tgc_ = None
    tcf = Path(__file__).parent / 'test_001.tcf'
    tgc = Path(__file__).parent / 'test_001.tgc'
    with tcf.open('w') as f:
        f.write('Solution Scheme == HPC\n')
        f.write('Hardware == GPU\n')
        f.write('Geometry Control File == test_001.tgc')
    with tgc.open('w') as f:
        f.write('Read GIS Code == 2d_code_M01_R.shp')
    try:
        cf = TCF(tcf)
        cf.tgc().dirty = True
        cf.write()
        tcf_ = Path(__file__).parent / 'test_002.tcf'
        tgc_ = Path(__file__).parent / 'test_002.tgc'
        assert tcf_.exists()
        assert tgc_.exists()
        with tcf_.open('r') as f:
            assert f.read() == 'Solution Scheme == HPC\nHardware == GPU\nGeometry Control File == test_002.tgc\n'
        with tgc_.open('r') as f:
            assert f.read() == 'Read GIS Code == 2d_code_M01_R.shp\n'
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        tgc.unlink()
        if tcf_ and tcf_.exists():
            tcf_.unlink()
        if tgc_ and tgc_.exists():
            tgc_.unlink()


def test_write_trd():
    tcf_ = None
    tcf_trd_ = None
    tgc_ = None
    tgc_trd_ = None
    tcf = Path(__file__).parent / 'test_001.tcf'
    tgc = Path(__file__).parent / 'test_001.tgc'
    tcf_trd = Path(__file__).parent / 'tcf_trd_001.trd'
    tgc_trd = Path(__file__).parent / 'tgc_trd_001.trd'
    with tcf.open('w') as f:
        f.write('Read File == tcf_trd_001.trd\n')
        f.write('Geometry Control File == test_001.tgc')
    with tcf_trd.open('w') as f:
        f.write('Solution Scheme == HPC\n')
        f.write('Hardware == GPU\n')
    with tgc.open('w') as f:
        f.write('Read File == tgc_trd_001.trd')
    with tgc_trd.open('w') as f:
        f.write('Read GIS Code == 2d_code_M01_R.shp')
    try:
        cf = TCF(tcf)
        cf.find_input('hardware')[0].dirty = True
        cf.tgc().dirty = True
        cf.find_input('code')[0].dirty = True
        cf.write()
        tcf_ = Path(__file__).parent / 'test_002.tcf'
        tgc_ = Path(__file__).parent / 'test_002.tgc'
        tcf_trd_ = Path(__file__).parent / 'tcf_trd_002.trd'
        tgc_trd_ = Path(__file__).parent / 'tgc_trd_002.trd'
        assert tcf_.exists()
        assert tgc_.exists()
        assert tcf_trd_.exists()
        assert tgc_trd_.exists()
        with tcf_.open('r') as f:
            assert f.read() == 'Read File == tcf_trd_002.trd\nGeometry Control File == test_002.tgc\n'
        with tcf_trd_.open() as f:
            assert f.read() == 'Solution Scheme == HPC\nHardware == GPU\n'
        with tgc_.open('r') as f:
            assert f.read() == 'Read File == tgc_trd_002.trd\n'
        with tgc_trd_.open('r') as f:
            assert f.read() == 'Read GIS Code == 2d_code_M01_R.shp\n'
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        tgc.unlink()
        tcf_trd.unlink()
        tgc_trd.unlink()
        if tcf_ and tcf_.exists():
            tcf_.unlink()
        if tcf_trd_ and tcf_trd_.exists():
            tcf_trd_.unlink()
        if tgc_trd_ and tgc_trd_.exists():
            tgc_trd_.unlink()
        if tgc_ and tgc_.exists():
            tgc_.unlink()


def test_control_file_write_scope():
    tcf_ = None
    tcf = Path(__file__).parent / 'test_001.tcf'
    with tcf.open('w') as f:
        f.write('If Scenario == HPC\n')
        f.write('\tSolution Scheme == HPC\n')
        f.write('\tHardware == GPU\n')
        f.write('Else\n')
        f.write('\tSolution Scheme == Classic\n')
        f.write('End If\n')
    try:
        cf = TCF(tcf)
        cf.write()
        tcf_ = Path(__file__).parent / 'test_002.tcf'
        assert tcf_.exists()
        with tcf_.open('r') as f:
            assert f.read() == 'If Scenario == HPC\n\tSolution Scheme == HPC\n\tHardware == GPU\nElse\n\tSolution Scheme == Classic\nEnd If\n'
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        if tcf_ and tcf_.exists():
            tcf_.unlink()


def test_control_file_write_nested_scope():
    tcf_ = None
    tcf = Path(__file__).parent / 'test_001.tcf'
    with tcf.open('w') as f:
        f.write('If Scenario == HPC\n')
        f.write('    If Scenario == QPC\n')
        f.write('        Quadtree Control File == Single Level\n')
        f.write('    End If\n')
        f.write('    Solution Scheme == HPC\n')
        f.write('    Hardware == GPU\n')
        f.write('Else\n')
        f.write('    Solution Scheme == Classic\n')
        f.write('End If\n')
    try:
        cf = TCF(tcf)
        cf.write()
        tcf_ = Path(__file__).parent / 'test_002.tcf'
        assert tcf_.exists()
        with tcf_.open('r') as f:
            assert f.read() == 'If Scenario == HPC\n    If Scenario == QPC\n        Quadtree Control File == Single Level\n    End If\n    Solution Scheme == HPC\n    Hardware == GPU\nElse\n    Solution Scheme == Classic\nEnd If\n'
    except Exception as e:
        raise e
    finally:
        tcf.unlink()
        if tcf_ and tcf_.exists():
            tcf_.unlink()

def test_output_folder_2d():
    p = Path(__file__).parent / 'test_datasets' / 'EG15_001.tcf'
    tcf = TCF(p)
    assert tcf.output_folder_2d().resolve() == TuflowPath(__file__).parent / 'results' / 'EG15'


def test_get_input_with_uuid():
    p = Path(__file__).parent / 'test_datasets' / 'EG15_001.tcf'
    tcf = TCF(p)
    inp = tcf.inputs[0]
    uuid = inp.uuid
    assert tcf.input(uuid) == inp
    assert tcf.input(str(uuid)) == inp


def test_if_logic_redundant_scenario():
    p = Path(__file__).parent / 'test_datasets' / 'redundant_scenario_logic.tcf'
    tcf = TCF(p)
    assert tcf == tcf


def test_preview_read_file():
    p = './tests/tmf/test_datasets/model_with_trd.tcf'
    tcf = TCF(p)
    buf = io.StringIO()
    tcf.preview(buf)
    text = (
        'Solution Scheme == HPC\n'
        'Read File == read_file.trd\n'
    )
    assert buf.getvalue() == text


def test_insert_before_comment():
    p = './tests/tmf/test_datasets/models/shp/runs/EG00_001.tcf'
    tcf = TCF(p)
    inp = tcf.inputs.inputs(include_hidden=True)[0]
    tcf.insert_input(inp, '! header comment')
    assert str(tcf.inputs.inputs(include_hidden=True)[0]) == '! header comment'


def test_insert_mat_file_without_ext():
    p = './tests/tmf/test_datasets/M01_2_5m_~s1~.tcf'
    tcf = TCF(p)
    roughness = tcf.find_input('Read Materials File')[0]
    plus = f'Read Materials File == Dummy_File | 1.2'
    minus = f'Read Materials File == Dummy_File | 0.8'
    minus_inp = tcf.insert_input(roughness, minus)
    assert minus_inp.TUFLOW_TYPE == const.INPUT.DB_MAT


def test_log_folder_with_spatial_database():
    p = './tests/tmf/test_datasets/EG07_002_test.tcf'
    tcf = TCF(p)
    assert tcf.log_folder_path() == Path('./tests/tmf/test_datasets/log')


def test_check_file_prefix():
    p = './tests/tmf/test_datasets/check_file_prefix.tcf'
    tcf = TCF(p)
    assert tcf.config.check_file_prefix_2d == 'model'
    assert tcf.config.check_file_prefix_1d == 'model1d'


def test_set_variable_with_file_path():
    if os.name == 'nt':
        p = './tests/tmf/test_datasets/set_variable_windows_file_path.tcf'
    else:
        p = './tests/tmf/test_datasets/set_variable_unix_file_path.tcf'
    tcf = TCF(p)
    if os.name == 'nt':
        assert tcf.output_folder_2d() == Path(r'C:\Users\Public\Public Models\Cavan\TUFLOW\Results')
    else:
        assert tcf.output_folder_2d() == Path('/home/public/models/cavan/tuflow/Results')


def test_absolute_folder_path():
    if os.name == 'nt':
        p = './tests/tmf/test_datasets/absolute_folder_path_windows.tcf'
    else:
        p = './tests/tmf/test_datasets/absolute_folder_path_linux.tcf'
    tcf = TCF(p).context()
    if os.name == 'nt':
        assert tcf.find_input('write check')[0].value == Path(r'C:\TUFLOW\Model\Check')
        assert tcf.find_input('output folder')[0].value == Path(r'D:\TUFLOW\Model\Results\1D')
    else:
        assert tcf.find_input('write check')[0].value == Path('/home/share/TUFLOW/Model/Check/')


def test_mi_projection_string():
    p = './tests/tmf/test_datasets/mi_proj_string.tcf'
    tcf = TCF(p).context()
    assert tcf.find_input('mi projection')[0].value == 'CoordSys Earth Projection 8, 79, "m", -2, 49, 0.9996012717, 400000, -100000 Bounds (-7845061.1011, -15524202.1641) (8645061.1011, 4470074.53373)'
