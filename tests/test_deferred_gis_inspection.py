"""Regression tests for optional GIS attribute-linked source inspection."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pytuflow._tmf.gis import network_attribute_file_sources
from pytuflow.validation_gis import inspect_gis_attribute_sources


def _make_gpkg(path: Path, *, layer: str, attributes: tuple[str, ...],
               geometry: str = "LINESTRING") -> None:
    """Make the minimum SQLite metadata required for read-only attribute tests."""
    columns = ", ".join(f'"{name}" TEXT' for name in attributes)
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        db.execute(
            "CREATE TABLE gpkg_geometry_columns "
            "(table_name TEXT, column_name TEXT, geometry_type_name TEXT)"
        )
        db.execute("INSERT INTO gpkg_contents VALUES (?)", (layer,))
        db.execute(
            "INSERT INTO gpkg_geometry_columns VALUES (?, 'geom', ?)",
            (layer, geometry),
        )
        db.execute(
            f'CREATE TABLE "{layer}" (fid INTEGER PRIMARY KEY, {columns}, geom BLOB)'
        )


def test_network_matrix_and_operational_matrix_are_files() -> None:
    row: list[str | None] = [None] * 11
    row[1], row[2], row[10] = "M", "", "inlet_a.csv|inlet_b.csv"
    assert network_attribute_file_sources(row) == ("inlet_a.csv", "inlet_b.csv")

    row[1], row[10] = "QO", "controller|control_matrix.csv"
    assert network_attribute_file_sources(row) == ("control_matrix.csv",)

    row[2] = "Y"
    assert network_attribute_file_sources(row) == ()

    row[2], row[10] = "", "controller"
    with pytest.raises(ValueError, match="Invalid QO"):
        network_attribute_file_sources(row)


def test_gpkg_bc_selected_names_only(tmp_path: Path) -> None:
    path = tmp_path / "boundaries.gpkg"
    attributes = ("Type", "Flags", "Name", "d", "e", "f", "g", "b")
    _make_gpkg(path, layer="2d_bc_boundaries", attributes=attributes, geometry="POLYGON")
    with sqlite3.connect(path) as db:
        db.execute(
            'INSERT INTO "2d_bc_boundaries" '
            "(Type, Flags, Name, d, e, f, g, b) VALUES "
            "('GT', '', 'ActiveBC', '', '', '', '', '0')"
        )
        db.execute(
            'INSERT INTO "2d_bc_boundaries" '
            "(Type, Flags, Name, d, e, f, g, b) VALUES "
            "('IG', '', 'UnusedBC', '', '', '', '', '0')"
        )
    request = (path, "2d_bc_boundaries", True)
    result, opened = inspect_gis_attribute_sources({request})
    assert opened == 1
    assert result[request].status == "present"
    assert result[request].bc_layer_selected
    assert result[request].bc_identifiers == ("ActiveBC",)
    assert result[request].sources == ()


def test_network_matrix_source_is_identified_without_stat(tmp_path: Path) -> None:
    path = tmp_path / "network.gpkg"
    columns = (
        "ID", "Type", "Ignore", "attr3", "attr4", "attr5", "attr6",
        "attr7", "attr8", "attr9", "Inlet_Type",
    )
    _make_gpkg(path, layer="1d_nwk_test", attributes=columns)
    with sqlite3.connect(path) as db:
        db.execute(
            'INSERT INTO "1d_nwk_test" (ID, Type, Ignore, Inlet_Type) '
            "VALUES ('C1', 'M', '', 'inlet_matrix.csv')"
        )
    request = (path, "1d_nwk_test", True)
    result, opened = inspect_gis_attribute_sources({request})
    assert opened == 1
    assert result[request].status == "present"
    assert result[request].sources == (tmp_path / "inlet_matrix.csv",)


def test_unsupported_gpkg_attribute_metadata_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "invalid.gpkg"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
    request = (path, "1d_nwk_any", False)
    result, opened = inspect_gis_attribute_sources({request})
    assert opened == 1
    assert result[request].status == "unresolved"
    assert result[request].sources == ()
