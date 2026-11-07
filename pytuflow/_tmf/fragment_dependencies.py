"""Invocation-local immutable dependency fragments for file-existence batches.

Evaluate each section only for distinct effective substitutions and branch
decisions. Mutable InputRunState objects are discarded after projection, never
shared. The ordinary evaluator remains authoritative for command semantics.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Any, cast

from .compiled_scope import ScopeProgram, builtin_translation
from .context import Context
from .dependency_records import (
    BatchDependencyRun,
    BatchInputCommand,
    BatchInputReference,
)
from .effective_dependencies import EffectiveDependencyManifest
from .file_reference import (
    DeferredDatabaseActivation,
    DeferredDatabaseSource,
    FileReference,
)
from .fragment_context import FragmentContextBase, raw_class_attribute
from .options import FileResolution

_TOKEN = re.compile(r"<<([^<>]+)>>")
_LIMIT = 10000


def _variable_name(token: str) -> str:
    """Normalise variable names for compiled expression caching."""
    name = token.upper()
    if re.fullmatch(r"~[SE]~", name):
        name = name[:-1] + "1~"
    return name.strip("~") if name.startswith(("~S", "~E")) else name


def _has_partial_delimiter(value: str) -> bool:
    """Detect bracket pieces outside already-complete <<variable>> tokens."""
    if "<" not in value and ">" not in value:
        return False
    remainder = _TOKEN.sub("", value)
    return "<" in remainder or ">" in remainder


@dataclass(frozen=True, slots=True)
class CompiledExpression:
    """Literal/token operations; complex TEF replacement uses Context semantics."""

    text: str
    operations: tuple[tuple[bool, str], ...]
    variables: tuple[str, ...]

    @classmethod
    def compile(cls, text: str) -> CompiledExpression:
        """Compile an expression while preserving variable substitution order."""
        operations: list[tuple[bool, str]] = []
        names: set[str] = set()
        end = 0
        for match in _TOKEN.finditer(text):
            operations.append((False, text[end : match.start()]))
            operations.append((True, match.group(0)))
            names.add(_variable_name(match.group(1)))
            end = match.end()
        operations.append((False, text[end:]))
        return cls(text, tuple(operations), tuple(sorted(names)))

    def bindings(self, ctx: Any) -> tuple[object, ...]:
        """Compute the transitive variable values used in cache keys."""
        # Follow actual variable values transitively, including scoped Set
        # Variable declarations. Cycles terminate; Context decides errors.
        pending = list(self.variables)
        found: dict[str, object] = {}
        while pending:
            name = pending.pop()
            if name in found:
                continue
            value = ctx.var_map.get(name)
            found[name] = (
                value
                if isinstance(value, (str, int, float, type(None)))
                else repr(value)
            )
            if isinstance(value, str):
                pending.extend(
                    _variable_name(m.group(1)) for m in _TOKEN.finditer(value)
                )
        # TEF tokens are arbitrary strings and replacements can introduce other
        # tokens or <<variables>>. Retain ordered complete event bindings when
        # they can participate; do not assume tokens have ~ delimiters.
        has_events = bool(ctx.event_variables) and (
            bool(self.variables)
            or any(str(key).upper() in self.text.upper() for key in ctx.event_variables)
        )
        events = (
            tuple((key, str(value)) for key, value in ctx.event_variables.items())
            if has_events
            else ()
        )
        # Single angle brackets can join with literals/other substitutions
        # to *create* a previously untracked <<variable>> token. Unlike
        # complete tokens, these fragments are not discovered by the normal
        # transitive-variable walk. Include the full run variable map in the
        # expression-cache key rather than sharing a value across scenario
        # flags that were absent from the original expression.
        if (
            events
            or _has_partial_delimiter(self.text)
            or any(
                isinstance(value, str) and _has_partial_delimiter(value)
                for value in found.values()
            )
        ):
            # TEF substitutions and partial variable delimiters can reveal
            # additional variables absent from the original expression.
            return tuple(
                sorted((str(k), repr(v)) for k, v in ctx.var_map.items())
            ), events
        return tuple(sorted(found.items())), events

    def evaluate(self, ctx: Any) -> Any:
        """Resolve the expression using safe compiled substitutions."""
        # Only use the token join when no replacement can trigger a subsequent
        # replacement, numeric coercion, or arbitrary TEF substitution.
        # Even a single angle bracket can combine with another binding
        # and expose a <<~s1~>> token on Context's second pass.
        if (
            not ctx.event_variables
            and not _has_partial_delimiter(self.text)
            and all(
                isinstance(ctx.var_map.get(name), str)
                and "<" not in ctx.var_map[name]
                and ">" not in ctx.var_map[name]
                for name in self.variables
            )
        ):
            return "".join(
                str(ctx.var_map[_variable_name(value[2:-2])]) if token else value
                for token, value in self.operations
            )
        return Context.translate(ctx, self.text)


class ExpressionPool:
    """Compile expressions once and share evaluations by effective bindings."""

    def __init__(self) -> None:
        """Initialise per-batch fragment and scope caches."""
        self.plans: dict[str, CompiledExpression] = {}
        self.values: dict[tuple[str, tuple[object, ...]], Any] = {}
        self.evaluations = 0
        self.reuses = 0

    def translate(self, ctx: Any, text: Any) -> Any:
        """Evaluate an expression using compiled substitutions where safe."""
        from .tfpathlib import TuflowPath

        if not isinstance(text, (str, TuflowPath)):
            return text
        text = str(text)
        plan = self.plans.get(text)
        if plan is None:
            plan = CompiledExpression.compile(text)
            if len(self.plans) < _LIMIT:
                self.plans[text] = plan
        key = text, plan.bindings(ctx)
        if key in self.values:
            self.reuses += 1
            return self.values[key]
        value = plan.evaluate(ctx)
        self.evaluations += 1
        if len(self.values) < _LIMIT:
            self.values[key] = value
        return value


class _FragmentContext(FragmentContextBase):
    """Hold one run's variable and scope dependency state."""

    event_variables: dict[str, str]
    _batch_variable_assignments: tuple[tuple[Any, tuple[str, str]], ...]

    def __init__(
        self,
        flags: Any,
        config: Any,
        expressions: ExpressionPool,
        scopes: ScopeProgram | None = None,
    ) -> None:
        """Initialise per-batch fragment and scope caches."""
        self._scope_program = scopes
        self._compiled_scope_safe: bool | None = None
        self._compiled_flag_names: dict[str, frozenset[str]] = {}
        self._compiled_event_names: tuple[tuple[str, ...], frozenset[str]] = (
            (),
            frozenset(),
        )
        self.expressions = expressions
        # A subtree is keyed repeatedly through its ancestors. Keep each
        # expression's complete key component once per run, never cross-run.
        self._fragment_signature_values: dict[str, tuple[str, tuple[object, ...]]] = {}
        cast(Any, super()).__init__(flags, config=config)
        self.file_resolution = FileResolution.DEFERRED

    def _invalidate(self) -> None:
        """Invalidate compilation results when the run context changes."""
        # Invalidate cached signatures whenever events, scenarios or
        # Set Variable declarations change during run preparation.
        self._fragment_signature_values.clear()
        self._compiled_scope_safe = None
        self._compiled_flag_names.clear()
        self._compiled_event_names = ((), frozenset())
        super()._invalidate()

    def _compiled_scope_eligible(self) -> bool:
        """Check whether this context permits safe builtin scope compilation."""
        if self._compiled_scope_safe is None:
            self._compiled_scope_safe = all(
                type(value) is str and "<<" not in value
                for kind in ("S", "E")
                for value in self._create_list(kind)
            )
        return self._compiled_scope_safe and all(
            "<<" not in key for key in self.event_variables
        )

    def _compiled_membership(self, kind: str) -> frozenset[str]:
        """Find the selected scope names for compiled membership tests."""
        from .scope import Scope

        names = self._compiled_flag_names.get(kind)
        if names is None:
            # Normalise selected flag values through the original constructors
            # once per invalidation, including alternatives and negative names.
            names = frozenset(
                name.lower()
                for value in self._create_list(kind)
                for part in Scope(kind, value).explode()
                if not part.is_neg()
                for name in part.names
            )
            self._compiled_flag_names[kind] = names
        if kind == "E" and self.event_variables:
            keys = tuple(self.event_variables)
            if keys != self._compiled_event_names[0]:
                self._compiled_event_names = (
                    keys,
                    frozenset(
                        name.lower()
                        for key in keys
                        for part in Scope("EVENT DEFINE", key).explode()
                        if not part.is_neg()
                        for name in part.names
                    ),
                )
            return names | self._compiled_event_names[1]
        return names

    def in_context_by_scope(self, req_scope: Any) -> bool:
        """Check scope membership, falling back to original evaluation as needed."""
        if self._scope_program is not None:
            active = self._scope_program.evaluate(req_scope, self)
            if active is not None:
                return active
        return super().in_context_by_scope(req_scope)

    def translate(self, item: Any) -> Any:
        """Evaluate an expression using compiled substitutions where safe."""
        from .tfpathlib import TuflowPath

        # Flags, event definitions and variables invalidate this run's
        # translation cache when they change. Repeated subtree-key checks can
        # therefore reuse resolved values within the current run.
        if not self._batch_active or not isinstance(item, (str, TuflowPath)):
            return self.expressions.translate(self, item)
        key = str(item)
        if key in self._batch_translations:
            self.translation_hits += 1
            return self._batch_translations[key]
        translated = self.expressions.translate(self, item)
        self.translation_misses += 1
        self._batch_translations[key] = translated
        return translated


