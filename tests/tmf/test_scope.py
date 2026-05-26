import pytest

from ...pytuflow._tmf.scope import *


def test_scope_arg_error():
    with pytest.raises(TypeError):
        Scope()

    with pytest.raises(AttributeError):
        Scope(20)

    with pytest.raises(TypeError):
        Scope('GLOBAL', 5.5)

    with pytest.raises(TypeError):
        Scope('BANANA', 'test')


def test_scope_init_global():
    scope = Scope('GLOBAL', 'test')
    assert isinstance(scope, GlobalScope)
    assert scope.names == ['test']
    assert repr(scope) == '<GlobalScope>'


def test_scope_init_scenario():
    scope = Scope('SCENARIO', 'test')
    assert isinstance(scope, ScenarioScope)
    assert repr(scope) == '<ScenarioScope> test'


def test_scope_init_event():
    scope = Scope('EVENT', 'test')
    assert isinstance(scope, EventScope)
    assert repr(scope) == '<EventScope> test'


def test_scope_init_1d():
    scope = Scope('1D DOMAIN', 'test')
    assert isinstance(scope, OneDimScope)
    assert repr(scope) == '<OneDimScope> test'


def test_scope_init_map_output_zone():
    scope = Scope('OUTPUT ZONE', 'test')
    assert isinstance(scope, OutputZoneScope)
    assert repr(scope) == '<OutputZoneScope> test'


def test_scope_init_control():
    scope = Scope('CONTROL', 'test')
    assert isinstance(scope, ControlScope)
    assert repr(scope) == '<ControlScope> test'


def test_scope_init_variable():
    scope = Scope('VARIABLE', '<<test>>')
    assert isinstance(scope, VariableScope)
    assert repr(scope) == '<VariableScope> <<test>>'


def test_scope_str():
    scope = Scope('GLOBAL', 'test')
    assert str(scope) == 'GlobalScope: test'


def test_scope_eq():
    scope1 = Scope('GLOBAL', 'test')
    scope2 = Scope('GLOBAL', 'test')
    scope3 = Scope('GLOBAL', 'test2')
    scope4 = Scope('SCENARIO', 'test')
    assert scope1 == scope2
    assert scope1 != scope3
    assert scope1 != scope4
    assert scope1 != 5


def test_scope_known():
    scope = Scope('SCENARIO', 'test')
    assert scope.known is True
    scope = Scope('SCENARIO', '<<~s1~>>')
    assert scope.known is False


def test_scope_multiple():
    scope = Scope('SCENARIO', 'test | test2')
    assert scope.names == ['test', 'test2']
    assert repr(scope) == '<ScenarioScope> test | test2'


