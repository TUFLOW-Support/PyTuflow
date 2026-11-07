"""Read-only, deduplicated discovery of TUFLOW GIS attribute-linked input files.

Only the declared file-valued field positions for recognised TUFLOW layer types
are inspected. GeoPackages are opened once per distinct file, not per run.
Unsupported sources/schemas remain unresolved rather than silently passing.
"""

from __future__ import annotations

import fnmatch
import math
import os
import re
import sqlite3
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dbfread import DBF

from ._tmf.gis import network_attribute_file_sources, tuflow_type_requires_feature_iter
from ._tmf.gis_attr_driver import GISAttributes
from ._tmf.gpkg_safety import readonly_gpkg
from ._tmf.tfpathlib import TuflowPath
from .validation import _shapefile_companions


@dataclass(frozen=True, slots=True)
class AttributeInspection:
    """Secondary file references or a reason the layer cannot be certified."""

    status: Literal["present", "unresolved"]
    sources: tuple[Path, ...] = ()
    identifiers: tuple[str, ...] = ()
    detail: str = ""
    network_identifiers: tuple[str, ...] = ()
    pit_identifiers: tuple[str, ...] = ()
    bc_identifiers: tuple[str, ...] = ()
    bc_layer_selected: bool = False


def _quote_identifier(value: str) -> str:
    """Quote only identifiers returned by the opened GeoPackage itself."""
    return '"' + value.replace('"', '""') + '"'


def _file_field_index(layer: str) -> int | None:
    """Use the original PyTUFLOW positional GIS-file attribute rules."""
    indexes = tuflow_type_requires_feature_iter(layer)
    if not indexes:
        return None
    if len(indexes) != 1:
        raise ValueError(f"Unsupported multi-column file references in {layer}")
    return indexes[0]


def _bc_name_field_index(layer: str) -> int | None:
    """TUFLOW §§8.3–8.4: Name is third in 1d/2d_bc, first in 2d_sa/rf."""
    if re.match(r"^[12]d_bc_", layer, re.IGNORECASE):
        return 2
    if re.match(r"^2d_(sa|rf)_", layer, re.IGNORECASE):
        return 0
    return None


def _one_d_bc_identifiers(rows: Iterable[Sequence[object]], layer: str) -> tuple[str, ...]:
    """Read Type/Flags/Name without treating automatic HQ slopes as database keys.

    This deliberately supports named HT/HQ/QT/QH boundaries. Other 1D types
    remain unresolved until their own dependency semantics are implemented.
    """
    names: set[str] = set()
    for attrs in rows:
        # Legacy 1d_bc T flag ignores the feature, including any Name value.
        if "T" in str(attrs[1] or "").upper():
            continue
        bc_type = str(attrs[0] or "").strip().upper()
        if bc_type not in {"HT", "HQ", "QT", "QH"}:
            raise ValueError(f"Unrecognised or unsupported 1d_bc Type {bc_type!r}: {layer}")
        value = attrs[2]
        if not isinstance(value, str) or not value.strip() or "<<" in value or ">>" in value:
            raise ValueError(f"Missing or unexpanded BC Name in {layer}: {value!r}")
        value = value.strip()
        if bc_type == "HQ" and re.match(r"^slope\s*=", value, re.IGNORECASE):
            try:
                slope = float(value.split("=", 1)[1].strip())
            except ValueError as exc:
                raise ValueError(f"Invalid automatic 1d_bc HQ slope in {layer}: {value!r}") from exc
            if not math.isfinite(slope) or slope <= 0:
                raise ValueError(f"Invalid automatic 1d_bc HQ slope in {layer}: {value!r}")
            continue
        names.add(value)
    return tuple(sorted(names, key=str.casefold))


