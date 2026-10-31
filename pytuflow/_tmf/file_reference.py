"""Immutable syntactic input-file references for deferred TUFLOW contexts.

References are not existence assertions. A caller can aggregate them across
contexts and inspect paths, database layers and GIS attributes in bulk.
"""

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .options import CaseSensitivity
from .parsers.command import Command
from .tfpathlib import TuflowPath
from .tfstrings.patterns import globify


def _cached_filename_matches(
    filename: str, pattern: str, case_sensitivity: CaseSensitivity
) -> bool:
    """Match cached names under TUFLOW's filename-only -cs policy."""
    if os.name == "nt":
        return fnmatch.fnmatchcase(filename.casefold(), pattern.casefold())
    if case_sensitivity == CaseSensitivity.STRICT:
        return fnmatch.fnmatchcase(filename, pattern)
    if case_sensitivity == CaseSensitivity.EXTENSION_INSENSITIVE:
        return (
            fnmatch.fnmatchcase(filename.casefold(), pattern.casefold())
            and fnmatch.fnmatchcase(Path(filename).stem, Path(pattern).stem)
        )
    if case_sensitivity == CaseSensitivity.FILENAME_INSENSITIVE:
        return fnmatch.fnmatchcase(filename.casefold(), pattern.casefold())
    raise ValueError(f"Unsupported TUFLOW filename case policy: {case_sensitivity}")


def _cached_path_matches(path: Path, pattern: Path, case_sensitivity: CaseSensitivity) -> bool:
    """Match parsed paths lexically, without filesystem I/O.

    Linux directories remain case-sensitive in every -cs mode. Only the
    basename follows the configured filename policy.
    """
    parts = Path(os.path.normpath(str(path))).parts
    wanted = Path(os.path.normpath(str(pattern))).parts
    if len(parts) != len(wanted):
        return False
    for actual, expected in zip(parts[:-1], wanted[:-1], strict=True):
        if os.name == "nt":
            actual, expected = actual.casefold(), expected.casefold()
        if not fnmatch.fnmatchcase(actual, expected):
            return False
    return _cached_filename_matches(parts[-1], wanted[-1], case_sensitivity)


@dataclass(frozen=True)
class FileReference:
    """Context-expanded source-file pattern and deferred inspection requirements."""

    base_directory: Path
    expanded_value: str
    path_pattern: Path
    layer_pattern: str | None
    origin: str
    requires_directory_scan: bool
    requires_layer_scan: bool
    requires_attribute_scan: bool
    requires_database_scan: bool
    unresolved_variables: tuple[str, ...] = ()
    database_kind: str | None = None
    requires_table_link_scan: bool = False
    requires_raster_metadata_scan: bool = False
    # Resolved time/value names for ordinary BC CSVs; empty means unsupported.
    csv_columns: tuple[str, ...] | None = None


@dataclass(frozen=True)
class DeferredDatabaseActivation:
    """Database declaration in the context-specific ordered command stream.

    This is an activation record, not permission to merge Source rows from
    unrelated BC databases. Consumers can join the sequence/UUID to active
    GIS and boundary inputs before selecting the correct database. The run
    has already applied event/scenario scope filtering. No disk/GIS reads.
    """

    sequence: int
    input_uuid: str
    database_kind: str
    database_path: Path
    owning_command: str
    owner_control_file: Path | None
    line_number: int | None


@dataclass(frozen=True)
class DeferredDatabaseSource:
    """Context-resolved secondary input from a cached, parsed database.

    The primary database file remains a normal FileReference. A Source is
    a syntactic file pattern, not an existence assertion. No file is opened
    while creating this record from an already loaded build-state database.
    """

    database_path: Path
    database_kind: str
    entry_name: str
    path_pattern: Path
    owning_command: str = ''
    owner_control_file: Path | None = None
    layer_pattern: str | None = None
    source_field: str | None = None
    requires_layer_scan: bool = False
    requires_directory_scan: bool = False
    requires_raster_metadata_scan: bool = False
    # Resolved time/value names for ordinary BC CSVs; empty means unsupported.
    csv_columns: tuple[str, ...] | None = None
    input_uuid: str = ''