def test_scope_list_contains():
    scope_list = ScopeList([Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example')])
    assert Scope('SCENARIO') in scope_list


def test_scope_list_contains_2():
    scope_list = ScopeList([Scope('SCENARIO', 'test | test2'), Scope('SCENARIO', 'example')])
    assert Scope('SCENARIO', 'test') in scope_list


def test_scope_list_contains_3():
    scope_list = ScopeList([Scope('SCENARIO', 'test | test2'), Scope('SCENARIO', 'example')])
    assert Scope('SCENARIO', 'test2') in scope_list


def test_scope_list_contains_4():
    scope_list = ScopeList([Scope('SCENARIO', 'test | test2'), Scope('SCENARIO', 'example', var='<<~s~>>')])
    assert Scope('SCENARIO', '<<~s1~>>') in scope_list


def test_scope_list_contains_5():
    scope_list = ScopeList([Scope('SCENARIO', 'test | test2'), Scope('SCENARIO', '<<~s1~>>')])
    assert Scope('SCENARIO', '<<~s1~>>') in scope_list


def test_scope_list_contains_6():
    scope_list = ScopeList([Scope('SCENARIO', 'test | test2'), Scope('SCENARIO', '<<~s1~>>')])
    assert Scope('SCENARIO', '<<~s2~>>') not in scope_list


def test_scope_list_contains_7():
    scope_list = ScopeList([Scope('SCENARIO', 'test | test2'), Scope('SCENARIO', 'example', var='<<~s~>>')])
    assert Scope('SCENARIO', '<<~s2~>>') not in scope_list


def test_scope_list_contains_8():
    scope_list = ScopeList([Scope('SCENARIO', 'test'), Scope('SCENARIO', '<<~s~>>')])
    assert Scope('SCENARIO', 'test | test2') in scope_list


def test_scope_list_contains_9():
    scope_list = ScopeList([Scope('SCENARIO', 'test | test2'), Scope('SCENARIO', 'example', var='<<~s1~>>')])
    assert '<<~s2~>>' not in scope_list


def test_scope_list_contains_10():
    scope_list = ScopeList([Scope('SCENARIO', '!test'), Scope('SCENARIO', 'example')])
    assert Scope('SCENARIO') in scope_list


def test_scope_list_contains_11():
    scope_list = ScopeList([Scope('SCENARIO', '!test'), Scope('SCENARIO', 'example')])
    assert scope_list.contains(Scope('SCENARIO', 'test'), neg=False)


def test_scope_list_contains_12():
    scope_list = ScopeList([Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example')])
    assert Scope('SCENARIO', '!test') in scope_list


def test_scope_list_contains_13():
    scope_list = ScopeList([Scope('SCENARIO', '<<~s~>>'), Scope('SCENARIO', 'example')])
    assert Scope('SCENARIO', 'test2') not in scope_list


def test_event_variable():
    scope = Scope('EVENT DEFINE', '~ARI~')
    assert isinstance(scope, EventDefineScope)


def test_scope_str_neg():
    scope = Scope('EVENT', '!event1 | !event2')
    assert str(scope) == 'EventScope: !event1 | !event2'


def test_scope_str_neg_2():
    scope = Scope('EVENT', '!<<~s~>>')
    assert str(scope) == 'EventScope: !<<~s~>>'


def test_scope_repr_neg():
    scope = Scope('EVENT', '!event1 | !event2')
    assert repr(scope) == '<EventScope> !event1 | !event2'


def test_scope_repr_neg_2():
    scope = Scope('EVENT', '!<<~s~>>')
    assert repr(scope) == '<EventScope> !<<~s~>>'


def test_scope_contains():
    scope = Scope('SCENARIO', 'test')
    assert 'test' in scope


def test_scope_contains_2():
    scope = Scope('SCENARIO', 'test | test2')
    assert 'test2' in scope


def test_scope_contains_3():
    scope = Scope('SCENARIO', '<<~s~>>')
    assert 'test' not in scope


def test_scope_sort():
    scopes = [Scope('SCENARIO', 'test'), Scope('SCENARIO', 'example')]
    assert sorted(scopes) == [Scope('SCENARIO', 'example'), Scope('SCENARIO', 'test')]


def test_scope_is_neg():
    scope = Scope('SCENARIO', '!test')
    assert scope.is_neg()


def test_scope_is_neg_2():
    scope = Scope('SCENARIO', 'test')
    assert not scope.is_neg()


def test_scope_is_else():
    scope = Scope('SCENARIO (ELSE)', 'test')
    assert scope.is_else()


def test_scope_is_not_else():
    scope = Scope('SCENARIO', 'test')
    assert not scope.is_else()


def test_scope_var():
    scope = Scope('SCENARIO', 'test', var='<<~s~>>')
    assert scope.var == '<<~s1~>>'


def test_scope_var_2():
    scope = Scope('SCENARIO', '<<~e~>>')
    assert scope.var == '<<~e1~>>'


def test_scope_var_3():
    scope = Scope('VARIABLE', '<<CELL_SIZE>>')
    assert scope.var == '<<CELL_SIZE>>'


def test_scope_from_string():
    string = 'this_is_a_file_name'
    scope_list = Scope.from_string(string, string)
    assert scope_list == ScopeList([Scope('GLOBAL')])


def test_scope_from_string_2():
    string = 'this_<<~s~>>_a_file_name'
    scope_list = Scope.from_string(string, 'this_is_a_file_name')
    assert scope_list == ScopeList([Scope('SCENARIO', 'is')])


def test_scope_from_string_3():
    string = 'this_<<~s~>>_<<~e1~>>_file_name'
    scope_list = Scope.from_string(string, 'this_is_a_file_name')
    assert sorted(scope_list) == sorted(ScopeList([Scope('SCENARIO', 'is'), Scope('EVENT', 'a')]))


def test_scope_from_string_4():
    string = 'this_<<~s~>>_<<~e1~>>_<<var>>_name'
    scope_list = Scope.from_string(string, 'this_is_a_file_name')
    assert sorted(scope_list) == sorted(ScopeList([Scope('SCENARIO', 'is'), Scope('EVENT', 'a'), Scope('VARIABLE', '<<var>>')]))


def test_scope_from_string_5():
    string = 'this_<<~s~>>_<<~e1~>>_<<var>>_<<var>>'
    scope_list = Scope.from_string(string, 'this_is_a_file_name')
    assert sorted(scope_list) == sorted(ScopeList([Scope('SCENARIO', 'is'), Scope('EVENT', 'a'), Scope('VARIABLE', '<<var>>')]))


def test_scope_from_string_6():
    string = 'this_<<~s~>>_<<~e1~>>_<<var>>_<<var>>'
    scope_list = Scope.from_string(string, 'nothesamestring')
    assert sorted(scope_list) == sorted(ScopeList([Scope('SCENARIO', '<<~s~>>'), Scope('EVENT', '<<~e1~>>'), Scope('VARIABLE', '<<var>>')]))


def test_resolve_scopes():
    req_scope_list = ScopeList([Scope('SCENARIO', '<<~s~>>')])
    test_scopes = ScopeList([Scope('SCENARIO', 'is')])
    Scope.resolve_scope(req_scope_list, 'this_<<~s~>>_a_file_name', 'this_is_a_file_name', test_scopes)
    assert req_scope_list == ScopeList([Scope('SCENARIO', 'is')])


def test_resolve_scopes_2():
    req_scope_list = ScopeList([Scope('SCENARIO', 'is')])
    test_scopes = ScopeList([Scope('SCENARIO', 'is')])
    Scope.resolve_scope(req_scope_list, 'this_<<~s~>>_a_file_name', 'this_is_a_file_name', test_scopes)
    assert req_scope_list == ScopeList([Scope('SCENARIO', 'is')])