def _bc_identifiers_from_rows(
    rows: Iterable[Sequence[object]], layer: str
) -> tuple[str, ...]:
    """Return only database-key Name fields from active BC features.

    2d_bc link/ignore/code geometries never reference BC Name values.
    For HQ, a positive b value generates the curve internally.
    """
    if re.match(r"^1d_bc_", layer, re.IGNORECASE):
        return _one_d_bc_identifiers(rows, layer)
    names: set[str] = set()
    two_d_bc = bool(re.match(r"^2d_bc_", layer, re.IGNORECASE))
    source_types = {"HS", "HT", "HQ", "QT", "RF", "SD", "SH", "ST", "VG", "WT", "GT"}
    for attrs in rows:
        if two_d_bc:
            bc_type = str(attrs[0] or "").strip().upper()
            if not bc_type:
                message = f"Blank 2d_bc Type requires external Blank BC Type context: {layer}"
                raise ValueError(message)
            if bc_type not in source_types:
                # Geometries used as links, codes or ignored elements do not
                # name database rows. Unknown kinds are unresolved.
                if bc_type not in {"HX", "SX", "CN", "CD", "IG", "ZP", "2D", "SC"}:
                    message = f"Unrecognised 2d_bc Type {bc_type!r}: {layer}"
                    raise ValueError(message)
                continue
            if bc_type == "HQ":
                if len(attrs) < 3:
                    message = f"Cannot determine automatic HQ curve selection: {layer}"
                    raise ValueError(message)
                slope = attrs[2]
                if slope not in (None, ""):
                    try:
                        if float(str(slope)) > 0:
                            continue
                    except ValueError as exc:
                        message = f"Invalid HQ b slope in {layer}: {slope!r}"
                        raise ValueError(message) from exc
            value = attrs[1]
        else:
            value = attrs[0]
        if not isinstance(value, str) or not value.strip() or "<<" in value or ">>" in value:
            message = f"Missing or unexpanded BC Name in {layer}: {value!r}"
            raise ValueError(message)
        names.add(value.strip())
    return tuple(sorted(names, key=str.casefold))


def _attribute_file_paths(value: str, *, network_m: bool, parent: Path) -> tuple[Path, ...]:
    """Convert candidate TUFLOW attribute values into file references."""
    raw = value.strip()
    if not raw:
        return ()
    if "<<" in raw or ">>" in raw:
        message = "Unexpanded variable or ambiguous GIS attribute reference"
        raise ValueError(message)
    if "|" in raw:
        operation, reference = (part.strip() for part in raw.split("|", maxsplit=1))
        values = (operation, reference) if network_m else (reference,)
    else:
        values = (raw,)
    paths: list[Path] = []
    for item in values:
        if not item:
            message = "Empty GIS attribute file reference"
            raise ValueError(message)
        # TUFLOW interprets an initial slash as relative to the source
        # layer's directory; retain absolute Windows drives/UNC shares.
        windows_absolute = bool(re.match(r"^[A-Za-z]:[\\/]", item) or item.startswith("\\\\"))
        normal = item.replace("\\", "/")
        if normal.startswith("/") and not windows_absolute:
            normal = "." + normal
        candidate = Path(item if windows_absolute else normal)
        if not candidate.is_absolute() and not windows_absolute:
            candidate = parent / candidate
        if windows_absolute and os.name != "nt":
            message = "Windows absolute attribute reference requires Windows inspection"
            raise ValueError(message)
        paths.append(candidate.absolute())
    return tuple(paths)


def _scan_file_reference_rows(
    rows: Iterable[Sequence[object]],
    *,
    layer: str,
    geometry_type: str,
    parent: Path,
) -> tuple[tuple[Path, ...], tuple[str, ...]]:
    """Interpret selected attributes identically for Shapefiles and GeoPackages.

    Provider readers own field positioning, file opening and geometry metadata.
    This function alone owns TUFLOW channel-type and ignore-flag semantics.
    """
    network = bool(re.match(r"^1d_nwk[eb]?_", layer, flags=re.IGNORECASE))
    pit = bool(re.match(r"^1d_pit_", layer, flags=re.IGNORECASE))
    if network and geometry_type.casefold() not in {"linestring", "multilinestring"}:
        if geometry_type.casefold() != "geometry":
            return (), ()  # Known non-line geometries cannot contain line channels.
        message = "Mixed or unknown network geometry requires feature-level inspection"
        raise ValueError(message)

    sources: set[Path] = set()
    database_identifiers: set[str] = set()
    for row in rows:
        value = row[-1]
        if network and isinstance(row[1], str) and row[1].strip().casefold() in {"y", "t"}:
            continue
        kind = row[0].strip().upper() if (network or pit) and isinstance(row[0], str) else ""
        if value is None or value == "":
            if (network and kind in {"M", "Q", "QO", "P"}) or (pit and kind in {"Q", "VPI", "I"}):
                message = f"Required inlet matrix or curve identifier is blank in {layer}"
                raise ValueError(message)
            continue
        if not isinstance(value, str):
            message = f"Non-text GIS file-reference attribute in {layer}"
            raise TypeError(message)
        if network:
            if kind in {"Q", "P"}:
                database_identifiers.add(value.strip())
                continue
            if kind in {"M", "QO"}:
                # Reuse the parser's exact M/QO/Ignore file-versus-curve rule,
                # instead of independently interpreting Inlet_Type pipes.
                attributes = [None] * 11
                attributes[1], attributes[2], attributes[10] = (
                    kind, row[1], value
                )
                source_values = network_attribute_file_sources(attributes)
                if not source_values:
                    raise ValueError(
                        f"Required {kind} file reference absent in {layer}"
                    )
                for file_value in source_values:
                    sources.update(
                        _attribute_file_paths(
                            file_value, network_m=False, parent=parent
                        )
                    )
                continue
            # All other channel types name operational rules or nonfile IDs.
            continue
        elif pit:
            if kind in {"Q", "VPI", "I"}:
                database_identifiers.add(value.strip())
            # Other pit types do not use Inlet_Type to reference a file.
            continue
        sources.update(_attribute_file_paths(value, network_m=network, parent=parent))
    return tuple(sorted(sources)), tuple(sorted(database_identifiers))


