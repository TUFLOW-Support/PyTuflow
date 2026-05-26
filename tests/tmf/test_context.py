import pytest

from ...pytuflow._tmf.context import Context
from ...pytuflow._tmf.scope import Scope, ScopeList
from ...pytuflow._tmf.tfpathlib import TuflowPath
from ...pytuflow._tmf.event import EventDatabase


def test_context_init_ordered_args():
    ctx = Context('-s1 EXG -s2 5m -e1 100y')
    assert ctx['S1'] == 'EXG'
    assert ctx.S2 == '5m'
    assert ctx.E1 == '100y'


def test_context_init_orderd_dict():
    d = {'s1': 'EXG', 's2': '5m', 'e1': '100y'}
    ctx = Context(d)
    assert ctx['S1'] == 'EXG'
    assert ctx.S2 == '5m'
    assert ctx.E1 == '100y'


def test_context_init_variables():
    ctx = Context('-s1 EXG -s2 5m -e1 100y')
    ctx.load_variables({'CELL_SIZE': '5m', 'SAMPLE_DISTANCE': '10m'})
    assert ctx['CELL_SIZE'] == '5m'


def test_context_in_context_ordered():
    ctx = Context('-s1 EXG -s2 5m -e 100y')
    ctx.load_variables({'CELL_SIZE': '5m'})
    scopes = [Scope('SCENARIO', 'EXG')]
    input = TuflowPath(__file__).parent / 'input_file_<<~s1~>>.txt'
    p = TuflowPath(__file__).parent / 'input_file_EXG.txt'
    with p.open('w') as f:
        f.write('a,b,c\n1,2,3')
    try:
        assert ctx.in_context_by_scope(scopes) == True
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_context_in_context_ordered_2():
    ctx = Context('-s1 EXG -s2 5m e 100y')
    ctx.load_variables({'CELL_SIZE': '5m'})
    scopes = [Scope('SCENARIO', 'EXG'), Scope('EVENT', '100y'), Scope('VARIABLE', '5m', var='CELL_SIZE')]
    input = TuflowPath(__file__).parent / 'input_file_<<~s1~>>_<<~e~>>_<<CELL_SIZE>>.txt'
    p = TuflowPath(__file__).parent / 'input_file_EXG_100y_5m.txt'
    with p.open('w') as f:
        f.write('a,b,c\n1,2,3')
    try:
        assert ctx.in_context_by_scope(scopes) == True
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_context_in_context_ordered_3():
    ctx = Context('-s1 EXG -s2 5m -s3 100y')
    scopes = [Scope('SCENARIO', 'EXG'), Scope('SCENARIO', '100y'), Scope('SCENARIO', '5m')]
    input = TuflowPath(__file__).parent / 'input_file_<<~s1~>>_<<~s2~>>_<<~s3~>>.txt'
    p = TuflowPath(__file__).parent / 'input_file_EXG_100y_5m.txt'
    with p.open('w') as f:
        f.write('a,b,c\n1,2,3')
    try:
        assert ctx.in_context_by_scope(scopes) == True
    except Exception as e:
        raise e
    finally:
        p.unlink()


def test_context_in_context_negative_scopes():
    ctx = Context('-s1 EXG -s2 5m -s3 DEV')
    scopes = [Scope('SCENARIO', '!DEV'), Scope('SCENARIO', 'EXG'), Scope('SCENARIO', '5m')]
    assert ctx.in_context_by_scope(scopes) == False


def test_context_get_item_fail():
    ctx = Context('-s1 EXG -s2 5m -s3 DEV')
    assert ctx['s1'] is None


def test_parse_context_from_dict_error():
    d = {'s': 'EXG', 's1': 'DEV'}
    ctx = Context({})
    with pytest.raises(ValueError):
        ctx._parse_context_from_dict(d, 's')


def test_parse_context_from_dict_error2():
    d = {'s': 'EXG'}
    ctx = Context(d)
    with pytest.raises(ValueError):
        ctx._parse_context_from_dict(d, 's')


def test_parse_context_from_dict():
    d = {'s': 'EXG', 's2': 'DEV'}
    ctx = Context({})
    ctx._parse_context_from_dict(d, 's')
    assert ctx.S1 == 'EXG'


def test_parse_context_from_dict2():
    d = {'s': ['EXG'], 's2': 'DEV'}
    ctx = Context({})
    ctx._parse_context_from_dict(d, 's')
    assert ctx.S1 == 'EXG'


def test_convert_to_lower_keys():
    a = {'S': 'EXG', 'CELL_SIZE': '5m'}
    ctx = Context({})
    b = ctx._convert_to_lower_keys(a)
    assert b['s'] == 'EXG'
    assert b['CELL_SIZE'] == '5m'


def test_context_avaiable_scopes():
    ctx = Context('-s1 EXG -s2 BASE -s3 DEV -e Q100')
    ctx.load_variables({'CELL_SIZE': ['5m', '10m']})
    ctx.load_events(EventDatabase({'Q100': {'_ARI_': '100yr'}}))
    assert ctx.available_scopes == [Scope('SCENARIO', 'EXG'), Scope('SCENARIO', 'BASE'), Scope('SCENARIO', 'DEV'),
                                    Scope('EVENT', 'Q100'), Scope('EVENT DEFINE', '_ARI_'), Scope('VARIABLE', '5m'),
                                    Scope('VARIABLE', '10m')]


def test_context_load_variables():
    ctx = Context('-s1 EXG -s2 BASE -s3 DEV e Q100')
    ctx.load_variables(None)
    assert len(ctx.available_scopes) == 4


def test_context_load_event_variables():
    ctx = Context()
    ctx.load_events(None)
    assert len(ctx.available_scopes) == 0


def test_in_context_by_scope():
    ctx = Context()
    assert ctx.in_context_by_scope([Scope('SCENARIO', 'EXG')]) == False


def test_in_context_by_scope2():
    ctx = Context()
    ctx.load_variables({'CELL_SIZE': '5m'})
    assert ctx.in_context_by_scope([Scope('VARIABLE', '<<CELL_SIZE>>')]) == False


def test_translate():
    ctx = Context('-s EXG e Q100')
    ctx.load_variables({'CELL_SIZE': '5m'})
    ctx.load_events(EventDatabase({'Q100': {'_ARI_': '100yr'}}))
    assert ctx.translate('<<CELL_SIZE>>') == '5m'
    assert ctx.translate('<<~s1~>>') == 'EXG'
    assert ctx.translate('_ARI_') == '100yr'


def test_is_resolved():
    ctx = Context('-s EXG -e Q100')
    ctx.load_variables({'CELL_SIZE': '10'})
    ctx.load_events(EventDatabase({'Q100': {'_ARI_': '100yr'}}))
    assert ctx.is_resolved('<<CELL_SIZE>>') == False
    assert ctx.is_resolved(10) == True
    assert ctx.is_resolved('<<~s1~>>') == False
    assert ctx.is_resolved('filepath') == True
    assert ctx.is_resolved('_ARI_') == False


def test_context_from_string():
    ctx = Context('-s1 EXG -s2 5m -e1 100y')
    assert ctx['S1'] == 'EXG'
    assert ctx.S2 == '5m'
    assert ctx.E1 == '100y'
    assert ctx.context_args == ['-s1', 'EXG', '-s2', '5m', '-e1', '100y']
