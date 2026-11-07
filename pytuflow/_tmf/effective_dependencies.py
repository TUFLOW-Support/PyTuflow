"""Conservative, invocation-local proofs for compact subtree signatures."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .compiled_scope import ScopePredicate, ScopeProgram
from .tfstrings.patterns import replace_exact_names

_TOKEN = re.compile(r"<<([^<>]+)>>")
_FLAG = re.compile(r"[SE][1-9]?")


def _name(token: str) -> str:
    """Normalise TUFLOW variable tokens for manifest lookup."""
    name = token.upper()
    if re.fullmatch(r"~[SE]~", name):
        name = name[:-1] + "1~"
    return name.strip("~") if name.startswith(("~S", "~E")) else name


def _references(text: str) -> tuple[str, ...] | None:
    """Find dependencies in a variable expression or decline unsupported syntax."""
    if any(mark in _TOKEN.sub("", text) for mark in ("<<", ">>")):
        return None
    return tuple(sorted({_name(match.group(1)) for match in _TOKEN.finditer(text)}))


@dataclass(frozen=True, slots=True)
class EffectiveDependencyManifest:
    """Record effective variable dependencies for one input."""

    source_identity: int
    variables: tuple[str, ...]
    predicates: tuple[ScopePredicate, ...]
    expressions: tuple[str, ...]
    allowed_values: tuple[tuple[str, frozenset[str]], ...]
    fallback_reason: str | None

    @classmethod
    def compile(
        cls,
        identity: int,
        expressions: tuple[str, ...],
        scopes: tuple[Any, ...],
        assignments: Any,
        program: ScopeProgram,
    ) -> EffectiveDependencyManifest:
        """Compile a manifest of transitive variable and scope dependencies."""
        declarations: dict[str, set[str]] = {}
        for _, (name, value) in assignments:
            declarations.setdefault(str(name).upper(), set()).add(str(value))
        found: set[str] = set()
        visiting: set[str] = set()
        reason: str | None = None

        def visit(name: str) -> None:
            """Traverse a referenced variable, reporting cycles conservatively."""
            nonlocal reason
            if name in visiting:
                reason = "cyclic-variable"
                return
            if name in found:
                return
            found.add(name)
            values = declarations.get(name)
            if values is None:
                if not _FLAG.fullmatch(name):
                    reason = "unknown-variable"
                return
            visiting.add(name)
            for value in values:
                refs = _references(value)
                if refs is None:
                    reason = "unsupported-variable-syntax"
                else:
                    for ref in refs:
                        visit(ref)
            visiting.remove(name)

        for text in expressions:
            refs = _references(text)
            if refs is None:
                reason = "unsupported-expression-syntax"
            else:
                for ref in refs:
                    visit(ref)
        predicates: list[ScopePredicate] = []
        for scope in scopes:
            predicate = program.compile(scope)
            if predicate is None:
                reason = "unsupported-scope"
            elif predicate not in predicates:
                predicates.append(predicate)
        return cls(
            identity,
            tuple(sorted(found)),
            tuple(predicates),
            expressions,
            tuple(
                (name, frozenset(declarations.get(name, ()))) for name in sorted(found)
            ),
            reason,
        )

    def bindings(self, ctx: Any) -> tuple[object, ...] | None:
        """Resolve the variable values that distinguish one reusable fragment."""
        values: list[object] = []
        for name, allowed in self.allowed_values:
            value = ctx.var_map.get(name)
            if value is not None and type(value) is not str:
                return None
            # Run flags may contain arbitrary text. Only parsed declarations
            # certify the closure of a value exposing additional substitutions.
            if isinstance(value, str) and "<<" in value and value not in allowed:
                return None
            values.append(value)
        return tuple(values)

    def event_independent(self, ctx: Any) -> bool:
        """Certify every variable-only pass, including concatenated TEF tokens.

        Called once per distinct binding/token-name signature by the plan, not
        per run. Check intermediate passes too: a TEF token may disappear after
        a later variable pass. Arbitrary replacement chains use the full key.
        """
        # Context normalises regex-matched replacement keys with upper().
        # lower()/casefold() alone miss e.g. final sigma or dotless i.
        tokens = tuple(str(key).upper() for key in ctx.event_variables)
        # Two independently expanded values can assemble a *new* variable
        # token. E.g. L="<", R=">" and "<<L>><~s1~><<R>>" expose
        # <<~s1~>> on the next translation pass. That new flag was not in
        # the compiled closure, so a compact key could alias different runs.
        # Check the closure at every intermediate variable-only pass, even
        # when there are no event variables. Unknown/malformed tokens must
        # use the existing complete-key evaluator.
        proven = frozenset(self.variables)
        for text in self.expressions:
            for _ in range(len(self.variables) + 3):
                refs = _references(text)
                if refs is None or any(ref not in proven for ref in refs):
                    return False
                if any(token in text.upper() for token in tokens):
                    return False
                expanded = replace_exact_names("<<.+?>>", ctx.var_map, text)
                if type(expanded) is not str:
                    return False
                if expanded == text:
                    break
                text = expanded
            else:
                return False
        return True