@dataclass(frozen=True, slots=True)
class DependencyFragment:
    """Shared values with relative command ordinals and no mutable run owner."""

    commands: tuple[BatchInputCommand, ...] = ()
    references: tuple[BatchInputReference, ...] = ()
    sources: tuple[DeferredDatabaseSource, ...] = ()
    activations: tuple[DeferredDatabaseActivation, ...] = ()


# No mutable state or provenance is associated with an inactive input.
_EMPTY_FRAGMENT = DependencyFragment()


def _join(fragments: Iterable[DependencyFragment]) -> DependencyFragment:
    """Merge ordered fragments while retaining all input provenance."""
    commands: list[BatchInputCommand] = []
    refs: list[BatchInputReference] = []
    sources: list[DeferredDatabaseSource] = []
    activations: list[DeferredDatabaseActivation] = []
    for fragment in fragments:
        offset = len(commands)
        if offset:
            # Only later fragments need their relative ordinals rebased.
            commands.extend(
                replace(item, command_index=item.command_index + offset)
                for item in fragment.commands
            )
            refs.extend(
                replace(item, command_index=item.command_index + offset)
                for item in fragment.references
            )
            activations.extend(
                replace(item, sequence=item.sequence + offset)
                for item in fragment.activations
            )
        else:
            # Frozen first-fragment records already have the correct ordinals.
            commands.extend(fragment.commands)
            refs.extend(fragment.references)
            activations.extend(fragment.activations)
        sources.extend(fragment.sources)
    return DependencyFragment(
        tuple(commands), tuple(refs), tuple(sources), tuple(activations)
    )


