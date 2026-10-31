"""Opt-in secondary source discovery using cached TUFLOW database rows."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np

from .file_reference import FileReference, _cached_path_matches, make_file_reference
from .parsers.command import Command

if TYPE_CHECKING:
    from pandas import DataFrame

    from .context import Context
    from .inp.db import DatabaseInput
    from .settings import TCFConfig


class DeferredDatabaseResolutionError(ValueError):
    """Database sources cannot be completely inspected by the deferred API."""


def _cached_database_path_key(path: Path) -> str:
    """Compare cached paths lexically using the host filesystem's case rules.

    Do not resolve or stat paths: mapped drives and UNC aliases must retain
    their original spelling, while POSIX case distinctions must be preserved.
    """
    return os.path.normcase(os.path.normpath(str(path)))


def _expanded(value: object, context: Context, *, kind: str, row: object) -> str:
    """Expand model variables before classifying a table cell."""
    if value is None:
        return ''
    raw = str(value).strip()
    if raw.casefold() == 'nan' or (kind != 'soils' and raw.casefold() == 'none'):
        return ''
    translated = str(context.translate(raw)).strip()
    if translated and not context.is_resolved(translated):
        raise DeferredDatabaseResolutionError(
            f'Unresolved {kind} database row {row!s}: {raw}'
        )
    return translated


def _inline_material(value: str, row: object) -> bool:
    """Validate depth/n pairs the same way eager MatDBEntry.is_list identifies.

    Inline comma-delimited values are numeric depth and Manning n pairs,
    not filenames. Malformed comma lists must not silently pass.
    """
    if ',' not in value:
        return False
    tokens = [part.strip().strip('"').strip("'") for part in value.split(',')]
    try:
        numbers = [float(token) for token in tokens]
    except ValueError as exc:
        raise DeferredDatabaseResolutionError(
            f'Invalid inline Manning/depth list at material {row}: {value}'
        ) from exc
    if len(numbers) < 2 or len(numbers) % 2:
        raise DeferredDatabaseResolutionError(
            f'Inline Manning/depth list needs complete depth/n pairs at material {row}: {value}'
        )
    return True


def _validate_soil_rows(frame: DataFrame, context: Context) -> None:
    """Validate supported inline soil methods without generating fictitious files.

    SoilDatabase.value() currently implements NONE, ILCL, GA, HO, CO and
    SCS. These methods contain parameters or USDA classifications, not
    secondary filenames; unknown methods fail closed.
    """
    required = {
        'NONE': (),
        'ILCL': (1, 2),
        'GA': (1,),
        'HO': (1, 2, 3, 4),
        'CO': (1, 2),
        'SCS': (1, 2),
    }
    for key, record in frame.iterrows():
        fields = [_expanded(item, context, kind='soils', row=key) for item in record.tolist()]
        if not fields or not fields[0]:
            raise DeferredDatabaseResolutionError(f'Missing soil method at row {key}')
        method = fields[0].upper()
        if method not in required:
            raise DeferredDatabaseResolutionError(f'Unsupported soil method {method} at row {key}')
        for index in required[method]:
            if len(fields) <= index or not fields[index]:
                raise DeferredDatabaseResolutionError(
                    f'Missing {method} parameter {index} at soil row {key}'
                )
            if not (method == 'GA' and index == 1):
                try:
                    float(fields[index])
                except ValueError as exc:
                    raise DeferredDatabaseResolutionError(
                        f'Invalid {method} parameter {index} at soil row {key}: {fields[index]}'
                    ) from exc
        # For GA a numeric suction requires numeric hydraulic conductivity
        # and porosity; a USDA soil-type string is a known inline class.
        if method == 'GA':
            try:
                float(fields[1])
                numeric_ga = True
            except ValueError:
                numeric_ga = False
            if numeric_ga:
                for index in (2, 3):
                    if len(fields) <= index:
                        raise DeferredDatabaseResolutionError(
                            f'Missing GA parameter {index} at soil row {key}'
                        )
                    try:
                        float(fields[index])
                    except ValueError as exc:
                        raise DeferredDatabaseResolutionError(
                            f'Invalid GA parameter {index} at soil row {key}: {fields[index]}'
                        ) from exc


def _ad_global_references(
    frame: DataFrame, context: Context, config: TCFConfig, database_path: Path,
) -> tuple[FileReference, ...]:
    """Project spatial AD constituent fields from an already-loaded CSV.

    The TUFLOW AD global database permits a numeric value or GIS file for
    Initial Condition and Minimum Dispersion. Blank initial values mean zero;
    blank minimum dispersion is invalid. GIS validation is a later stage.
    """
    columns = {str(column).strip().casefold(): column for column in frame.columns}
    required = ('initial condition', 'minimum dispersion')
    if any(name not in columns for name in required):
        raise DeferredDatabaseResolutionError(
            'AD Global Database is missing Initial Condition or Minimum Dispersion'
        )
    result: list[FileReference] = []
    for key, row in frame.iterrows():
        for field in required:
            value = _expanded(row[columns[field]], context, kind='ad_global', row=key)
            if not value:
                if field == 'minimum dispersion':
                    raise DeferredDatabaseResolutionError(
                        f'AD constituent {key} requires Minimum Dispersion'
                    )
                continue
            try:
                float(value)
            except ValueError:
                pass
            else:
                continue
            command = Command(f'Read GIS == {value}', config, parent=database_path)
            found = tuple(
                replace(
                    make_file_reference(part),
                    origin=f'ad_global database row {key} / {field}',
                    database_kind=None,
                )
                for part in command.parts() if part.is_value_a_file()
            )
            if len(found) != 1:
                raise DeferredDatabaseResolutionError(
                    f'Invalid AD {field} GIS source at constituent {key}: {value}'
                )
            result.extend(found)
    return tuple(result)


def database_source_references(
    build_input: DatabaseInput, context: Context, kind: str | None, config: TCFConfig,
    *, source_base: Path | None = None, primary_path: Path | None = None,
) -> tuple[FileReference, ...]:
    """Describe context-specific secondary sources with no additional file I/O.

    The build-state already contains database rows from initial TCF parsing.
    BC databases use the Source column; rainfall indexes supply grid paths;
    materials and soils follow the inline/source classifications supported
    by eager processing.
    """
    if kind not in ('bc', 'ad_bc', 'ad_global', 'pit_inlet', 'depth_discharge', 'cross_section', 'materials', 'soils', 'rainfall'):
        raise DeferredDatabaseResolutionError(
            f'Unsupported deferred database schema: {kind!r}'
        )
    databases = tuple(build_input.cf)
    loaded_paths = tuple(getattr(build_input, '_database_loaded_paths', ()))
    if primary_path is not None and loaded_paths:
        if len(loaded_paths) != len(databases):
            raise DeferredDatabaseResolutionError(f'Incomplete cached {kind} database path index')
        # Match the paths captured during initial loading, not physical fpath:
        # resolve() here would probe storage and could change mapped/UNC aliases.
        selected = _cached_database_path_key(primary_path)
        indices = [
            i for i, original in enumerate(loaded_paths)
            if _cached_database_path_key(original) == selected
        ]
        if not indices:
            indices = [
                i for i, original in enumerate(loaded_paths)
                if _cached_path_matches(
                    Path(original), Path(primary_path), config.case_sensitivity
                )
            ]
        # Exact spellings win. Multiple non-exact case-policy matches
        # remain ambiguous and must fail closed.
        databases = tuple(databases[i] for i in indices)
    if len(databases) != 1:
        raise DeferredDatabaseResolutionError(
            f'Expected one cached {kind} database, found {len(databases)}'
        )
    database = databases[0]
    if not getattr(database, 'loaded', False) or database.fpath is None:
        raise DeferredDatabaseResolutionError(f'{kind} database has not been loaded')
    # Flood Modeller DAT stores its cross-section units directly in the
    # primary file. There is no Source filename column to expand.
    if kind == 'cross_section' and database.driver.name() == 'dat_cross_section':
        return ()
    frame = cast("DataFrame", database.df)
    columns = list(frame.columns)
    if kind == 'soils':
        _validate_soil_rows(frame, context)
        return ()
    if kind == 'ad_global':
        return _ad_global_references(frame, context, config, Path(database.fpath))
    if kind in ('bc', 'ad_bc', 'pit_inlet', 'depth_discharge', 'cross_section'):
        column = next((col for col in columns if str(col).strip().casefold() == 'source'), None)
        if column is None:
            raise DeferredDatabaseResolutionError(f'{kind} database has no Source column')
    elif kind == 'rainfall':
        if len(columns) != 1 or str(columns[0]).strip().casefold() != 'rainfall_file':
            raise DeferredDatabaseResolutionError('Rainfall index requires one Rainfall_File column')
        column = columns[0]
    else:
        if not columns:
            raise DeferredDatabaseResolutionError('Materials database has no value column')
        column = columns[0]

    if kind == 'bc':
        # A CSV separator or comma-prefixed ! comment can survive loading as
        # an entirely missing row. It is not a boundary declaration. Retain
        # named rows and every row carrying data for the existing validation.
        empty = np.asarray(frame.index.isna(), dtype=bool) & np.asarray(
            frame.isna().all(axis=1), dtype=bool,
        )
        frame = frame.loc[~empty]

    refs: list[FileReference] = []
    for key, record in frame.iterrows():
        value = _expanded(record[column], context, kind=kind, row=key)
        if not value:
            if kind == 'bc':
                # TUFLOW BC Database allows a blank Source *only* for a
                # constant boundary with a numeric Column 2 (Value). Do not
                # invent a source filename, or silently accept an incomplete
                # constant without a value (2026.3 manual Table 8.13).
                constant_column = next(
                    (col for col in columns if str(col).strip().casefold()
                     in ('column 2', 'value', 'column 2 or value')),
                    None,
                )
                if constant_column is None:
                    raise DeferredDatabaseResolutionError(
                        f'Blank BC Source at row {key} without Column 2'
                    )
                constant = _expanded(
                    record[constant_column], context, kind=kind, row=key,
                )
                try:
                    float(constant)
                except ValueError as exc:
                    raise DeferredDatabaseResolutionError(
                        f'Blank BC Source at row {key} lacks numeric Column 2: {constant!r}'
                    ) from exc
                continue
            if kind in ('rainfall', 'ad_bc', 'pit_inlet', 'depth_discharge', 'cross_section'):
                raise DeferredDatabaseResolutionError(f'Empty {kind} source path at row {key}')
            continue
        if kind == 'materials' and _inline_material(value, key):
            continue
        try:
            float(value)
        except ValueError:
            pass
        else:
            if kind == 'rainfall':
                raise DeferredDatabaseResolutionError(f'Numeric rainfall grid path at time {key}: {value}')
            if kind in ('ad_bc', 'pit_inlet', 'depth_discharge', 'cross_section'):
                # These database types need an actual Source. A numeric
                # string is not a documented inline curve value; skipping
                # it silently loses the dependency. Fail closed rather
                # than silently omitting a potentially extensionless file.
                raise DeferredDatabaseResolutionError(
                    f'Numeric {kind} Source at row {key} cannot be classified: {value}'
                )
            # BC and materials support documented inline constants.
            continue
        fews_source = kind == 'bc' and value.split('|', 1)[0].strip().casefold() == 'fews'
        csv_columns = None
        if kind == 'bc' and Path(value).suffix.casefold() == '.csv':
            from .db.bc_dbase import BCDatabase

            csv_columns = tuple(
                _expanded(record[columns[index - 1]], context, kind=kind, row=key)
                if 0 < index <= len(columns) else ''
                for index in (BCDatabase.TIME_INDEX, BCDatabase.VALUE_INDEX)
            )
        if fews_source:
            # The BC Database FEWS form is "FEWS | filename.csv/.xml".
            # FEWS is a format selector, never a missing input file.
            fields = [item.strip() for item in value.split('|')]
            if (len(fields) != 2 or not fields[1]
                    or Path(fields[1]).suffix.casefold() not in ('.csv', '.xml')):
                raise DeferredDatabaseResolutionError(
                    f'Invalid FEWS BC Source at row {key}: {value}'
                )
            value = fields[1]
            csv_columns = () if Path(value).suffix.casefold() == '.csv' else None
        command = Command(
            f'Read File == {value}', config,
            parent=source_base if source_base is not None else Path(database.fpath),
        )
        found = tuple(
            replace(make_file_reference(part),
                    origin=f'{kind} database row {key!s}', database_kind=None,
                    requires_raster_metadata_scan=(kind == 'rainfall'),
                    csv_columns=csv_columns)
            for part in command.parts() if part.is_value_a_file()
        )
        if not found:
            raise DeferredDatabaseResolutionError(
                f'Unrecognised {kind} source in row {key!s}: {value}'
            )
        refs.extend(found)
    return tuple(refs)