def _attribute_column_indexes(layer: str, field_count: int) -> tuple[int, ...]:
    """Select positional TUFLOW fields required to inspect input dependencies.

    The schema decision is shared by the GIS attribute readers and the
    GeoPackage SQL projection, avoiding duplicate channel/BC field rules.
    """
    bc_index = _bc_name_field_index(layer)
    if bc_index is not None:
        if re.match(r"^1d_bc_", layer, re.IGNORECASE):
            if field_count <= bc_index:
                raise ValueError(f"Missing required 1d_bc Type/Flags/Name columns in {layer}")
            return (0, 1, 2)
        if field_count <= bc_index or (bc_index == 2 and field_count <= 7):
            raise ValueError(f"Missing required BC Name/Type/b columns in {layer}")
        return (0, 2, 7) if bc_index == 2 else (bc_index,)

    index = _file_field_index(layer)
    if index is None:
        raise ValueError(f"Unsupported GIS attribute-linked layer type: {layer}")
    network = bool(re.match(r"^1d_nwk[eb]?_", layer, re.IGNORECASE))
    pit = bool(re.match(r"^1d_pit_", layer, re.IGNORECASE))
    if field_count <= index or ((network or pit) and field_count <= 2):
        raise ValueError(f"Required file-reference attribute index {index} absent from {layer}")
    if network:
        return (1, 2, index)
    if pit:
        return (1, index)
    return (index,)


def _interpret_attribute_rows(
    rows: Iterable[Sequence[object]],
    *,
    layer: str,
    geometry_type: str,
    parent: Path,
) -> tuple[tuple[Path, ...], tuple[str, ...], tuple[str, ...]]:
    """Interpret the selected TUFLOW attributes regardless of GIS format."""
    if _bc_name_field_index(layer) is not None:
        return (), (), _bc_identifiers_from_rows(rows, layer)
    sources, identifiers = _scan_file_reference_rows(
        rows, layer=layer, geometry_type=geometry_type, parent=parent
    )
    return sources, identifiers, ()


def _scan_attribute_rows(
    rows: Iterable[Sequence[object]],
    *,
    field_count: int,
    layer: str,
    geometry_type: str,
    parent: Path,
) -> tuple[tuple[Path, ...], tuple[str, ...], tuple[str, ...]]:
    """Apply shared field selection to PyTuflow's existing GIS readers."""
    columns = _attribute_column_indexes(layer, field_count)
    selected = (tuple(row[i] for i in columns) for row in rows)
    return _interpret_attribute_rows(
        selected, layer=layer, geometry_type=geometry_type, parent=parent
    )


def _scan_shapefile(
    path: Path,
) -> tuple[tuple[Path, ...], tuple[str, ...], tuple[str, ...]]:
    """Read the DBF with PyTUFLOW's existing dbfread dependency.

    Keep exact SHP/DBF/SHX stem spelling and consistent extension-case style.
    Do not perform an implicit case-insensitive companion search on Linux.
    """
    dbf, shx = _shapefile_companions(path)
    if not dbf.is_file() or not shx.is_file():
        raise ValueError("Shapefile requires matching DBF and SHX companions")
    with path.open("rb") as stream:
        header = stream.read(100)
    if len(header) != 100:
        raise ValueError("Truncated Shapefile header")
    shape_type = int.from_bytes(header[32:36], "little")
    geometry_type = (
        "LINESTRING" if shape_type in (3, 13, 23)
        else "GEOMETRY" if shape_type == 0
        else "OTHER"
    )
    database = DBF(str(dbf), load=False, char_decode_errors="strict")
    return _scan_attribute_rows(
        (tuple(record.values()) for record in database),
        field_count=len(database.field_names),
        layer=path.stem, geometry_type=geometry_type,
        parent=path.parent,
    )


