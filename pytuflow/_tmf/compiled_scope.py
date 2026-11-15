"""Invocation-local predicates for literal built-in scenario/event scopes.

This removes expansion and equality work, while preserving the original Context evaluation rules. Event definitions remain visible in source order.
Unknown, variable and extended scopes retain Context's ordinary evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from .context import (
    _CONTEXT_APPEND_ATTRIBUTES,  # pyright: ignore[reportPrivateUsage]
    Context,
)
from .scope import (
    _SCOPE_APPEND_DEFINITIONS,  # pyright: ignore[reportPrivateUsage]  - original built-in proof table
    ControlScope,
    EventDefineScope,
    EventScope,
    GlobalScope,
    OneDimScope,
    OutputZoneScope,
    ScenarioScope,
    ScopeList,
)


@dataclass(frozen=True, slots=True)
class ScopePredicate:
    """Represent an immutable, evaluated set of builtin scope requirements."""

    # Each condition is an OR of names; conditions are joined with AND.
    conditions: tuple[tuple[str, frozenset[str], bool], ...]

    def evaluate(self, ctx: Any) -> bool:
        """Check the selected run against the compiled scope requirements."""
        for kind, names, negated in self.conditions:
            available = ctx._compiled_membership(kind)
            if bool(names & available) == negated:
                return False
        return True


def builtin_translation() -> bool:
    """Check whether Context.translate retains its original implementation."""
    return Context.translate is dict(_CONTEXT_APPEND_ATTRIBUTES)["translate"]


def _builtin_definitions() -> bool:
    """Detect modified context or scope implementations before optimisation."""
    # A Context extension may redefine membership or the available scope set.
    # Compiling the built-in rule would bypass that hook, so retain its evaluator.
    original = dict(_CONTEXT_APPEND_ATTRIBUTES)
    if any(
        Context.__dict__.get(name) is not original[name]
        for name in ("in_context_by_scope", "available_scopes", "_create_list")
    ):
        return False
    return all(
        cls.__mro__ == mro
        and len(cls.__dict__) == len(attributes)
        and all(cls.__dict__.get(name) is value for name, value in attributes)
        for cls, mro, attributes in _SCOPE_APPEND_DEFINITIONS
    )


def _custom_attributes(scope: Any) -> bool:
    """Detect extension-defined scope attributes that affect evaluation."""
    attributes = cast(dict[str, object], vars(scope))
    return any(callable(value) for value in attributes.values())


class ScopeProgram:
    """Compile stable parsed scope lists once; never retain mutable contexts."""

    def __init__(self) -> None:
        """Initialise an invocation-local cache only when builtin scopes are intact."""
        self.enabled = _builtin_definitions()
        self.plans: dict[int, tuple[object, ScopePredicate | None]] = {}
        self.evaluations = 0
        self.fallbacks = 0

    def compile(self, scopes: Any) -> ScopePredicate | None:
        """Retrieve or construct a predicate for eligible builtin scopes."""
        prior = self.plans.get(id(scopes))
        if prior is not None and prior[0] is scopes:
            return prior[1]
        result = self._compile(scopes) if self.enabled else None
        if len(self.plans) < 10000:
            self.plans[id(scopes)] = scopes, result
        return result

    @staticmethod
    def _compile(scopes: Any) -> ScopePredicate | None:
        """Compile supported scope objects without changing their semantics."""
        if scopes is None:
            return ScopePredicate(())
        if type(scopes) is not ScopeList:
            return None
        items = cast(list[Any], scopes)
        allowed = (
            ScenarioScope,
            EventScope,
            EventDefineScope,
            GlobalScope,
            OneDimScope,
            OutputZoneScope,
            ControlScope,
        )
        if any(
            type(scope) not in allowed or _custom_attributes(scope) for scope in items
        ):
            return None
        # Context's GLOBAL membership check precedes all other predicates.
        if any(type(scope) is GlobalScope and not scope.is_neg() for scope in items):
            return ScopePredicate(())
        conditions: list[tuple[str, frozenset[str], bool]] = []
        for scope in items:
            if type(scope) in (OneDimScope, OutputZoneScope, ControlScope):
                continue
            if (
                type(scope) is GlobalScope
                or not scope.known
                or not scope.names
                or any(
                    not name or any(char in name for char in "<>|!")
                    for name in scope.names
                )
            ):
                return None
            kind = "S" if type(scope) is ScenarioScope else "E"
            conditions.append(
                (kind, frozenset(name.lower() for name in scope.names), scope.is_neg())
            )
        return ScopePredicate(tuple(conditions))

    def evaluate(self, scopes: Any, ctx: Any) -> bool | None:
        """Check the selected run against the compiled scope requirements."""
        predicate = self.compile(scopes)
        if predicate is None or not ctx._compiled_scope_eligible():
            self.fallbacks += 1
            return None
        self.evaluations += 1
        return predicate.evaluate(ctx)
