import logging
import typing
from pathlib import Path

from ..abc.run_state import RunState, ResolveError
from ..abc.input import Input
from ..tmf_types import PathLike
from ..parsers.command import Command
from ..scope import ScopeList
from ..context import Context
from ..settings import from_config
from ..file_reference import FileReference



if typing.TYPE_CHECKING:
    from .inp_build_state import InputBuildState
    from ..cf.cf_run_state import ControlFileRunState

logger = logging.getLogger('pytuflow')


class InputRunState(RunState, Input):
    """Class for storing the run state of an input.

    This class should not be instantiated directly, but rather it should be created from an instance
    of a BuildState class using the `context` method of the BuildState class.

    Parameters
    ----------
    build_state : InputBuildState
        The BuildState object that the RunState object is based on.
    context : Context
        The context object that the RunState object is based on.
    parent : ControlFileRunState
        The parent control file run state.
    """

    def __init__(self, build_state: 'InputBuildState', context: Context, parent: 'ControlFileRunState'):
        super().__init__(build_state, context, parent)
        #: InputBuildState: the BuildState object that the RunState object is based on.
        self.bs = build_state
        #: ControlFileRunState: the parent control file
        self.parent = parent
        #: ControlFileRunState | DatabaseRunState: the loaded run state if the input is a control file or database.
        self.cf = []
        #: UUID4: A unique identifier for the input, set to the same as the BuildState UUID.
        self.uuid = self.bs.uuid
        #: Path | None: The .trd file that this input is from.
        self.trd = self.bs.trd
        #: TCFConfig: Configuration object for the input.
        self.config = self.bs.config
        #: int: The number of parts in the input command.
        self.part_count = 1

        self._rs: 'InputBuildState'

        self._resolve_scope_in_context()

    def __repr__(self):
        """Input name is BuildState type + Context."""
        if hasattr(self, 'lhs') and hasattr(self, 'rhs'):
            return '<{0}Context> {1} == {2}'.format(self._name, self.lhs, self.rhs)
        elif hasattr(self, 'lhs'):
            return '<{0}Context> {1}'.format(self._name, self.lhs)
        return '<{0}Context>'.format(self._name)

    @property
    def value(self) -> str | float | int | Path | tuple[str | float | int, ...]:
        return self._rs.value

    @property
    def files(self) -> list[Path]:
        return self._rs.files if self._rs else []

    @property
    def file_references(self) -> tuple[FileReference, ...]:
        """Immutable syntactic references; does not probe files or GIS layers."""
        if not self._rs:
            return ()
        return self._rs.file_references

    @property
    def database_source_references(self) -> tuple[FileReference, ...]:
        """Secondary input-file references from cached database rows.

        Explicit access only. Database files are loaded at initial TCF parse,
        not while building a deferred context or requesting file_references.
        Unsupported database schemas raise so consumers must fail closed.
        """
        from ..deferred_database import database_source_references
        kinds = {ref.database_kind for ref in self.file_references
                 if ref.requires_database_scan}
        if not kinds:
            return ()
        if len(kinds) != 1:
            raise ValueError(f'Ambiguous deferred database kinds: {kinds}')
        kind = next(iter(kinds))
        primaries = [ref for ref in self.file_references
                     if ref.requires_database_scan and ref.database_kind == kind]
        if len(primaries) != 1:
            raise ValueError(f'Cannot identify one primary {kind} database')
        primary_path = primaries[0].path_pattern
        source_base = None
        if kind == 'ad_bc':
            # TUFLOW AD specifies its BC Source paths relative to the
            # AD Global Database, not the AD BC table (2026.3 §9.4.4.1).
            owner = self.parent
            if owner is None:
                raise ValueError('Cannot resolve AD BC Source without an owning control file')
            globals_ = owner.root_cf.find_input(
                callback=lambda inp: inp.lhs.strip().casefold() == 'ad global database',
            )
            if len(globals_) != 1:
                raise ValueError(
                    f'AD BC Source requires one active AD Global Database; found {len(globals_)}'
                )
            primaries = [
                ref for ref in globals_[0].file_references
                if ref.database_kind == 'ad_global'
            ]
            if len(primaries) != 1 or primaries[0].requires_directory_scan or (
                primaries[0].unresolved_variables
            ):
                raise ValueError('Cannot identify a resolved AD Global Database path')
            source_base = primaries[0].path_pattern
        source_config = self._command.config
        if source_config.file_resolution != 'deferred':
            # A source projection is syntax-only even for an eager context.
            # Command.parts() must not glob or open GIS while classifying rows.
            source_config = from_config(source_config)
            source_config.file_resolution = 'deferred'
            source_config.variables = self.ctx.translate
        return database_source_references(
            self.bs, self.ctx, kind, source_config,
            source_base=source_base, primary_path=primary_path,
        )

    @property
    def has_missing_files(self) -> bool:
        return self._rs.has_missing_files if self._rs else False

    @property
    def line_number(self) -> int:
        return self.bs.line_number

    def file_scope(self, file: PathLike) -> ScopeList:
        return self._rs.file_scope(file)

    def _resolve_scope_in_context(self):
        """Method called after all initialisation and resolves all inputs to remove variable names and unused inputs.
        Also resolve any numeric and file references in command value.

        e.g.
        File references can be using variable names (either user defined or scenario/event)
        or
        Some commands can contain numeric values that have been replaced by a variable name
        even GIS inputs can contain numeric values:
            - Read GIS Mat == 2d_mat.shp | 3  ! 3 is the column index to use
            - Read GIS Zpts Conveyance == <gis file> | <float> | <grid>  ! second value is the numeric value

        GIS inputs also may have file references in the attribute table - these are resolved lazily (when required).
        """
        from .get_input_class import get_input_class
        cmd_txt = f'{self.bs.lhs} == {self.ctx.translate(self.bs.rhs)}' if self.bs.rhs else self.bs.lhs
        deferred = getattr(self.ctx, 'file_resolution', 'eager') == 'deferred'
        run_config = from_config(self.config) if deferred else self.config
        if deferred:
            run_config.file_resolution = 'deferred'
            run_config.variables = self.ctx.translate
        source_command = self.bs.command()
        from ..parsers.command import EventCommand
        # Keep the source file, original command position and event metadata.
        if isinstance(source_command, EventCommand):
            self._command = EventCommand(
                cmd_txt, run_config, source_command.parent, source_command.part_index,
            )
            self._command.event_name = source_command.event_name
        else:
            self._command = source_command.__class__(
                cmd_txt, run_config, source_command.parent,
                source_command.part_index, source_command.line_number,
            )
        self._command.define_blocks = source_command.define_blocks
        # A plain Command expands its value in the constructor. On the
        # opt-in deferred batch path, avoid repeating that work only when
        # no event or DEFINE blocks can change the expansion.
        if not (deferred and getattr(self.ctx, '_batch_active', False)
                and type(source_command) is Command
                and not source_command.define_blocks):
            self._command.reload_value()
        self._command.config.variables = self.ctx.translate
        self._rs = get_input_class(self._command)(self.bs.parent, self._command, load_control_files=False)  # Input representing the RunState
        # check all variable names in file have been resolved
        if deferred:
            # Inspect the context-expanded command text, not the absolute
            # reference path: a literal ancestor directory can legitimately
            # contain text matching a TEF event wildcard (e.g. '_event_').
            # Check only the contextual command expression. An absolute
            # parent folder may contain a literal TEF token such as _event_
            # and must never be mistaken for an unresolved command.
            # Eager contexts do not require output/check/log directories to
            # resolve as inputs. Preserve that boundary for syntax-only mode,
            # including nested ECF destinations with late-bound output aliases.
            command_resolved = self._command.is_value_a_folder() or self.ctx.is_resolved(
                str(self.ctx.translate(self.bs.rhs))
            )
            unresolved = [ref for ref in self.file_references if ref.unresolved_variables]
            if not command_resolved:
                unresolved.append(str(self._command.value))
        else:
            unresolved = [x for x in self.files if not self.ctx.is_resolved(x)]
        if unresolved:
            raise ResolveError('Input has not been completely resolved - {0}'.format(self.rhs))