def make_file_reference(command: Command) -> FileReference:
    """Construct a reference lexically, without filesystem or GIS probes."""
    # The path-expanded value includes an active Spatial Database for GIS
    # layer-only syntax (e.g. Read GIS Code == 2d_code). Command.value alone
    # does not include its GeoPackage filename. Deferred path expansion is
    # lexical and does not scan the filesystem or open the database.
    # Keep unresolved-variable detection scoped to the command expression:
    # its owning absolute directory may contain a literal TUFLOW token.
    value = str(command.value).strip()
    expanded = (str(command.value_expanded_path).strip()
                if command.value_expanded_path is not None else value)
    db, layer = TuflowPath(expanded)._split_db_and_lyr()
    owner = command.parent
    base = (Path(owner).parent if owner and owner != Path() else Path.cwd()).absolute()
    # Match wildcard tokens in only the portion supplied by the command,
    # never an ancestor of the owning control file. Absolute paths produced
    # by the parser can contain literal event-like tokens in their parents.
    expanded_path = Path(db)
    if expanded_path.is_absolute():
        try:
            relative = expanded_path.relative_to(base)
        except ValueError:
            # Spatial Database may point outside the owning control folder.
            # Preserve its configured directories and only expand the leaf.
            source_pattern = str(globify(expanded_path.name, command.config.wildcards))
            path = expanded_path.with_name(source_pattern)
        else:
            source_pattern = str(globify(str(relative), command.config.wildcards))
            path = base / source_pattern
    else:
        source_pattern = str(globify(db, command.config.wildcards))
        path = base / source_pattern
    path_glob = str(path)
    # A layerless GIS/Projection GeoPackage resolves to its stem-named layer
    # in eager TUFLOW materialisation. Preserve that requirement for
    # deferred consumers; omitting it would skip a required GPKG layer check.
    if layer is None and path.suffix.casefold() == '.gpkg' and (
        command.is_read_gis() or command.is_read_projection()
    ):
        layer = path.stem
    layer_glob = str(globify(layer, command.config.wildcards)) if layer is not None else None
    unresolved = tuple(dict.fromkeys(re.findall(r'<<[^<>]+>>', value)))
    # All GIS sources are candidates: their attributes may reference further
    # files, especially for 1D network and cross-section layers.
    layer_name = (layer or path.stem).lower()
    # Only layers likely to have file-valued fields need an attribute scan.
    # Unknown/wildcard names remain candidates, preserving dependency coverage.
    from .gis import tuflow_type_requires_feature_iter
    attr_scan = (command.is_table_link() or (command.is_read_gis() and not command.is_read_projection()
                 and (bool(tuflow_type_requires_feature_iter(layer_name))
                      or any(char in layer_name for char in '*?<[')
                      or layer_name == 'all')))
    if command.is_ad_bc_dbase_file():
        kind = 'ad_bc'
    elif command.is_bc_dbase_file():
        kind = 'bc'
    elif command.is_ad_global_database_file():
        kind = 'ad_global'
    elif command.is_mat_dbase():
        kind = 'materials'
    elif command.is_soil_dbase():
        kind = 'soils'
    elif command.is_depth_discharge_dbase_file():
        kind = 'depth_discharge'
    elif command.is_pit_inlet_dbase_file():
        kind = 'pit_inlet'
    elif command.is_table_link():
        kind = 'gis_table_links'
    elif command.is_xs_dbase():
        kind = 'cross_section'
    elif command.is_rainfall_grid():
        kind = 'rainfall_netcdf' if command.is_rainfall_grid_nc() else 'rainfall'
    elif command.is_read_database():
        kind = 'unknown'
    else:
        kind = None
    return FileReference(
        base_directory=base, expanded_value=expanded, path_pattern=Path(path_glob),
        layer_pattern=layer_glob, origin=command.command_orig,
        requires_directory_scan=any(char in source_pattern for char in '*?['),
        requires_layer_scan=layer_glob is not None,
        requires_attribute_scan=attr_scan,
        requires_database_scan=(command.is_read_database() and not command.is_rainfall_grid_nc()),
        unresolved_variables=unresolved, database_kind=kind,
        requires_table_link_scan=command.is_table_link(),
        requires_raster_metadata_scan=(command.is_read_grid() or command.is_rainfall_grid_nc()),
    )
