"""Schéma SQLite initial."""

import sqlite3

import pytest

from scenix16.storage import database as db


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "scenix16.db")
    yield connection
    connection.close()


def test_schema_created_with_version(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"meta", "tracks", "setlists", "setlist_entries",
            "setlist_contacts", "setlist_schedule"} <= tables
    assert conn.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
    assert db.is_empty(conn)


def test_reopen_keeps_data(tmp_path):
    path = tmp_path / "scenix16.db"
    with db.connect(path) as c:
        c.execute("INSERT INTO tracks(position, title) VALUES (1, 'A')")
    c.close()
    c2 = db.connect(path)
    assert c2.execute("SELECT title FROM tracks").fetchone()[0] == "A"
    assert not db.is_empty(c2)
    c2.close()


def test_name_is_required(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO setlists(name) VALUES ('')")


def test_date_optional_and_iso(conn):
    conn.execute("INSERT INTO setlists(name) VALUES ('Nouvelle setlist')")  # sans date (D5)
    conn.execute("INSERT INTO setlists(name, concert_date) VALUES ('X', '2026-06-21')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO setlists(name, concert_date) VALUES ('Y', '21/06/26')")


def test_status_values(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO setlists(name, status) VALUES ('X', 'past')")


def test_entries_allow_repetition_and_keep_order(conn):
    conn.execute("INSERT INTO tracks(id, position, title) VALUES (1, 1, 'A'), (2, 2, 'B')")
    conn.execute("INSERT INTO setlists(id, name) VALUES (1, 'S')")
    conn.executemany("INSERT INTO setlist_entries(setlist_id, position, track_id) VALUES (1, ?, ?)",
                     [(1, 1), (2, 2), (3, 1)])
    rows = conn.execute("SELECT track_id FROM setlist_entries WHERE setlist_id=1 ORDER BY position").fetchall()
    assert [r[0] for r in rows] == [1, 2, 1]


def test_foreign_keys_enforced(conn):
    conn.execute("INSERT INTO setlists(id, name) VALUES (1, 'S')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO setlist_entries(setlist_id, position, track_id) VALUES (1, 1, 99)")


def test_text_kept_verbatim(conn):
    title = "ENJOY THE SILENCE \n(BOOKHOUSE BOYS)"
    conn.execute("INSERT INTO tracks(position, title) VALUES (1, ?)", (title,))
    assert conn.execute("SELECT title FROM tracks").fetchone()[0] == title
