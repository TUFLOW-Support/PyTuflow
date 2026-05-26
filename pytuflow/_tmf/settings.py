import copy
import dataclasses
import typing
from pathlib import Path
from dataclasses import dataclass, field
import re
import platform

from .event import EventDatabase
from .tfpathlib import TuflowPath
from .gis import GisFormat


def set_prefer_gdal(value: bool):
    """Set whether to prefer GDAL or other Python libraries for GIS operations.

    For example, if set to False, geopandas using pyogrio will be preferred over GDAL for reading vector files.
    If geopandas is not found, then GDAL will be used as a fallback.

    Parameters
    ----------
    value : bool
        Whether to prefer GDAL for GIS operations.
    """
    from .gis import _set_prefer_gdal
    from .tfpathlib import set_prefer_gdal
    _set_prefer_gdal(value)
    set_prefer_gdal(value)


def get_cache_dir() -> str:
    """Return the cache directory for this package."""
    return str(Path.home() / '.tuflow_model_files')


@dataclasses.dataclass
class _ParseContext:
    """Mutable accumulator used exclusively during :meth:`TCFConfig.read_tcf`.

    All three parsing passes write into this object instead of the published
    ``TCFConfig`` instance, so ``TCFConfig`` fields are only updated once —
    atomically — after all passes (and any override) have completed.

    ``_ParseContext`` exposes the same attribute interface that
    ``Command``/``TuflowLine``/``TuflowValueExpander`` read from a settings
    object, so it can be passed as *config* to :func:`get_commands` and to
    :meth:`TCFConfig.from_tcf_config` without any special-casing.

    ``variables`` is intentionally passed by reference when seeding the
    context so that variable definitions accumulate and are immediately visible
    to later commands within the same pass.
    """
    tcf: Path = dataclasses.field(default_factory=TuflowPath)
    control_file: Path = dataclasses.field(default_factory=TuflowPath)
    spatial_database: Path = dataclasses.field(default_factory=TuflowPath)
    spatial_database_tcf: Path = dataclasses.field(default_factory=TuflowPath)
    projection_wkt: str = ''
    tif_projection: str = ''
    root_folder: Path = dataclasses.field(default_factory=TuflowPath)
    output_folder: Path = dataclasses.field(default_factory=TuflowPath)
    output_zones: list = dataclasses.field(default_factory=list)
    wildcards: list = dataclasses.field(default_factory=list)
    variables: dict = dataclasses.field(default_factory=dict)
    scenarios: list = dataclasses.field(default_factory=list)
    event_db: EventDatabase = dataclasses.field(default_factory=EventDatabase)
    errors: bool = False
    warning: bool = False
    model_name: str = ''
    gis_format: GisFormat = GisFormat.MIF
    grid_format: GisFormat = GisFormat.TIF
    check_file_prefix_1d: str = ''
    check_file_prefix_2d: str = ''

    def set_spatial_database(self, value: 'str | Path | None'):
        """Mirror of :meth:`TCFConfig.set_spatial_database`, operating on *self*."""
        value = str(value)
        if value.upper() == 'TCF':
            self.spatial_database = self.spatial_database_tcf
        elif value.upper() == 'NONE':
            self.spatial_database = TuflowPath()
            self.spatial_database_tcf = TuflowPath()
        else:
            self.spatial_database = self.control_file.parent / value

        if self.control_file.suffix.upper() == '.TCF':
            self.spatial_database_tcf = self.spatial_database