@dataclass(frozen=True, slots=True)
class FragmentBatchResult:
    """Expose collected dependencies and fragment-reuse statistics."""

    runs: tuple[BatchDependencyRun, ...]
    fragments: tuple[DependencyFragment, ...]
    fragment_evaluations: int
    fragment_reuses: int
    expression_evaluations: int
    expression_reuses: int
    fallback_runs: int
    fallback_reason: str | None
    elapsed_seconds: float

    @property
    def passed(self) -> bool:
        """Report whether all requested runs resolved their dependencies."""
        return bool(self.runs) and all(run.error is None for run in self.runs)


# These classes inherit the unmodified base context constructor. A custom
# extension/monkeypatch is never eligible for immutable fragment caching.
_DEFAULT_CONTROL_FILE_TYPES = frozenset(
    {
        ("pytuflow._tmf.cf.adcf", "ADCF"),
        ("pytuflow._tmf.cf.fvptm", "FVPTM"),
        ("pytuflow._tmf.cf.qcf", "QCF"),
        ("pytuflow._tmf.cf.tbc", "TBC"),
        ("pytuflow._tmf.cf.tesf", "TESF"),
        ("pytuflow._tmf.cf.tgc", "TGC"),
        ("pytuflow._tmf.cf.toc", "TOC"),
        ("pytuflow._tmf.cf.trd", "TRD"),
        ("pytuflow._tmf.cf.trfc", "TRFC"),
        ("pytuflow._tmf.cf.tscf", "TSCF"),
    }
)


