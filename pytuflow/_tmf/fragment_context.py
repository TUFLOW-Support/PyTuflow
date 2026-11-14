"""Minimal memoised context for immutable fragment projection.

Uses existing Context semantics for events, scenarios and Set Variable blocks.
Each cache is confined to a single run, keeping context-specific state
isolated while reusing already parsed model inputs.
"""

from __future__ import annotations

from typing import Any

from .context import Context
from .scope import ScopeList


def raw_class_attribute(cls: type, name: str) -> object | None:
    """Inspect class dispatch without invoking a possibly custom descriptor."""
    for owner in type.__getattribute__(cls, "__mro__"):
        namespace = type.__getattribute__(owner, "__dict__")
        if name in namespace:
            return namespace[name]
    return None


class FragmentContextBase(Context):
    """Only the per-run scope/translation state needed by fragment projection."""

    def __init__(self, run_flags: str | dict[str, str], *, config: Any) -> None:
        """Initialise the independent scenario/event context for one batch run."""
        self._batch_active = False
        self._batch_scopes: ScopeList | None = None
        self._batch_scope_decisions: dict[int, tuple[object, bool]] = {}
        self._batch_translations: dict[str, str] = {}
        self.translation_hits = 0
        self.translation_misses = 0
        self.scope_builds = 0
        self.scope_hits = 0
        super().__init__(run_flags, config=config)
        self._batch_active = True

    def _invalidate(self) -> None:
        """Clear compiled scope state after modifying run selections."""
        self._batch_scopes = None
        self._batch_scope_decisions.clear()
        self._batch_translations.clear()

    def load_context_from_dict(self, context: dict) -> None:
        """Update flags while invalidating cached membership."""
        was_active = self._batch_active
        self._batch_active = False
        self._invalidate()
        try:
            super().load_context_from_dict(context)
        finally:
            self._invalidate()
            self._batch_active = was_active

    def load_events(self, event_db: Any) -> None:
        """Load selected events without sharing old scope state."""
        # Event definitions become visible sequentially while being loaded.
        was_active = self._batch_active
        self._batch_active = False
        self._invalidate()
        try:
            super().load_events(event_db)
        finally:
            self._invalidate()
            self._batch_active = was_active

    def load_variables(self, var_map: Any) -> None:
        """Apply scoped variables and invalidate compiled expressions."""
        self._invalidate()
        try:
            super().load_variables(var_map)
        finally:
            self._invalidate()

    @property
    def available_scopes(self) -> ScopeList:
        """Expose the selected scopes to the ordinary evaluator."""
        if not self._batch_active:
            return super().available_scopes
        if self._batch_scopes is None:
            self._batch_scopes = super().available_scopes
            self.scope_builds += 1
        else:
            self.scope_hits += 1
        return self._batch_scopes

    def in_context_by_scope(self, req_scope: ScopeList) -> bool:
        """Evaluate scope membership while retaining fallback semantics."""
        if not self._batch_active:
            return super().in_context_by_scope(req_scope)
        saved = self._batch_scope_decisions.get(id(req_scope))
        if saved is not None and saved[0] is req_scope:
            return saved[1]
        result = super().in_context_by_scope(req_scope)
        self._batch_scope_decisions[id(req_scope)] = (req_scope, result)
        return result
