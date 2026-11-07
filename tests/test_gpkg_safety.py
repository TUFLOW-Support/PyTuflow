"""Core PyTUFLOW GeoPackage safety independent of the batch validator."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from pytuflow._tmf.gpkg_safety import (
    GeoPackageSafetyError,
    _readonly_sqlite_uri,
    check_gpkg_safety,
    read_gpkg_layer_names,
    readonly_gpkg,
)


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("file:///C:/models/grid.gpkg",
         "file:///C:/models/grid.gpkg?mode=ro&immutable=1"),
        ("file://server/share/grid.gpkg",
         "file:////server/share/grid.gpkg?mode=ro&immutable=1"),
        ("file://server/share/space%20%23%20100%25%20caf%C3%A9.gpkg",
         "file:////server/share/space%20%23%20100%25%20caf%C3%A9.gpkg"
         "?mode=ro&immutable=1"),
        ("file:///C:/models/space%20%23%20100%25%20caf%C3%A9.gpkg",
         "file:///C:/models/space%20%23%20100%25%20caf%C3%A9.gpkg"
         "?mode=ro&immutable=1"),
        ("file:///models/space%20%23%20100%25%20caf%C3%A9.gpkg",
         "file:///models/space%20%23%20100%25%20caf%C3%A9.gpkg"
         "?mode=ro&immutable=1"),
    ],
)
def test_readonly_uri_preserves_path_and_escapes(
    uri: str, expected: str,
) -> None:
    """UNC authorities become path components without changing local URIs."""
    with patch.object(Path, "as_uri", return_value=uri) as as_uri:
        assert _readonly_sqlite_uri(Path("unused.gpkg")) == expected
        as_uri.assert_called_once_with()


@pytest.mark.parametrize("name", ["plain.gpkg", "space # 100% café.gpkg"])
def test_readonly_uri_opens_escaped_file_and_rejects_writes(
    tmp_path: Path, name: str,
) -> None:
    """Escaped names select the existing database and never permit writes."""
    path = tmp_path / name
    with sqlite3.connect(path) as writer:
        writer.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        writer.execute("INSERT INTO gpkg_contents VALUES ('grid')")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with readonly_gpkg(path) as database:
        assert database.execute("SELECT table_name FROM gpkg_contents").fetchall() == [
            ("grid",),
        ]
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            database.execute("CREATE TABLE forbidden (value TEXT)")
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_readonly_core_gpkg_reader_no_auxiliary_files(tmp_path: Path) -> None:
    path = tmp_path / "readable.gpkg"
    with sqlite3.connect(path) as writer:
        writer.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
        writer.execute("INSERT INTO gpkg_contents VALUES ('grid')")
    before = path.read_bytes()

    check_gpkg_safety(path)
    with readonly_gpkg(path) as source:
        assert source.execute(
            "SELECT table_name FROM gpkg_contents"
        ).fetchone() == ("grid",)
    assert read_gpkg_layer_names(path) == (("grid",), "")

    assert path.read_bytes() == before
    assert {p.name for p in tmp_path.iterdir()} == {"readable.gpkg"}


def test_core_reader_rejects_active_rollback_journal(tmp_path: Path) -> None:
    path = tmp_path / "busy.gpkg"
    with sqlite3.connect(path) as writer:
        writer.execute("CREATE TABLE gpkg_contents (table_name TEXT)")
    editor = sqlite3.connect(path)
    try:
        editor.execute("PRAGMA journal_mode=DELETE")
        editor.execute("BEGIN IMMEDIATE")
        editor.execute("INSERT INTO gpkg_contents VALUES ('uncommitted')")
        assert path.with_name(path.name + "-journal").stat().st_size > 0
        before = path.read_bytes()
        journal = path.with_name(path.name + "-journal").read_bytes()
        with (
            pytest.raises(GeoPackageSafetyError, match="journal"),
            readonly_gpkg(path) as source,
        ):
            source.execute("SELECT table_name FROM gpkg_contents")
        assert path.read_bytes() == before
        assert path.with_name(path.name + "-journal").read_bytes() == journal
    finally:
        editor.rollback()
        editor.close()