def _original_control_file_context(cf: Any) -> bool:
    """Reject custom model/include hooks before bypassing their evaluation.

    Only exact built-in control-file types with their original class method
    and no instance override can be treated as immutable fragments. Inspect
    raw definitions, avoiding execution of untrusted context descriptors.
    """
    from .cf.cf_build_state import (
        _CONTROL_FILE_BUILD_CONTEXT,  # pyright: ignore[reportPrivateUsage]
    )
    from .cf.ecf import _ECF_CONTEXT, ECF  # pyright: ignore[reportPrivateUsage]
    from .cf.fvc import _FVC_CONTEXT, FVC  # pyright: ignore[reportPrivateUsage]
    from .cf.fvsed import _FVSED_CONTEXT, FVSed  # pyright: ignore[reportPrivateUsage]
    from .cf.fvwq import _FVWQ_CONTEXT, FVWQ  # pyright: ignore[reportPrivateUsage]
    from .cf.tcf import _TCF_CONTEXT, TCF  # pyright: ignore[reportPrivateUsage]
    from .cf.tef import _TEF_CONTEXT, TEF  # pyright: ignore[reportPrivateUsage]

    cls = cast(type[Any], type(cf))
    special = {
        TCF: _TCF_CONTEXT,
        TEF: _TEF_CONTEXT,
        ECF: _ECF_CONTEXT,
        FVC: _FVC_CONTEXT,
        FVSed: _FVSED_CONTEXT,
        FVWQ: _FVWQ_CONTEXT,
    }
    expected = special.get(cls)
    if expected is None:
        if (cls.__module__, cls.__name__) not in _DEFAULT_CONTROL_FILE_TYPES:
            return False
        expected = _CONTROL_FILE_BUILD_CONTEXT
    namespace = object.__getattribute__(cf, "__dict__")
    return (
        type(namespace) is dict
        and "context" not in namespace
        and raw_class_attribute(cls, "context") is expected
        and raw_class_attribute(cls, "__getattribute__") is object.__getattribute__
    )