def _scan_mif_mid(
    path: Path,
) -> tuple[tuple[Path, ...], tuple[str, ...], tuple[str, ...]]:
    """Use PyTUFLOW's existing MIF/MID/GDAL attribute reader.

    No duplicate MIF syntax parser or custom CSV dialect is introduced.
    For network layers, the existing GIS provider supplies geometry types;
    if it cannot establish line geometry, reject the source instead of
    assuming channel rows apply to unsupported geometry.
    """
    layer = path.stem
    geometry_type = "OTHER"
    if re.match(r"^1d_nwk[eb]?_", layer, re.IGNORECASE):
        with TuflowPath(path).open_gis() as source:
            geometries = tuple(source.geometry_types())
        if not geometries:
            raise ValueError("Cannot determine network geometry of MIF/MID layer")
        line_geometries = tuple(
            name.casefold() in ("linestring", "multilinestring")
            for name in geometries
        )
        if all(line_geometries):
            geometry_type = "LINESTRING"
        elif any(line_geometries):
            raise ValueError(
                "Mixed network geometry requires feature-level inspection"
            )
        else:
            geometry_type = "OTHER"
    with GISAttributes(TuflowPath(path)) as reader:
        records = iter(reader)
        try:
            first = tuple(next(records).values())
        except StopIteration as exc:
            field_count = len(getattr(reader, "_col_names", ()))
            if not field_count:
                raise ValueError("Empty MIF/MID attribute schema cannot be certified") from exc
            values: Iterable[tuple[object, ...]] = ()
        else:
            from itertools import chain

            field_count = len(first)
            values = chain((first,), (tuple(record.values()) for record in records))
        return _scan_attribute_rows(
            values,
            field_count=field_count,
            layer=layer,
            geometry_type=geometry_type,
            parent=path.parent,
        )


def _scan_layer(
    connection: sqlite3.Connection, layer: str, geometry_type: str, path: Path
) -> tuple[tuple[Path, ...], tuple[str, ...], tuple[str, ...]]:
    """Project only known GeoPackage fields through the common row interpreter.

    The caller supplies an existing pinned, read-only SQLite connection.
    Geometry blobs and unrelated attributes are never selected.
    """
    if re.match(r"^1d_nwk[eb]?_", layer, re.IGNORECASE):
        if geometry_type.casefold() not in {"linestring", "multilinestring"}:
            if geometry_type.casefold() != "geometry":
                return (), (), ()
            raise ValueError("Mixed or unknown network geometry requires feature-level inspection")

    quoted = _quote_identifier(layer)
    columns = [
        (name, pk)
        for _, name, _, _, _, pk in connection.execute(f"PRAGMA table_info({quoted})")
    ]
    geom_names = {
        str(name).casefold()
        for (name,) in connection.execute(
            "SELECT column_name FROM gpkg_geometry_columns WHERE lower(table_name) = lower(?)",
            (layer,),
        )
    }
    if not geom_names:
        raise ValueError(f"GeoPackage layer geometry column is unavailable: {layer}")
    attrs = [
        name for name, pk in columns
        if not pk and str(name).casefold() not in geom_names
    ]
    indexes = _attribute_column_indexes(layer, len(attrs))
    fields = ", ".join(_quote_identifier(str(attrs[i])) for i in indexes)
    return _interpret_attribute_rows(
        connection.execute(f"SELECT {fields} FROM {quoted}"),
        layer=layer,
        geometry_type=geometry_type,
        parent=path.parent,
    )


def _matches_layer(candidate: str, selector: str, implicit: bool) -> bool:
    """Match implicit literal names or explicitly selected TUFLOW layers."""
    if implicit:
        return candidate.casefold() == selector.casefold()
    return (
        selector.casefold() == "all"
        or fnmatch.fnmatchcase(candidate.casefold(), selector.casefold())
    )


def _inspection_from_layers(
    layer_results: Iterable[
        tuple[str, tuple[tuple[Path, ...], tuple[str, ...], tuple[str, ...]]]
    ],
) -> AttributeInspection:
    """Combine selected attribute sources and distinguish network/BC roles."""
    sources: set[Path] = set()
    network: set[str] = set()
    pits: set[str] = set()
    bc: set[str] = set()
    has_bc = False
    for layer, (files, identifiers, bc_names) in layer_results:
        sources.update(files)
        bc.update(bc_names)
        if re.match(r"^1d_nwk[eb]?_", layer, re.IGNORECASE):
            network.update(identifiers)
        elif re.match(r"^1d_pit_", layer, re.IGNORECASE):
            pits.update(identifiers)
        has_bc |= _bc_name_field_index(layer) is not None
    return AttributeInspection(
        "present",
        tuple(sorted(sources)),
        tuple(sorted(network | pits)),
        network_identifiers=tuple(sorted(network)),
        pit_identifiers=tuple(sorted(pits)),
        bc_identifiers=tuple(sorted(bc, key=str.casefold)),
        bc_layer_selected=has_bc,
    )