@dataclass
class TCFConfig:
    """Config class for parsing TUFLOW model files. Collects various settings from the TCF file in an initial
    pass of the TCF that can be passed into the TUFLOW model file parser e.g., variables, GIS projection, etc.

    This class also holds the current global settings defined in the TCF that can change depending on the cursor
    position in the TCF. An example of this is the spatial database which can be changed in the TCF which will
    affect the parsing of later control files.
    """
    tcf: str | Path | None = TuflowPath()
    control_file: Path = TuflowPath()
    spatial_database: Path = field(default_factory=TuflowPath, repr=False)
    spatial_database_tcf: Path = field(default_factory=TuflowPath, repr=False)
    projection_wkt: str = field(default='', repr=False)
    tif_projection: str = field(default='', repr=False)
    root_folder: Path = field(default_factory=TuflowPath, repr=False)
    output_folder: Path = field(default_factory=TuflowPath, repr=False)
    output_zones: list = field(default_factory=list, repr=False)
    wildcards: list = field(default_factory=list, repr=False)
    variables: dict | typing.Callable[[str], str] = field(default_factory=dict)
    scenarios: list = field(default_factory=list)
    event_db: EventDatabase = field(default_factory=EventDatabase)
    errors: bool = field(default=False, repr=False)
    warning: bool = field(default=False, repr=False)
    model_name: str = ''
    gis_format: GisFormat = GisFormat.MIF
    grid_format: GisFormat = GisFormat.TIF
    check_file_prefix_1d: str = field(default='', repr=False)
    check_file_prefix_2d: str = field(default='', repr=False)
    init_from_tcf: bool = field(default=True, repr=False)

    def __post_init__(self):
        if not self.wildcards:
            self.wildcards = [r'(<<.{1,}?>>)']
        self.tcf = TuflowPath(self.tcf) if self.tcf else TuflowPath()  # ensure tcf is a TuflowPath object
        if self.tcf != TuflowPath() and self.init_from_tcf:
            self.model_name = self.get_model_name(self.tcf)
            self.read_tcf()

    def __bool__(self):
        return self.tcf != Path()

    @staticmethod
    def from_tcf_config(config: 'TCFConfig | _ParseContext') -> 'TCFConfig':
        """Create a new TCFConfig snapshot from an existing TCFConfig or _ParseContext.

        ``variables`` is passed by reference so that variable definitions
        accumulated during pass 1 remain visible to later commands in the same
        pass (see :class:`TuflowValueExpander`).

        All other mutable collections are shallow-copied so that subsequent
        mutations to the source do not affect the snapshot.
        """
        return TCFConfig(
            tcf=config.tcf,
            control_file=config.control_file,
            spatial_database=config.spatial_database,
            spatial_database_tcf=config.spatial_database_tcf,
            projection_wkt=config.projection_wkt,
            tif_projection=config.tif_projection,
            root_folder=config.root_folder,
            output_folder=config.output_folder,
            output_zones=list(config.output_zones),
            wildcards=list(config.wildcards),
            variables=config.variables,  # intentionally shared — live dict for variable expansion
            scenarios=list(config.scenarios),
            event_db=config.event_db.copy(),
            model_name=config.model_name,
            gis_format=config.gis_format,
            grid_format=config.grid_format,
            check_file_prefix_1d=config.check_file_prefix_1d,
            check_file_prefix_2d=config.check_file_prefix_2d,
            init_from_tcf=False
        )

    @staticmethod
    def get_model_name(tcf):
        """Extract the model name from the tcf minus all the wildcards."""
        p1 = r'[_\s]?~[es]\d?~'
        p2 = r'~[es]\d?~[_\s]?'
        m1 = re.sub(p1, '', tcf.name, flags=re.IGNORECASE)
        m2 = re.sub(p2, '', tcf.name, flags=re.IGNORECASE)
        if m1.count('_') != m2.count('_'):
            model_name = m1 if m1.count('_') > m2.count('_') else m2
        else:
            model_name = m1

        if model_name[-1] == '_':
            model_name = model_name[:-1]

        return str(Path(model_name).with_suffix(''))

    def read_tcf(self):
        """Routine to make an initial read of the TCF to extract some settings.

        All three passes write into a private :class:`_ParseContext` rather
        than ``self`` directly.  ``self`` is only updated once all passes (and
        any ``_TUFLOW_Override``) have finished, so the published
        ``TCFConfig`` is never seen in a partially-initialised state.
        """
        ctx = _ParseContext(
            tcf=self.tcf,
            control_file=self.tcf,
            # Seed with any values already set on self (e.g. by callers who
            # pre-populated variables before constructing the TCFConfig).
            variables=dict(self.variables),
            wildcards=list(self.wildcards),
            model_name=self.model_name,
        )
        ctx = self._run_tcf_passes(ctx)
        self._apply_context(ctx)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_tcf_passes(self, ctx: _ParseContext) -> _ParseContext:
        """Run all three parsing passes on *ctx* and return the final context.

        If a ``_TUFLOW_Override`` file is found, an override context is seeded
        from the accumulated *ctx* and the passes are run recursively on it.
        The override context (which includes all accumulated state from both
        the base TCF and the override) is then returned in place of *ctx*.
        """
        from .inp.event import EventInput
        from .parsers.command import EventCommand

        # Pass 1 — variable definitions
        self.read_file_for_variables(ctx.control_file, ctx)
        ctx.set_spatial_database(None)

        # Pass 2 — event database
        event_text, event_name = self.read_file_for_event_db(ctx.control_file, ctx)
        if event_name and event_text:
            inp = EventInput(None, EventCommand(f'BC Event Source == {event_text} | {event_name}', ctx))
            ctx.event_db.inputs.append(inp)
        ctx.set_spatial_database(None)

        # Pass 3 — projection, formats, zones, wildcards
        self.read_file_for_config(ctx.control_file, ctx)
        ctx.set_spatial_database(None)

        # Optional _TUFLOW_Override
        tcf_override = self.tuflow_override(ctx.tcf)
        if tcf_override:
            # Seed the override context from the fully accumulated base state.
            # variables and event_db are shared by reference so that override
            # additions merge additively with what the base TCF accumulated.
            override_ctx = _ParseContext(
                tcf=tcf_override,
                control_file=tcf_override,
                variables=ctx.variables,           # shared — additive merging
                event_db=ctx.event_db,             # shared — additive merging
                wildcards=list(ctx.wildcards),
                output_zones=list(ctx.output_zones),
                scenarios=list(ctx.scenarios),
                projection_wkt=ctx.projection_wkt,
                tif_projection=ctx.tif_projection,
                gis_format=ctx.gis_format,
                grid_format=ctx.grid_format,
                check_file_prefix_1d=ctx.check_file_prefix_1d,
                check_file_prefix_2d=ctx.check_file_prefix_2d,
                model_name=ctx.model_name,
            )
            ctx = self._run_tcf_passes(override_ctx)

        return ctx

    def _apply_context(self, ctx: _ParseContext):
        """Publish all accumulated parse results to *self* in one dict update.

        Using ``self.__dict__.update`` collapses the 16 individual attribute
        stores into a single C-level dict update, reducing the window during
        which another thread could observe a partially-initialised instance.
        """
        self.__dict__.update({
            'control_file': ctx.tcf,
            'variables': ctx.variables,
            'event_db': ctx.event_db,
            'spatial_database': ctx.spatial_database,
            'spatial_database_tcf': ctx.spatial_database_tcf,
            'projection_wkt': ctx.projection_wkt,
            'tif_projection': ctx.tif_projection,
            'root_folder': ctx.root_folder,
            'output_folder': ctx.output_folder,
            'gis_format': ctx.gis_format,
            'grid_format': ctx.grid_format,
            'wildcards': ctx.wildcards,
            'output_zones': ctx.output_zones,
            'scenarios': ctx.scenarios,
            'check_file_prefix_1d': ctx.check_file_prefix_1d,
            'check_file_prefix_2d': ctx.check_file_prefix_2d,
        })

    # ------------------------------------------------------------------
    # Parsing passes  (accept an explicit ctx so they do not mutate self)
    # ------------------------------------------------------------------

    def read_file_for_variables(self, control_file: Path, ctx: _ParseContext):
        """Search for variable definitions in *control_file* and any Read File
        inclusions, accumulating results into *ctx*."""
        from .parsers.non_recursive_basic_parser import get_commands
        for command in get_commands(control_file, ctx):
            if command.is_read_file() and not command.in_scenario_block():
                self.read_file_for_variables(ctx.control_file.parent / command.value, ctx)
            elif command.is_set_variable() and not command.in_scenario_block():
                var_name, var_val = command.parse_variable()
                ctx.variables[var_name] = var_val

    def read_file_for_event_db(self, control_file: Path, ctx: _ParseContext) -> tuple[str, str]:
        """Scan *control_file* for event definitions, accumulating results into
        *ctx*.

        Returns
        -------
        tuple[str, str]
            ``(event_text, event_name)`` — the values of any top-level
            ``BC Event Text`` / ``BC Event Name`` commands found outside a
            ``Define Event`` block (consumed by the caller to create a
            synthetic ``BC Event Source`` entry).
        """
        from .parsers.non_recursive_basic_parser import get_commands
        from .parsers.command import EventCommand
        from .cf.tef import TEF
        from .inp.event import EventInput
        event_text = ''
        event_name = ''
        for command in get_commands(control_file, ctx):
            if command.is_read_file() and not command.in_scenario_block():
                child_et, child_en = self.read_file_for_event_db(ctx.control_file.parent / command.value, ctx)
                # last non-empty value wins, matching the original accumulation behaviour
                if child_en:
                    event_name = child_en
                if child_et:
                    event_text = child_et
            elif command.is_event_file():
                event_file = ctx.control_file.parent / command.value
                ctx.event_db.update(TEF.parse_event_file(event_file, ctx))
            elif command.is_event_source():
                event_command = EventCommand.from_command(command)
                inp = EventInput(None, event_command)
                ctx.event_db.inputs.append(inp)
                if inp.event_name:
                    if inp.event_name not in ctx.event_db:
                        ctx.event_db[inp.event_name] = {inp.event_var: inp.event_value}
                    else:
                        ctx.event_db[inp.event_name][inp.event_var] = inp.event_value
            elif command.is_bc_event_name():
                event_name = command.value
            elif command.is_bc_event_text():
                event_text = command.value
        return event_text, event_name

    def set_spatial_database(self, value: str | Path | None):
        value = str(value)
        if value.upper() == 'TCF':
            self.spatial_database = self.spatial_database_tcf
        elif value.upper() == 'NONE':
            self.spatial_database = TuflowPath()
            self.spatial_database_tcf = TuflowPath()
        else:
            self.spatial_database = self.control_file.parent / value

        if self.control_file.suffix.upper() == '.TCF':
            self.spatial_database_tcf = self.spatial_database

    @staticmethod
    def tuflow_override(tcf: Path) -> Path | None:
        if tcf.stem.lower().startswith('_tuflow_override'):
            return None
        comp_name = platform.node()
        tcf_override = tcf.parent / f'_TUFLOW_Override_{comp_name}.tcf'
        if tcf_override.exists():
            return tcf_override
        tcf_override = tcf.parent / f'_TUFLOW_Override.tcf'
        if tcf_override.exists():
            return tcf_override
        return None

    def read_file_for_config(self, control_file: Path, ctx: _ParseContext):
        """Scan *control_file* for projection, format, zone, and wildcard
        settings, accumulating results into *ctx*."""
        from .parsers.command import EventCommand
        from .parsers.non_recursive_basic_parser import get_commands
        from .gis import ogr_projection, gdal_projection, GisFormat

        gis_format = {'GPKG': GisFormat.GPKG, 'SHP': GisFormat.SHP, 'ASC': GisFormat.ASC,
                      'TIF': GisFormat.TIF, 'FLT': GisFormat.FLT, 'NC': GisFormat.NC,
                      'MIF': GisFormat.MIF}
        for command in get_commands(control_file, ctx):
            event_command = EventCommand(command.original_text, ctx)
            # spatial database
            if command.is_spatial_database_command():
                ctx.set_spatial_database(command.value)
            # projection
            elif command.is_read_projection():
                try:
                    ctx.projection_wkt = ogr_projection(command.value_expanded_path or command.value)
                except (ImportError, FileNotFoundError, RuntimeError):
                    continue
            # tif projection
            elif command.is_tif_projection():
                try:
                    ctx.tif_projection = gdal_projection(command.value_expanded_path or command.value)
                except (ImportError, FileNotFoundError, RuntimeError):
                    continue
            # gis format
            elif command.is_gis_format():
                ctx.gis_format = gis_format.get(command.value.upper(), GisFormat.Unknown)
            # grid format
            elif command.is_grid_format():
                ctx.grid_format = gis_format.get(command.value.upper(), GisFormat.Unknown)
            # event source
            elif event_command.is_event_source():
                event_wildcard, _ = event_command.get_event_source()
                if event_wildcard is not None and re.escape(event_wildcard) not in ctx.wildcards:
                    ctx.wildcards.append(re.escape(event_wildcard))
            # output zones
            elif command.is_output_zone():
                ctx.output_zones.extend(command.specified_output_zones())
            # read file / event file
            elif command.is_read_file() or command.is_event_file():
                self.read_file_for_config(ctx.control_file.parent / command.value, ctx)