class _Plan:
    """Maintain an invocation-local plan for reusable input evaluation."""

    def __init__(
        self, model: Any, *, use_scopes: bool = True, use_manifests: bool = True
    ) -> None:
        """Initialise per-batch fragment and scope caches."""
        compiled_started = perf_counter()
        self.use_scopes = use_scopes
        self.use_manifests = use_manifests
        from .inp.cf import ControlFileInput
        from .inp.comment import CommentInput
        from .inp.db import DatabaseInput
        from .inp.file import FileInput
        from .inp.folder import FolderInput
        from .inp.gis import GisInput
        from .inp.grid import GridInput
        from .inp.mat import MatDatabaseInput
        from .inp.setting import SettingInput
        from .inp.time_inp import TimeInput
        from .inp.tin import TinInput
        from .inp.trd import TuflowReadFileInput
        from .parsers.command import Command, EventCommand

        if not _original_control_file_context(model):
            raise NotImplementedError("Custom model control file context hook")
        # An overridden Context.translate can change even a literal filename.
        # The compiled expression pool and subtree cache assume the original
        # translation semantics. A full-key fallback alone is insufficient:
        # an untracked hook result could alias across distinct run contexts.
        # Refuse fragment compilation and use the authoritative batch path.
        if not builtin_translation():
            raise NotImplementedError(
                "Custom Context.translate requires ordinary batch evaluation"
            )
        self.model = model
        self.expressions = ExpressionPool()
        self.scope_program = ScopeProgram()
        self._builtin_manifest_translation = builtin_translation()
        self.manifests: dict[int, EffectiveDependencyManifest] = {}
        self.file_manifests: dict[int, EffectiveDependencyManifest] = {}
        self.manifest_certificates: dict[tuple[object, ...], bool] = {}
        self.include_selections: dict[
            tuple[object, ...], tuple[DependencyFragment, tuple[Any, ...]]
        ] = {}
        self.pending_selections: dict[
            tuple[object, ...], tuple[DependencyFragment, tuple[Any, ...]]
        ] = {}
        self.compact_signatures = 0
        self.full_keys = 0
        self.manifest_hits = 0
        self.manifest_misses = 0
        self.manifest_fallbacks: dict[str, int] = {}
        self.cache: dict[tuple[int, tuple[object, ...]], DependencyFragment] = {}
        self.pending: dict[tuple[int, tuple[object, ...]], DependencyFragment] = {}
        self.evaluations = 0
        self.reuses = 0
        self.expressions_by_input: dict[int, tuple[str, ...]] = {}
        self.scopes_by_input: dict[int, tuple[Any, ...]] = {}
        self.children: dict[int, tuple[Any, ...]] = {}
        self.allowed = {
            ControlFileInput,
            DatabaseInput,
            FileInput,
            FolderInput,
            GisInput,
            GridInput,
            SettingInput,
            CommentInput,
            TimeInput,
            TinInput,
            TuflowReadFileInput,
            MatDatabaseInput,
        }
        self.command_types = {Command, EventCommand}
        self._source_sequences: dict[int, tuple[Any, ...]] = {}
        self.roots = self._source_inputs(model)
        self.event_tokens = (
            tuple(
                str(token).upper() for token in model.config.event_db.event_variables()
            )
            if model.config.event_db
            else ()
        )
        self.assignments = tuple(
            (inp, inp.command().parse_variable())
            for inp in model.find_input(lhs="set variable", recursive=True)
        )
        for inp in self.roots:
            self._compile(inp, set())
        self.compilation_seconds = perf_counter() - compiled_started

    def _source_inputs(self, source: Any) -> tuple[Any, ...]:
        """Prepare the source's ordered inputs once for this batch."""
        key = id(source)
        if key not in self._source_sequences:
            self._source_sequences[key] = source._dependency_inputs()
        return self._source_sequences[key]

    def _compile(self, inp: Any, ancestors: set[int]) -> None:
        """Compile one input and its nested descendants into dependency fragments."""
        from .inp.cf import ControlFileInput
        from .inp.db import DatabaseInput

        if id(inp) in ancestors:
            raise NotImplementedError("Cyclic control-file inclusion")
        if (
            type(inp) not in self.allowed
            or type(inp.command()) not in self.command_types
        ):
            raise NotImplementedError(
                f"Unsupported fragment input: {type(inp).__name__}"
            )
        if str(inp.lhs).upper().startswith("AD "):
            raise NotImplementedError(
                "AD database ownership requires the ordinary evaluator"
            )
        # Custom input hooks can mutate shared context/source state; never cache
        # them as pure evaluations. Only the original built-in methods qualify.
        from .cf.cf_run_state import (
            _batch_append_context_methods,  # pyright: ignore[reportPrivateUsage]
        )

        methods: Any = _batch_append_context_methods()
        method = methods.get(type(inp))
        if getattr(inp.context, "__func__", None) is not method:
            raise NotImplementedError("Custom input context hook")
        inline = getattr(inp, "trd_input", None)
        if inline is not None and (
            any(token in str(inline.rhs) for token in ("<<", "*", "?"))
            or any(token in str(inline.rhs).upper() for token in self.event_tokens)
        ):
            raise NotImplementedError(
                "Dynamic inline Read File requires the ordinary evaluator"
            )
        self.scope_program.compile(inp.scope)
        expressions = [str(inp.rhs or "")]
        scopes = [inp.scope]
        children: tuple[Any, ...] = (
            tuple(cast(Any, inp).cf) if type(inp) is ControlFileInput else ()
        )
        self.children[id(inp)] = children
        for child in children:
            if not _original_control_file_context(child):
                raise NotImplementedError("Custom included control file context hook")
            child_expressions: list[str] = []
            child_scopes: list[Any] = []
            for sub in self._source_inputs(child):
                self._compile(sub, ancestors | {id(inp)})
                child_expressions.extend(self.expressions_by_input[id(sub)])
                child_scopes.extend(self.scopes_by_input[id(sub)])
            if self.use_manifests:
                self.file_manifests[id(child)] = EffectiveDependencyManifest.compile(
                    id(child),
                    tuple(dict.fromkeys(child_expressions)),
                    tuple(child_scopes),
                    self.assignments,
                    self.scope_program,
                )
            expressions.extend(child_expressions)
            scopes.extend(child_scopes)
        if isinstance(inp, DatabaseInput):
            # Dataframes are already loaded source listings. This reads no
            # physical data; include all cells conservatively for row selection.
            for database in cast(Any, inp).cf:
                frame = getattr(database, "_df", None)
                if frame is not None:
                    expressions.extend(
                        str(value)
                        for row in frame.itertuples(index=True, name=None)
                        for value in row
                    )
        self.expressions_by_input[id(inp)] = tuple(dict.fromkeys(expressions))
        self.scopes_by_input[id(inp)] = tuple(scopes)
        if self.use_manifests:
            self.manifests[id(inp)] = EffectiveDependencyManifest.compile(
                id(inp),
                (str(inp.rhs or ""),)
                if children
                else self.expressions_by_input[id(inp)],
                (inp.scope,) if children else tuple(scopes),
                self.assignments,
                self.scope_program,
            )

    def _manifest_signature(
        self, manifest: EffectiveDependencyManifest, ctx: Any
    ) -> tuple[object, ...] | None:
        """Compute the variable bindings required for a safe fragment key."""
        reason = manifest.fallback_reason
        if not self._builtin_manifest_translation:
            reason = "custom-context-translation"
        if (
            reason is None
            and manifest.predicates
            and not ctx._compiled_scope_eligible()
        ):
            reason = "unproven-runtime-scope"
        bindings = manifest.bindings(ctx) if reason is None else None
        if reason is None and bindings is None:
            reason = "unproven-runtime-binding"
        if reason is None:
            certificate_key = (
                manifest.source_identity,
                bindings,
                tuple(ctx.event_variables),
            )
            independent = self.manifest_certificates.get(certificate_key)
            if independent is None:
                independent = manifest.event_independent(ctx)
                if len(self.manifest_certificates) < _LIMIT:
                    self.manifest_certificates[certificate_key] = independent
            if not independent:
                reason = "event-substitution"
        if reason is not None:
            self.manifest_fallbacks[reason] = self.manifest_fallbacks.get(reason, 0) + 1
            return None
        return bindings, tuple(
            predicate.evaluate(ctx) for predicate in manifest.predicates
        )

    def _key(self, inp: Any, ctx: Any) -> tuple[int, tuple[object, ...]]:
        """Compute the conservative cache key for an input and run context."""
        if not self.use_manifests:
            return self._full_key(inp, ctx)
        signature = self._manifest_signature(self.manifests[id(inp)], ctx)
        if signature is None:
            return self._full_key(inp, ctx)
        from .inp.cf import ControlFileInput

        selected: tuple[object, ...] = ()
        if type(inp) is ControlFileInput:
            projection, children = self._include_selection(inp, ctx)
            # Preserve resolved path spelling and ordered parsed source identity.
            # A missing/unparsed/ambiguous source fails in the original selector
            # before any fragment lookup, including on a warm cache.
            child_signatures: list[object] = []
            for child in children:
                child_signature = self._manifest_signature(
                    self.file_manifests[id(child)], ctx
                )
                if child_signature is None:
                    return self._full_key(inp, ctx)
                child_signatures.append((id(child), str(child.fpath), child_signature))
            selected = (
                tuple(ref.reference.path_pattern for ref in projection.references),
                tuple(child_signatures),
            )
        self.compact_signatures += 1
        return id(inp), ("manifest", signature, selected)

    def _full_key(self, inp: Any, ctx: Any) -> tuple[int, tuple[object, ...]]:
        """Construct a full-context key when a reduced key is unsafe."""
        self.full_keys += 1
        # Equality is based on effective values, not entire flag dictionaries.
        # This covers transitive variables and TEF changes without guessing that
        # E/S flags alone describe a file's dependencies.
        values: list[tuple[str, tuple[object, ...]]] = []
        for text in self.expressions_by_input[id(inp)]:
            signature = ctx._fragment_signature_values.get(text)
            if signature is None:
                expression = self.expressions.plans.get(text)
                if expression is None:
                    expression = CompiledExpression.compile(text)
                    if len(self.expressions.plans) < _LIMIT:
                        self.expressions.plans[text] = expression
                try:
                    value = str(ctx.translate(text))
                    # A later constructor translation can still expand variable
                    # chains or TEF tokens exposed only by the second variable pass.
                    # For example <<A>> -> <<B>> -> _EVENT_ has no remaining "<<"
                    # but its cached fragment still depends on the event selection.
                    needs_bindings = "<<" in value
                    if not needs_bindings and ctx.event_variables:
                        # TEF replacements themselves can cascade: _x_ -> _Y_
                        # before a later ordinary translation resolves _Y_.
                        # This applies even without any <<variable>> in the
                        # source expression.
                        folded = value.upper()
                        needs_bindings = any(
                            str(token).upper() in folded
                            for token in ctx.event_variables
                        )
                    binding = expression.bindings(ctx) if needs_bindings else ()
                    signature = value, binding
                except (ValueError, TypeError):
                    # Inactive commands must not fail merely while forming a key.
                    # Their ordinary evaluation, if selected, determines the error.
                    signature = text, expression.bindings(ctx)
                if len(ctx._fragment_signature_values) < _LIMIT:
                    ctx._fragment_signature_values[text] = signature
            values.append(signature)
        scopes = tuple(
            ctx.in_context_by_scope(scope) for scope in self.scopes_by_input[id(inp)]
        )
        return id(inp), (tuple(values), scopes)

    def _include_selection(
        self, inp: Any, ctx: Any
    ) -> tuple[DependencyFragment, tuple[Any, ...]]:
        """Identify nested inputs that apply to the selected run."""
        from .inp.cf import select_deferred_children
        from .inp.inp_run_state import InputRunState

        # Use the complete existing expression binding for the filename alone.
        # This preserves TEF cascades and late constructor substitutions without
        # signing descendant commands just to resolve an include.
        text = str(inp.rhs or "")
        expression = self.expressions.plans.get(text)
        if expression is None:
            expression = CompiledExpression.compile(text)
            if len(self.expressions.plans) < _LIMIT:
                self.expressions.plans[text] = expression
        cached_translation = (
            ctx._batch_translations.get(text) if ctx._batch_active else None
        )
        translated = (
            str(ctx.translate(text))
            if cached_translation is None
            else str(cached_translation)
        )
        late = "<<" in translated or any(
            str(token).upper() in translated.upper() for token in ctx.event_variables
        )
        selection_key = (id(inp), translated, expression.bindings(ctx) if late else ())
        prior = self.include_selections.get(
            selection_key, self.pending_selections.get(selection_key)
        )
        if prior is not None:
            return prior
        state = cast(Any, InputRunState)(inp, ctx, None)
        projection = self._project_state(state)
        children = select_deferred_children(
            inp, tuple(item.reference for item in projection.references)
        )
        selection = projection, children
        # Publish immutable selections only after the complete run succeeds.
        if len(self.include_selections) + len(self.pending_selections) < _LIMIT:
            self.pending_selections[selection_key] = selection
        return selection

    @staticmethod
    def _project_state(state: Any) -> DependencyFragment:
        """Capture resolved input references as immutable records."""
        from .cf.tcf_run_state import TCFRunState

        refs: tuple[FileReference, ...] = tuple(state.file_references)
        descriptor = BatchInputCommand(
            str(state.uuid),
            0,
            state._command.parent,
            state.line_number,
            str(state.lhs),
            str(state._command.original_text),
            len(refs),
        )
        records = tuple(
            BatchInputReference(
                descriptor.input_uuid,
                0,
                descriptor.owner_control_file,
                descriptor.line_number,
                ref,
            )
            for ref in refs
        )
        activations: list[DeferredDatabaseActivation] = []
        sources: list[DeferredDatabaseSource] = []
        for ref in refs:
            if ref.requires_database_scan:
                if (
                    ref.unresolved_variables
                    or ref.requires_directory_scan
                    or ref.database_kind in (None, "unknown")
                ):
                    raise ValueError(
                        f"Cannot establish database activation: {ref.path_pattern}"
                    )
                activations.append(
                    DeferredDatabaseActivation(
                        0,
                        descriptor.input_uuid,
                        ref.database_kind,
                        ref.path_pattern,
                        ref.origin,
                        descriptor.owner_control_file,
                        descriptor.line_number,
                    )
                )
                sources.extend(
                    cast(Any, TCFRunState)._deferred_sources_for_input(
                        state, ref.database_kind, ref
                    )
                )
        result = DependencyFragment(
            (descriptor,), records, tuple(sources), tuple(activations)
        )
        return result

    def evaluate(self, inp: Any, ctx: Any) -> DependencyFragment:
        """Resolve the expression using safe compiled substitutions."""
        from .inp.cf import ControlFileInput

        # Inactive inputs cannot contribute commands or dependencies. Avoid
        # translating their RHS or signing descendant inputs and database rows.
        # Existing per-run scope caching handles flag, event and variable changes.
        if not ctx.in_context_by_scope(inp.scope):
            return _EMPTY_FRAGMENT

        key = self._key(inp, ctx)
        prior = self.cache.get(key, self.pending.get(key))
        if prior is not None:
            self.reuses += 1
            if key[1][0] == "manifest":
                self.manifest_hits += 1
            return prior
        self.evaluations += 1
        if key[1][0] == "manifest":
            self.manifest_misses += 1
        if str(inp.lhs).upper() == "PAUSE":
            raise ValueError(f"Pause command encountered: {inp.rhs}")
        # Includes are projected without constructing their mutable child
        # tree. Leaves use their existing evaluator once per signature.
        if type(inp) is ControlFileInput:
            if self.use_manifests:
                result, children = self._include_selection(inp, ctx)
            else:
                from .inp.cf import select_deferred_children
                from .inp.inp_run_state import InputRunState

                result = self._project_state(cast(Any, InputRunState)(inp, ctx, None))
                children = select_deferred_children(
                    inp, tuple(item.reference for item in result.references)
                )
            result = _join(
                (
                    result,
                    *(
                        self.evaluate(sub, ctx)
                        for child in children
                        for sub in self._source_inputs(child)
                    ),
                )
            )
        else:
            result = self._project_state(inp.context(context=ctx, parent=None))
        if len(self.cache) + len(self.pending) < _LIMIT:
            self.pending[key] = result
        return result


