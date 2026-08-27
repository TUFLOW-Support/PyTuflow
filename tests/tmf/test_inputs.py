import pytest

from ...pytuflow._tmf.inp.get_input_class import get_input_class
from ...pytuflow._tmf.inp.inputs import Inputs
from ...pytuflow._tmf.scope import Scope
from ...pytuflow._tmf.parsers.command import Command
from ...pytuflow._tmf.settings import TCFConfig


def test_inputs_init_blank():
    inputs = Inputs()
    assert inputs is not None
    assert len(inputs) == 0
    inputs.resolve_scopes()


def test_inputs_init_blank_2():
    inputs = Inputs()
    config = TCFConfig()
    cmd = Command('', config)
    inputs.append(get_input_class(cmd)(None, cmd))
    assert inputs is not None
    assert len(inputs) == 0


def test_inputs_init():
    inputs = Inputs()
    config = TCFConfig()
    cmd = Command('Tutorial Model == ON', config)
    inputs.append(get_input_class(cmd)(None, cmd))
    assert inputs is not None
    assert len(inputs) == 1
    assert repr(inputs) == 'Inputs([\'Tutorial Model == ON\'])'
    assert inputs._known_scopes() == [Scope('GLOBAL', '')]
    inputs.resolve_scopes()


def test_inputs_iter():
    inputs = Inputs()
    config = TCFConfig()
    cmd = Command('', config)
    inputs.append(get_input_class(cmd)(None, cmd))
    inputs.append(get_input_class(cmd)(None, cmd))
    inputs.append(get_input_class(cmd)(None, cmd))
    for input in inputs:
        assert input is not None


def test_inputs_slice():
    inputs = Inputs()
    config = TCFConfig()
    cmd1 = Command('Tutorial Model == ON', config)
    inputs.append(get_input_class(cmd1)(None, cmd1))
    cmd2 = Command('SGS == ON', config)
    inputs.append(get_input_class(cmd2)(None, cmd2))
    assert inputs[:] == [get_input_class(cmd1)(None, cmd1), get_input_class(cmd2)(None, cmd2)]


def test_inputs_get_item_error():
    inputs = Inputs()
    config = TCFConfig()
    cmd1 = Command('Tutorial Model == ON', config)
    cmd2 = Command('SGS == ON', config)
    inputs.append(get_input_class(cmd1)(None, cmd1))
    inputs.append(get_input_class(cmd2)(None, cmd2))
    with pytest.raises(TypeError):
        input = inputs['a']

