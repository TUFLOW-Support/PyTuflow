"""Compare compiled predicates to the original scope evaluator."""

from __future__ import annotations

from itertools import product
from typing import Any

import pytest

from pytuflow._tmf.compiled_scope import ScopeProgram
from pytuflow._tmf.context import Context
from pytuflow._tmf.fragment_dependencies import ExpressionPool, _FragmentContext
from pytuflow._tmf.scope import Scope, ScopeList
from pytuflow._tmf.settings import TCFConfig


@pytest.mark.parametrize('index', range(1, 10))
@pytest.mark.parametrize(('flag', 'kind'), [('s', 'SCENARIO'), ('e', 'EVENT')])
def test_all_nine_flags_participate_in_scope_membership(index, flag, kind):
    flags = {f'{flag}1': 'first', f'{flag}{index}': 'selected'}
    ordinary = Context(flags)
    compiled = _FragmentContext(flags, TCFConfig(), ExpressionPool(), ScopeProgram())
    for context in (ordinary, compiled):
        assert context.in_context_by_scope(ScopeList([Scope(kind, 'selected')]))
        assert not context.in_context_by_scope(ScopeList([Scope(kind, '!selected')]))


def test_literal_predicates_match_original_membership() -> None:
    program = ScopeProgram()
    for scenario, event, negative, kind in product(
        ("A", "B", "A | B", "!A"),
        ("Q10", "Q100"),
        (False, True),
        ("SCENARIO", "EVENT", "EVENT DEFINE"),
    ):
        scopes = ScopeList(
            [
                Scope(
                    kind,
                    ("!" if negative else "")
                    + ("A | B" if kind == "SCENARIO" else "Q10"),
                )
            ]
        )
        flags = {"s1": scenario, "e1": event}
        ordinary = Context(flags)
        compiled = _FragmentContext(flags, TCFConfig(), ExpressionPool(), program)
        assert compiled.in_context_by_scope(scopes) == ordinary.in_context_by_scope(
            scopes
        )


def test_event_definition_names_are_visible_in_order() -> None:
    ctx = _FragmentContext("-e1 rain", TCFConfig(), ExpressionPool(), ScopeProgram())
    scopes = ScopeList([Scope("EVENT", "_new_")])
    assert not ctx.in_context_by_scope(scopes)
    ctx.event_variables["_NEW_"] = "value"
    assert ctx.in_context_by_scope(scopes)
    ctx.event_variables.clear()
    assert not ctx.in_context_by_scope(scopes)


def test_flags_invalidate_membership() -> None:
    ctx = _FragmentContext("-s1 A", TCFConfig(), ExpressionPool(), ScopeProgram())
    scopes = ScopeList([Scope("SCENARIO", "B")])
    assert not ctx.in_context_by_scope(scopes)
    del ctx.S1
    ctx.var_map.pop("S1")
    ctx.load_context_from_dict({"s1": "B"})
    assert ctx.in_context_by_scope(scopes)


def test_unknown_variable_and_custom_scopes_fall_back() -> None:
    program = ScopeProgram()
    for scopes in (
        ScopeList([Scope("VARIABLE", "<<A>>")]),
        ScopeList([Scope("SCENARIO", "<<~s1~>>")]),
    ):
        assert program.compile(scopes) is None
    scope: Any = Scope("SCENARIO", "A")
    scope.resolvable = lambda: False
    assert program.compile(ScopeList([scope])) is None


def test_global_and_else_precedence_match_original() -> None:
    program = ScopeProgram()
    for flags in ("-s1 A", "-s1 B", "-s1 C", "-s1 A -s2 B"):
        ctx = _FragmentContext(flags, TCFConfig(), ExpressionPool(), program)
        ordinary = Context(flags)
        for scopes in (
            ScopeList([Scope("GLOBAL"), Scope("EVENT", "missing")]),
            ScopeList([Scope("SCENARIO", "!A"), Scope("SCENARIO", "B")]),
            ScopeList([Scope("SCENARIO", "!A"), Scope("SCENARIO", "!B")]),
            ScopeList([Scope("1D DOMAIN")]),
        ):
            assert ctx.in_context_by_scope(scopes) == ordinary.in_context_by_scope(
                scopes
            )


def test_unresolved_selected_flags_use_original_variable_identity_semantics() -> None:
    flags = {"s1": "<<Selected>>"}
    scopes = ScopeList([Scope("SCENARIO", "EXG", var="<<Selected>>")])
    ctx = _FragmentContext(flags, TCFConfig(), ExpressionPool(), ScopeProgram())
    assert ctx.in_context_by_scope(scopes) == Context(flags).in_context_by_scope(scopes)


def test_custom_context_membership_hook_is_not_bypassed() -> None:
    from unittest.mock import patch

    scopes = ScopeList([Scope("SCENARIO", "absent")])
    with patch.object(Context, "in_context_by_scope", lambda self, scopes: True):
        program = ScopeProgram()
        ctx = _FragmentContext("-s1 A", TCFConfig(), ExpressionPool(), program)
        assert not program.enabled
        assert ctx.in_context_by_scope(scopes)


def test_mixed_negative_flag_alternatives_match_original() -> None:
    for kind, slot in (("SCENARIO", "s1"), ("EVENT", "e1")):
        for available in ("A | !B", "!A | B", "A | !B | C", "A | !B | !C"):
            flags = {slot: available}
            ctx = _FragmentContext(flags, TCFConfig(), ExpressionPool(), ScopeProgram())
            ordinary = Context(flags)
            for required in ("A", "B", "C", "!A", "!B", "!C", "A | B", "!A | B"):
                scopes = ScopeList([Scope(kind, required)])
                assert ctx.in_context_by_scope(scopes) == ordinary.in_context_by_scope(
                    scopes
                )


def test_mixed_negative_event_definition_alternatives_match_original() -> None:
    ctx = _FragmentContext("-e1 rain", TCFConfig(), ExpressionPool(), ScopeProgram())
    ordinary = Context("-e1 rain")
    ctx.event_variables["A | !B"] = ordinary.event_variables["A | !B"] = "value"
    for required in ("A", "B", "!A", "!B"):
        scopes = ScopeList([Scope("EVENT", required)])
        assert ctx.in_context_by_scope(scopes) == ordinary.in_context_by_scope(scopes)