def collect_file_dependencies(
    model: Any, run_flags: Iterable[str | dict[str, str]]
) -> FragmentBatchResult:
    """Project file dependencies with shared immutable subtree evaluations.

    Source models must remain read-only throughout this synchronous call. No
    callbacks expose mutable parser state. Unsupported source types use the
    existing Context/RunState evaluator; a failed run publishes no partial fragments.
    """
    from .cf.cf_run_state import prepare_run_context
    from .deferred_dependency_fallback import collect_fallback_dependencies

    started = perf_counter()
    try:
        plan = _Plan(model)
    except Exception as exc:  # noqa: BLE001 - incomplete compilation uses the authoritative evaluator
        fallback = collect_fallback_dependencies(model, run_flags)
        return FragmentBatchResult(
            fallback.runs,
            (),
            0,
            0,
            0,
            0,
            len(fallback.runs),
            str(exc),
            perf_counter() - started,
        )
    results: list[BatchDependencyRun] = []
    for index, flags in enumerate(run_flags):
        text = (
            flags
            if isinstance(flags, str)
            else " ".join(f"-{key.lstrip('-')} {value}" for key, value in flags.items())
        )
        try:
            ctx = _FragmentContext(
                flags,
                model.config,
                plan.expressions,
                plan.scope_program if plan.use_scopes else None,
            )
            cast(Any, ctx)._batch_variable_assignments = plan.assignments
            prepare_run_context(model, ctx)
            fragment = _join(plan.evaluate(inp, ctx) for inp in plan.roots)
            # Match the ordinary activation contract, including duplicate UUID
            # rejection; references alone are not proof of correct ownership.
            uuids = [command.input_uuid for command in fragment.commands]
            if any(uuids.count(item.input_uuid) != 1 for item in fragment.activations):
                raise ValueError("Ambiguous database activation ownership")
            results.append(
                BatchDependencyRun(
                    index,
                    text,
                    tuple(item.reference for item in fragment.references),
                    fragment.sources,
                    fragment.activations,
                    None,
                    fragment.references,
                    fragment.commands,
                )
            )
            plan.cache.update(plan.pending)
            plan.include_selections.update(plan.pending_selections)
        except Exception as exc:  # noqa: BLE001 - invalidate the complete run on parser failures
            results.append(
                BatchDependencyRun(
                    index, text, (), (), (), f"{type(exc).__name__}: {exc}"
                )
            )
        finally:
            plan.pending.clear()
            plan.pending_selections.clear()
    if not results:
        raise ValueError("At least one simulation context is required")
    return FragmentBatchResult(
        tuple(results),
        tuple(plan.cache.values()),
        plan.evaluations,
        plan.reuses,
        plan.expressions.evaluations,
        plan.expressions.reuses,
        0,
        None,
        perf_counter() - started,
    )
