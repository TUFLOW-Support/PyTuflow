"""Conservative fallback for unsupported dependency fragments.

The standard Context/RunState evaluator remains authoritative when compact,
immutable fragment proofs cannot be established. Per-run errors fail closed,
and only identical structured flags reuse records in this invocation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

from .context import Context
from .dependency_records import (
    BatchDependencyRun,
    BatchInputCommand,
    BatchInputReference,
)
from .options import FileResolution

if TYPE_CHECKING:
    from .cf.tcf import TCF


@dataclass(frozen=True, slots=True)
class FallbackDependencyResult:
    """Per-run dependency results and explicit collection counters."""

    runs: tuple[BatchDependencyRun, ...]
    elapsed_seconds: float
    contexts_constructed: int
    contexts_reused: int

    @property
    def passed(self) -> bool:
        """Report whether every selected fallback run was resolved."""
        return bool(self.runs) and all(run.error is None for run in self.runs)


def _flag_text(flags: str | dict[str, str]) -> str:
    """Represent the run flags consistently in diagnostic messages."""
    if isinstance(flags, str):
        return flags
    return " ".join(f"-{key.lstrip('-')} {value}" for key, value in flags.items())


def _variable_assignments(model: TCF) -> tuple[tuple[object, tuple[str, str]], ...] | None:
    """Parse declarations once, but retain normal per-run scope selection.

    Failure to preparse is not a batch-wide failure: the standard evaluator
    must report the relevant errors for each run independently.
    """
    try:
        return tuple(
            (inp, inp.command().parse_variable())
            for inp in model.find_input(lhs="set variable", recursive=True)
        )
    except Exception:  # noqa: BLE001 - preserve ordinary per-run error boundaries
        return None


def collect_fallback_dependencies(
    model: TCF,
    run_flags: Iterable[str | dict[str, str]],
    *,
    on_run: Callable[[BatchDependencyRun], None] | None = None,
) -> FallbackDependencyResult:
    """Project supplied run flags with PyTUFLOW's existing context evaluator.

    This is not a scheduler. Scenario/event inventory does not establish valid combinations of -sN and -eN flags.

    Reuses the parsed model, its loaded TEF/database tables and immutable
    declarations. Context, variables, events and scopes are recomputed per
    distinct run. prepare_run_context selects active values.

    No post-parse filesystem, GIS or SQLite reads are requested here. Physical
    validation remains a separate consumer step. Errors fail closed and do not
    expose partial records. Callbacks run outside the parser error boundary.
    """
    started = perf_counter()
    assignments = _variable_assignments(model)
    seen: dict[tuple, BatchDependencyRun] = {}
    results: list[BatchDependencyRun] = []
    constructed = reused = 0

    for index, flags in enumerate(run_flags):
        flag_text = _flag_text(flags)
        # Keep type, dictionary order, keys and values; display text is lossy.
        flag_key = ('str', flags) if isinstance(flags, str) else ('dict', tuple(flags.items()))
        previous = seen.get(flag_key)
        if previous is not None:
            result = BatchDependencyRun(
                index, flag_text,
                previous.file_references,
                previous.database_sources,
                previous.database_activations,
                previous.error,
                previous.input_references,
                previous.ordered_inputs,
            )
            reused += 1
        else:
            constructed += 1
            try:
                ctx = Context(flags, config=model.config)
                if assignments is not None:
                    ctx._batch_variable_assignments = assignments
                # RunState resolves active inputs for each run independently.
                ctx._batch_run_index = index
                run = model.context(context=ctx, file_resolution=FileResolution.DEFERRED)
                active = tuple(run.find_input())
                commands: list[BatchInputCommand] = []
                refs: list[BatchInputReference] = []
                for ordinal, inp in enumerate(active):
                    input_refs = tuple(inp.file_references)
                    command = BatchInputCommand(
                        str(inp.uuid), ordinal, inp._command.parent,
                        inp.line_number, str(inp.lhs),
                        str(inp._command.original_text), len(input_refs),
                    )
                    commands.append(command)
                    refs.extend(
                        BatchInputReference(
                            command.input_uuid, ordinal,
                            command.owner_control_file,
                            command.line_number, ref,
                        )
                        for ref in input_refs
                    )
                activations = run.deferred_database_activations()
                sources = tuple(
                    source
                    for activation in activations
                    for source in run.deferred_database_sources_for_activation(
                        activation.input_uuid
                    )
                )
                result = BatchDependencyRun(
                    index, flag_text,
                    tuple(item.reference for item in refs),
                    sources,
                    activations,
                    None,
                    tuple(refs),
                    tuple(commands),
                )
            except Exception as exc:  # noqa: BLE001 - per-run fail-closed parity
                result = BatchDependencyRun(
                    index, flag_text, (), (), (), f"{type(exc).__name__}: {exc}"
                )
            seen[flag_key] = result

        results.append(result)
        if on_run is not None:
            on_run(result)

    if not results:
        raise ValueError("At least one simulation context is required")

    return FallbackDependencyResult(
        tuple(results), perf_counter() - started, constructed, reused
    )
