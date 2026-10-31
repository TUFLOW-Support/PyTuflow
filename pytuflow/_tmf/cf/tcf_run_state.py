import logging
import os
import typing
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .cf_run_state import ControlFileRunState
from ..abc.tcf_base import TCFBase
from ..tmf_types import PathLike
from ..tuflow_binaries import tuflow_binaries
from ..context import Context
from ..abc.tf_cf_base_mixin import TuflowControlFileMixin
from .model_run_mixin import ModelRunMixin



logger = logging.getLogger('pytuflow')


@dataclass(frozen=True, slots=True)
class _IndexedRunInput:
    """One input in find_input() order, including reference-free commands.

    The input is borrowed, never shared across runs. Only a synchronous batch
    may reuse this identity snapshot: InputRunState remains publicly mutable.
    """
    sequence: int
    input_uuid: str
    input_state: 'InputRunState'


@dataclass(frozen=True, slots=True)
class _RunInputIndex:
    """Index the ordered run inputs by UUID without sharing mutable run state."""

    ordered: tuple[_IndexedRunInput, ...]
    by_uuid: Mapping[str, tuple[_IndexedRunInput, ...]]


if typing.TYPE_CHECKING:
    from pytuflow import TPC
    from ..file_reference import DeferredDatabaseSource
    from ..inp.inp_run_state import InputRunState
    from .tcf import TCF
    from .tef_run_state import TEFRunState
    from ..db.bc_dbase_run_state import BCDatabaseRunState
    from ..db.mat import MatDatabaseRunState
    from ..db.soil import SoilDatabase
    from ..db.db_run_state import DatabaseRunState


