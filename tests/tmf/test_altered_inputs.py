from pathlib import Path

import pytest

from ...pytuflow._tmf.inp.altered_input import (AlteredInput, AlteredInputUpdatedValue,
                                    AlteredInputUpdatedCommand, AlteredInputAddedInput,
                                    AlteredInputRemovedInput, AlteredInputSetScope,
                                    AlteredInputs, get_altered_input_class)
from ...pytuflow._tmf.inp.get_input_class import get_input_class
from ...pytuflow._tmf.cf.tcf import TCF
from ...pytuflow._tmf.utils.commands import Command
from ...pytuflow._tmf.settings import TCFConfig
from ...pytuflow._tmf.scope import Scope, ScopeList


def test_updated_value_undo():
    cf = TCF()
    cmd = Command('Hardware == GPU', TCFConfig())
    inp = get_input_class(cmd)(cf, cmd)
    cf.inputs.append(inp)
    alt = get_altered_input_class('update_value')(inp, 0, 0, 0, 'update_value')
    assert isinstance(alt, AlteredInputUpdatedValue)
    inp.rhs = 'CPU'
    assert str(inp) == 'Hardware == CPU'
    alt.undo()
    assert str(inp) == 'Hardware == GPU'


def test_updated_command_undo():
    cf = TCF()
    cmd = Command('Hardware == GPU', TCFConfig())
    inp = get_input_class(cmd)(cf, cmd)
    cf.inputs.append(inp)
    alt = get_altered_input_class('update_command')(inp, 0, 0, 0, 'update_command')
    assert isinstance(alt, AlteredInputUpdatedCommand)
    inp.lhs = 'Solution Scheme'
    assert str(inp) == 'Solution Scheme == GPU'
    alt.undo()
    assert str(inp) == 'Hardware == GPU'


def test_add_input_undo():
    cf = TCF()
    cmd = Command('Hardware == GPU', TCFConfig())
    inp = get_input_class(cmd)(cf, cmd)
    cf.inputs.append(inp)
    alt = get_altered_input_class('add_input')(inp, 0, 0, 0, 'add_input')
    assert isinstance(alt, AlteredInputAddedInput)
    assert len(cf.inputs) == 1
    alt.undo()
    assert len(cf.inputs) == 0


def test_remove_input_undo():
    cf = TCF()
    cmd = Command('Hardware == GPU', TCFConfig())
    inp = get_input_class(cmd)(cf, cmd)
    alt = get_altered_input_class('remove_input')(inp, 0, 0, 0, 'remove_input')
    assert isinstance(alt, AlteredInputRemovedInput)
    assert len(cf.inputs) == 0
    alt.undo()
    assert len(cf.inputs) == 1


def test_remove_input_undo_2():
    p = Path(__file__).parent / 'test_datasets' / 'models' / 'shp' / 'runs' / 'EG00_001.tcf'
    tcf = TCF(p)
    inp = tcf.find_input('SGS == ON')[0]
    tcf.remove_input(inp)
    assert len(tcf.find_input('SGS == ON')) == 0
    tcf.undo()
    assert len(tcf.find_input('SGS == ON')) == 1
    inp = tcf.find_input('SGS == ON')[0]
    assert tcf.inputs.inputs(include_hidden=True).index(inp) == 12


def test_input_set_scope_undo():
    cf = TCF()
    cmd = Command('Hardware == GPU', TCFConfig())
    inp = get_input_class(cmd)(cf, cmd)
    inp.scope = ScopeList([Scope('SCENARIO', 'DEV')])
    cf.inputs.append(inp)
    alt = get_altered_input_class('set_scope')(inp, 0, 0, 0, 'set_scope')
    assert isinstance(alt, AlteredInputSetScope)
    inp.scope = ScopeList([Scope('SCENARIO', 'BASE')])
    assert inp.scope == [Scope('SCENARIO', 'BASE')]
    alt.undo()
    assert inp.scope == [Scope('SCENARIO', 'DEV')]


def test_altered_inputs_undo_group():
    alt_inps = AlteredInputs()
    cf = TCF()
    cmd = Command('Solution Scheme == HPC', TCFConfig())
    inp = get_input_class(cmd)(cf, cmd)
    cf.inputs.append(inp)
    alt_inps.add(inp, 0, 0, 0, 'add_input')
    cmd = Command('Hardware == GPU', TCFConfig())
    inp = get_input_class(cmd)(cf, cmd)
    cf.inputs.append(inp)
    alt_inps.add(inp, 1, 1, 0, 'add_input')
    assert len(cf.inputs) == 2
    alt_inps.undo(cf, False)
    assert len(cf.inputs) == 0


def test_altered_inputs_check_dirty():
    alt_inps = AlteredInputs()
    cf = TCF()
    cmd = Command('Solution Scheme == HPC', TCFConfig())
    inp = get_input_class(cmd)(cf, cmd)
    cf.inputs.append(inp)
    alt_inps.add(inp, 0, 0, 0, 'add_input')
    cmd = Command('Hardware == GPU', TCFConfig())
    inp = get_input_class(cmd)(cf, cmd)
    cf.inputs.append(inp)
    alt_inps.add(inp, 1, 1, 0, 'add_input')
    assert alt_inps.is_dirty(cf) == True


def test_altered_inputs_clear():
    alt_inps = AlteredInputs()
    cf = TCF()
    cf.dirty = True
    cmd = Command('Solution Scheme == HPC', TCFConfig())
    inp = get_input_class(cmd)(cf, cmd)
    inp.dirty = True
    cf.inputs.append(inp)
    alt_inps.add(inp, 0, 0, 0, 'add_input')
    alt_inps.clear()
    assert alt_inps.is_dirty(cf) == False
    assert cf.dirty == False
    assert inp.dirty == False


def test_altered_inputs_undo_after_write():
    p = './tests/tmf/test_datasets/models/shp/runs/EG00_001.tcf'
    tcf = TCF(p)
    inp = tcf.find_input('SGS == ON')[0]
    inp.rhs = 'Off'
    tcf.altered_inputs.clear()  # this is what write() calls
    tcf.undo()
    assert inp.rhs == 'ON'
    assert tcf.dirty == True