def _inspect_single_file(
    path: Path,
    selectors: set[tuple[str, bool]],
    results: dict[tuple[Path, str, bool], AttributeInspection],
    *,
    scan: Callable[[Path], tuple[tuple[Path, ...], tuple[str, ...], tuple[str, ...]]],
) -> int:
    """Inspect a Shapefile or MapInfo dataset only once for its selectors."""
    selected = {
        (selector, implicit)
        for selector, implicit in selectors
        if _matches_layer(path.stem, selector, implicit)
    }
    for selector, implicit in selectors - selected:
        results[(path, selector, implicit)] = AttributeInspection(
            "unresolved", detail=f"GIS layer does not match selector {selector!r}"
        )
    if not selected:
        return 0
    try:
        inspection = _inspection_from_layers(((path.stem, scan(path)),))
    except Exception as exc:  # noqa: BLE001 - a provider failure cannot certify a GIS input
        inspection = AttributeInspection(
            "unresolved", detail=f"Cannot inspect GIS attributes: {exc}"
        )
    for selector, implicit in selected:
        results[(path, selector, implicit)] = inspection
    return 1


def inspect_gis_attribute_sources(
    requests: Collection[tuple[Path, str, bool]],
) -> tuple[dict[tuple[Path, str, bool], AttributeInspection], int]:
    """Inspect attribute-linked sources once per distinct GIS dataset.

    Implicit layers are literal; explicit selectors permit wildcards and
    the TUFLOW all-layer keyword. GeoPackages use one pinned, read-only
    SQLite connection per file. Uncertain results cannot be certified.
    """
    grouped: dict[Path, set[tuple[str, bool]]] = defaultdict(set)
    for path, layer, implicit in requests:
        grouped[path].add((layer, implicit))

    results: dict[tuple[Path, str, bool], AttributeInspection] = {}
    databases = 0
    for path, selectors in grouped.items():
        suffix = path.suffix.casefold()
        if suffix == ".shp":
            databases += _inspect_single_file(
                path, selectors, results, scan=_scan_shapefile
            )
            continue
        if suffix in (".mif", ".mid"):
            databases += _inspect_single_file(
                path, selectors, results, scan=_scan_mif_mid
            )
            continue
        if suffix != ".gpkg":
            for selector, implicit in selectors:
                results[(path, selector, implicit)] = AttributeInspection(
                    "unresolved",
                    detail=f"GIS attribute reading does not support {path.suffix or 'unknown'} sources",
                )
            continue

        try:
            with readonly_gpkg(path) as database:
                databases += 1
                available = {
                    str(name): str(geometry)
                    for name, geometry in database.execute(
                        "SELECT table_name, geometry_type_name FROM gpkg_geometry_columns"
                    )
                }
                if not available:
                    raise ValueError("No vector layer metadata in GeoPackage")
                cache: dict[
                    str, tuple[tuple[Path, ...], tuple[str, ...], tuple[str, ...]]
                ] = {}
                for selector, implicit in selectors:
                    key = (path, selector, implicit)
                    chosen = [
                        name for name in available
                        if _matches_layer(name, selector, implicit)
                    ]
                    if not chosen:
                        results[key] = AttributeInspection(
                            "unresolved",
                            detail=f"No GIS attribute layers matched {selector!r}",
                        )
                        continue
                    try:
                        supported = [
                            name for name in chosen
                            if _file_field_index(name) is not None
                            or _bc_name_field_index(name) is not None
                        ]
                        for layer in supported:
                            if layer not in cache:
                                cache[layer] = _scan_layer(
                                    database, layer, available[layer], path
                                )
                        results[key] = _inspection_from_layers(
                            (layer, cache[layer]) for layer in supported
                        )
                    except (
                        OSError, ValueError, TypeError, RuntimeError, sqlite3.DatabaseError
                    ) as exc:
                        results[key] = AttributeInspection(
                            "unresolved", detail=f"Cannot inspect GIS attributes: {exc}"
                        )
        except (
            OSError, ValueError, TypeError, RuntimeError, sqlite3.DatabaseError
        ) as exc:
            for selector, implicit in selectors:
                results[(path, selector, implicit)] = AttributeInspection(
                    "unresolved", detail=f"Cannot inspect GIS attributes: {exc}"
                )
    return results, databases