class TCFRunState(ControlFileRunState, TuflowControlFileMixin, ModelRunMixin, TCFBase):
    """Class for storing the run state of a TCF file.

    This class should not be instantiated directly, but rather it should be created from an instance
    of a BuildState class using the :meth:`context()<pytuflow.TCF.context>` method of the BuildState class.

    Parameters
    ----------
    build_state : TCF
        The TCF build state instance that the RunState object is based on.
    context : Context
        The context instance that will be used to resolve the build state.
    parent : ControlFileRunState
        The parent control file run state.
    """
    def __init__(self, build_state: 'TCF', context: Context, parent: ControlFileRunState | None):
        #: TCF: the BuildState object that the RunState object is based on.
        self.bs = build_state
        #: subprocess.Popen: the process that is running the TUFLOW simulation.
        self.proc = None

        self._tpc = None  # cached TPC result

        super(TCFRunState, self).__init__(build_state, context, parent)

    def tgc(self) -> ControlFileRunState:
        """Returns the model's TGC ControlFileRunState instance.

        Returns
        -------
        ControlFileRunState
            The TGC ControlFileRunState instance.

        Raises
        ------
        KeyError
            If the Geometry Control File is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tgc = tcf.context().tgc()
        """
        return super().tgc()

    def tbc(self) -> ControlFileRunState:
        """Returns the model's TBC ControlFileRunState instance.

        Returns
        -------
        ControlFileRunState
            The TBC ControlFileRunState instance.

        Raises
        ------
        KeyError
            If the BC Control File is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tbc = tcf.context().tbc()
        """
        return super().tbc()

    def ecf(self) -> 'ControlFileRunState':
        """Returns the model's ECF ControlFileRunState instance.

        Returns
        -------
        ControlFileRunState
            The ECF ControlFileRunState instance.

        Raises
        ------
        KeyError
            If the ESTRY Control File is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> ecf = tcf.context().ecf()
        """
        return super().ecf()

    def tscf(self) -> 'ControlFileRunState':
        """Returns the model's TSCF ControlFileRunState instance.

        Returns
        -------
        ControlFileRunState
            The TSCF ControlFileRunState instance.

        Raises
        ------
        KeyError
            If the SWMM Control File is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tscf = tcf.context().tscf()
        """
        return super().tscf()

    def tef(self) -> 'TEFRunState':
        """Returns the model's TEFRunState instance.

        Returns
        -------
        TEFRunState
            The TEFRunState instance.

        Raises
        ------
        KeyError
            If the Event File is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tef = tcf.context().tef()
        """
        return super().tef()

    def bc_dbase(self) -> 'BCDatabaseRunState':
        """Returns the model's BCDatabaseRunState instance.

        Returns
        -------
        BCDatabaseRunState
            The BCDatabaseRunState instance.

        Raises
        ------
        KeyError
            If the bc_dbase is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> bc_dbase = tcf.context().bc_dbase()
        """
        return super().bc_dbase()

    def mat_file(self) -> 'MatDatabaseRunState':
        """Returns the model's MatDatabaseRunState instance.

        Returns
        -------
        MatDatabaseRunState
            The MatDatabaseRunState instance.

        Raises
        ------
        KeyError
            If the material file is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> mat_file = tcf.context().mat_file()
        """
        return super().mat_file()

    def soils_file(self) -> 'SoilDatabase':
        """Returns the model's SoilDatabase instance.

        Returns
        -------
        SoilDatabase
            The SoilDatabase instance.

        Raises
        ------
        KeyError
            If the soil file is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> soils_file = tcf.context().soils_file()
        """
        return super().soils_file()

    def rainfall_dbase(self) -> 'DatabaseRunState':
        """Returns the model's rainfall database instance.

        Returns
        -------
        DatabaseRunState
            The rainfall database instance.

        Raises
        ------
        KeyError
            If the rainfall database file is not found in the control file.

        Example
        -------
        >>> tcf = ... # assuming is an instance of TCF
        >>> rainfall_dbase = tcf.context().rainfall_dbase()
        """
        return super().rainfall_dbase()

    def _deferred_run_input_index(self) -> _RunInputIndex:
        """Create an ordered UUID index, with batch-only reuse.

        The public run-state API permits input/command mutation, so ordinary
        eager/deferred contexts always take a fresh snapshot per operation.
        During batch collection the per-run state is private, read
        synchronously, and discarded after that run. Only in that
        explicitly bounded lifecycle can the index safely be reused. No
        InputRunState, index or cache is shared across contexts or batches.

        A UUID maps to *all* matching entries, not just the last one. This
        retains the existing rejection of ambiguous/missing activation IDs.
        """
        batch_lifecycle = getattr(self.ctx, '_batch_run_index', None) is not None
        if batch_lifecycle:
            cached = getattr(self, '_batch_deferred_run_input_index', None)
            if cached is not None:
                return cached

        ordered = tuple(
            _IndexedRunInput(sequence, str(inp.uuid), inp)
            for sequence, inp in enumerate(self.find_input())
        )
        grouped: dict[str, list[_IndexedRunInput]] = {}
        for entry in ordered:
            grouped.setdefault(entry.input_uuid, []).append(entry)
        index = _RunInputIndex(
            ordered,
            MappingProxyType({uuid: tuple(entries) for uuid, entries in grouped.items()}),
        )
        if batch_lifecycle:
            self._batch_deferred_run_input_index = index
        return index

    def deferred_database_activations(self):
        """List scoped database declarations in syntactic control-file order.

        A BC Database may be reassigned during a TCF/TBC/ECF. It is therefore
        incorrect to select the first occurrence or treat all declarations
        as one global table. This immutable activation stream preserves
        the model's active command order and source ownership; selecting
        row identifiers for a particular GIS/BC command is a separate
        downstream materialisation step.

        Initial control-file parsing may perform I/O; this accessor does not.
        """
        from ..file_reference import DeferredDatabaseActivation

        if getattr(self.ctx, 'file_resolution', 'eager') != 'deferred':
            raise ValueError('deferred_database_activations requires deferred mode')

        activations = []
        for entry in self._deferred_run_input_index().ordered:
            inp = entry.input_state
            for ref in inp.file_references:
                if not ref.requires_database_scan:
                    continue
                if ref.unresolved_variables or ref.requires_directory_scan:
                    raise ValueError(
                        f'Cannot establish database activation: {ref.path_pattern}'
                    )
                if ref.database_kind is None or ref.database_kind == 'unknown':
                    raise ValueError(
                        f'Unclassified database activation: {ref.path_pattern}'
                    )
                activations.append(DeferredDatabaseActivation(
                    sequence=entry.sequence,
                    input_uuid=entry.input_uuid,
                    database_kind=ref.database_kind,
                    database_path=ref.path_pattern,
                    owning_command=ref.origin,
                    owner_control_file=inp._command.parent,
                    line_number=inp.line_number,
                ))
        return tuple(activations)

    @staticmethod
    def _deferred_sources_for_input(inp, kind, primary):
        """Project cached secondary rows while preserving declaration UUID."""
        from ..file_reference import DeferredDatabaseSource

        if primary.unresolved_variables or primary.requires_directory_scan:
            raise ValueError(f'Cannot inspect unresolved primary database: {primary.path_pattern}')
        result = []
        for source in inp.database_source_references:
            if (source.unresolved_variables or source.requires_database_scan
                    or source.requires_attribute_scan
                    or (source.layer_pattern is not None and kind != 'ad_global')):
                raise ValueError(f'Unsupported secondary database reference: {source.path_pattern}')
            prefix = f'{kind} database row '
            row = source.origin.removeprefix(prefix)
            if not source.origin.startswith(prefix) or not row:
                raise ValueError(f'Cannot identify database entry: {source.origin}')
            result.append(DeferredDatabaseSource(
                primary.path_pattern, kind,
                (row.rsplit(' / ', 1)[0] if kind == 'ad_global' else row),
                source.path_pattern,
                owning_command=primary.origin,
                owner_control_file=inp._command.parent,
                layer_pattern=source.layer_pattern,
                source_field=(source.origin.rsplit(' / ', 1)[-1]
                              if kind == 'ad_global' else None),
                requires_layer_scan=source.requires_layer_scan,
                requires_directory_scan=source.requires_directory_scan,
                requires_raster_metadata_scan=source.requires_raster_metadata_scan,
                input_uuid=str(inp.uuid),
                csv_columns=source.csv_columns,
            ))
        return tuple(result)

    def deferred_database_sources_for_activation(self, input_uuid: str):
        """Return cached Source rows for exactly one selected declaration.

        Consumers first pair a boundary/GIS command with its active database
        using deferred_database_activations(). They can then inspect this
        activation's source rows without merging unrelated BC databases.
        A duplicate UUID, missing declaration or unsupported schema fails
        closed. No additional file, GIS, SQLite or directory I/O is done.
        """
        if getattr(self.ctx, 'file_resolution', 'eager') != 'deferred':
            raise ValueError('deferred_database_sources_for_activation requires deferred mode')
        matches = self._deferred_run_input_index().by_uuid.get(str(input_uuid), ())
        if len(matches) != 1:
            raise ValueError(
                f'Expected exactly one database input for activation {input_uuid}, '
                f'found {len(matches)}'
            )
        inp = matches[0].input_state
        primaries = [ref for ref in inp.file_references if ref.requires_database_scan]
        if len(primaries) != 1:
            raise ValueError(f'Cannot identify database for activation {input_uuid}')
        primary = primaries[0]
        kind = primary.database_kind
        if kind is None or kind == 'unknown':
            raise ValueError(f'Unsupported database kind for activation {input_uuid}')
        return self._deferred_sources_for_input(inp, kind, primary)

    def deferred_database_sources(self):
        """Describe active database secondary files using cached parsed rows.

        Explicitly requesting this view does not open any database, create
        database run-state objects or materialise GIS inputs. All paths are
        syntactic; the consumer must validate and deduplicate them in bulk.
        Unsupported schemas, ambiguous databases and unexpanded variables
        raise rather than returning an incomplete dependency set.
        """
        from ..file_reference import DeferredDatabaseSource

        if getattr(self.ctx, 'file_resolution', 'eager') != 'deferred':
            raise ValueError('deferred_database_sources requires deferred mode')

        return self.database_sources()

    def database_sources(self) -> tuple['DeferredDatabaseSource', ...]:
        """Return typed secondary sources from context-resolved cached databases.

        Available in eager and deferred contexts. Input.files enumerates the
        input's own files; this explicit projection additionally describes AD
        sources and candidate curve rows. Consumers must select curve IDs from
        active GIS features instead of requiring every candidate curve file.
        Parsing, variable expansion and source ownership stay in PyTUFLOW.
        This accessor does not open source files or inspect GIS features.
        """
        result = []
        for kind, names in (
            ('bc', ('bc database',)),
            ('ad_bc', ('ad bc database',)),
            ('ad_global', ('ad global database',)),
            ('pit_inlet', ('pit inlet database',)),
            ('depth_discharge', ('depth discharge database',)),
            ('cross_section', ('xs database', 'read xs database')),
            ('materials', ('read materials file', 'read material file')),
            ('soils', ('read soil file', 'read soils file')),
            ('rainfall', ('read grid rf',)),
        ):
            # A substring lookup for 'BC Database' incorrectly includes
            # 'AD BC Database'. Roles must be selected independently.
            inputs = self.find_input(
                callback=lambda inp: inp.lhs.strip().casefold() in names,
            )
            lhs = names[0]
            if not inputs:
                continue
            # Rainfall and materials inputs are additive. Material files
            # with separate roughness classes are explicitly supported by
            # TUFLOW, and each distinct source contributes dependencies.
            # Stateful BC selection requires separate activation handling.
            if len(inputs) != 1 and kind not in ('rainfall', 'materials'):
                raise ValueError(f'Multiple active {lhs} inputs need disambiguation')
            for inp in inputs:
                if kind == 'rainfall' and len(inp.file_references) == 1:
                    netcdf = inp.file_references[0]
                    if netcdf.database_kind == 'rainfall_netcdf':
                        # A NetCDF rainfall grid is the whole source, not an
                        # index with secondary files to materialise.
                        continue
                primaries = [ref for ref in inp.file_references
                             if ref.requires_database_scan and ref.database_kind == kind]
                if len(primaries) != 1:
                    raise ValueError(f'Cannot uniquely identify primary {lhs} path')
                primary = primaries[0]
                if primary.unresolved_variables or primary.requires_directory_scan:
                    raise ValueError(f'Cannot inspect unresolved primary database: {primary.path_pattern}')
                result.extend(self._deferred_sources_for_input(inp, kind, primary))
        return tuple(result)

    def output_name(self) -> str:
        """Returns the file name of the result file without any extension.

        Returns
        -------
        str
            Name of the result file.

        Examples
        --------
        >>> tcf = TCF('/path/to/EG16_~s1~_~s2~_002.tcf')
        >>> tcf.context('-s1 5m -s2 EXG').output_name()
        'EG16_5m_EXG_002'
        """
        return self.ctx.translate_result_name(self.fpath.name)

    def tpc(self) -> 'TPC':
        """Returns the TPC result from the simulation.

        Returns
        -------
        TPC
            The TPC result.

        Examples
        --------
        >>> tcf = TCF('/path/to/EG15_001.tcf')
        >>> tpc = tcf.context().tpc()
        >>> tpc.ids()
        ['FC01.1_R.1',
         'FC01.1_R.2',
         'FC01.2_R.1',
         ...
         'Pipe8',
         'Pipe9']
        """
        if self._tpc is not None:
            return self._tpc

        try:
            from ....._outputs.tpc import TPC
        except ImportError:
            logger.error('Cannot import TPC from pytuflow.results. This method can only used when tmf has been '
                         'installed via the PyTuflow library.')
            raise ImportError('Cannot import TPC from pytuflow.results. This method can only used when tmf has been '
                              'installed via the PyTuflow library.')
        self._tpc = TPC(self.tpc_path())
        return self._tpc

    def tpc_path(self) -> Path:
        """Returns the path to the expected tpc file. Does not check it exists.

        Returns
        -------
        Path
            File path to the tpc file.

        Examples
        --------
        >>> tcf = TCF('/path/to/EG15_001.tcf')
        >>> tcf.context().tpc_path()
        WindowsPath('../results/EG15/plot/EG15_001.tpc')
        """
        return (self.output_folder_2d() / 'plot' / self.output_name()).with_suffix('.tpc')

    def tlf_path(self) -> Path:
        """Returns the path to the expected tlf file. Does not check it exists.

        Returns
        -------
        Path
            File path to the tlf file.

        Examples
        --------
        >>> tcf = TCF('/path/to/EG15_001.tcf')
        >>> tcf.context().tlf_path()
        WindowsPath('./log/EG15_001.tlf')
        """
        return (self.log_folder_path() / self.output_name()).with_suffix('.tlf')

    def run(self, tuflow_bin: PathLike, prec: str = 'sp', add_cli_args: list[str] = (), *args, **kwargs):
        """Run the control file in context using the specified TUFLOW binary.

        * TUFLOW binary can be a file path to the executable or a version name that has been registered using
          the :func:`register_tuflow_binary function()<pytuflow.register_tuflow_binary>`
          or the :func:`register_tuflow_binary_folder()<pytuflow.register_tuflow_binary_folder>`.

        Additional arguments can be passed in and will be passed to the subprocess.Popen() call. By default,
        a new console will be created for the subprocess.

        Parameters
        ----------
        tuflow_bin : PathLike
            Path to the TUFLOW binary or a registered version name.
        prec : str, optional
            Precision of the run. Default is ``"sp"`` (single precision).
            Alternate option is ``"dp"`` (double precision) (accepted aliases ``"idp"`` and ``"double"``).
        add_cli_args : list[str]
            A list of additional command line arguments specific to TUFLOW that will be passed directly to the
            subprocess.Popen() call. e.g. ``add_cli_args=['-t']`` to pass in the ``-t`` flag to run TUFLOW in test mode,
            or ``add_cli_args=['-cs1']`` to pass in the ``-cs1`` flag to run TUFLOW with case-insensitive file paths.
        *args, **kwargs:
            Will be passed to subprocess.Popen() call.

        Returns
        -------
        subprocess.Popen
            The subprocess.Popen object that is created when the control file is run.

        Examples
        --------
        >>> tcf = ... # assuming is an instance of TCF
        >>> tcf.context().run('2025.1.2')
        <Popen: returncode: None args: ['C:\\TUFLOW\\releases\\2025.1.2\\TUFLOW_iSP_...>
        """
        tuflow_bin_ = self._find_tuflow_bin(tuflow_binaries, tuflow_bin, prec)
        if '-b' not in add_cli_args:
            add_cli_args = list(add_cli_args)
            add_cli_args.insert(0, '-b')
        return self._run(self.fpath, tuflow_bin_, self.ctx.context_args, add_cli_args, *args, **kwargs)

    def test(self, tuflow_bin: PathLike, prec: str = 'sp') -> tuple[str, str]:
        """Run the control file in context using the specified TUFLOW binary in test mode.

        The stdout and stderr are automatically captured (no console window is produced) and once complete, the
        return values are the captured stdout and stderr.

        Parameters
        ----------
        tuflow_bin : PathLike
            File path to the TUFLOW binary or a registered version name.
        prec : str, optional
            Precision of the run. Default is ``"sp"`` (single precision).
            Alternate option is to use ``"dp"`` (double precision) (accepted aliases ``"idp"`` and ``"double"``).

        Returns
        -------
        tuple[str, str]
            Captured stdout and stderr from the run.

        Examples
        --------
        >>> tcf = ... # assuming is an instance of TCF
        >>> stdout, stderr = tcf.context().test('2025.1.2')
        >>> print(stderr)
        NoXY: ERROR 2131 - Reading parameter(s) or option for .tcf command below, or command is ambiguous.
        """
        kwargs = {}
        if os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        proc = self.run(tuflow_bin, prec, add_cli_args=['-t', '-nmb'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        out, err = proc.communicate()
        if isinstance(out, bytes):
            out = out.decode('utf-8')
        if isinstance(err, bytes):
            err = err.decode('utf-8')
        return out, err
