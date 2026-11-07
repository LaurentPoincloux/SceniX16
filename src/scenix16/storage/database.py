"""Base SQLite de SceniX16 : schéma initial (version 1).

Correspondance avec le Design Book :
- tracks : bibliothèque TRACKS (titre, KEY, MK, VIRUS|TI, statut ON/OFF) ;
- setlists : un concert et ses informations (D16) ; date absente = « DATE À
  DÉFINIR » (D5) ; statut maintenu / annulé (D4, D20) ; « passé » n'est pas
  stocké, il se calcule à partir de la date (D2, D10) ;
- setlist_entries : morceaux d'une setlist dans leur ordre, répétitions
  autorisées (D13) ;
- setlist_contacts / setlist_schedule : listes 0..n de D16.

Les valeurs importées sont conservées telles quelles : aucune contrainte ne
modifie ou normalise le texte (espaces, retours à la ligne).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE tracks (
    id            INTEGER PRIMARY KEY,
    position      INTEGER NOT NULL,          -- ordre dans la bibliothèque
    title         TEXT    NOT NULL,
    key           TEXT,                      -- tonalité (KEY)
    mk            TEXT,                      -- patch MK
    virus         TEXT,                      -- patch VIRUS|TI
    virus_status  TEXT,                      -- ON / OFF, tel que saisi
    source_cell   TEXT,                      -- ex. TRACKS!A2 (traçabilité de l'import)
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
);

CREATE TABLE setlists (
    id            INTEGER PRIMARY KEY,
    name          TEXT    NOT NULL CHECK (length(name) > 0),   -- seul champ obligatoire (D16)
    concert_date  TEXT    CHECK (concert_date IS NULL OR concert_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    venue         TEXT,                      -- salle / lieu
    address       TEXT,
    organizer     TEXT,
    notes         TEXT,
    visual_file   TEXT,                      -- copie locale dans UserData/media (Q7)
    status        TEXT    NOT NULL DEFAULT 'maintained' CHECK (status IN ('maintained', 'cancelled')),
    source_sheet  TEXT,                      -- feuille d'origine pour un import
    created_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
    updated_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now'))
);

CREATE TABLE setlist_entries (
    setlist_id    INTEGER NOT NULL REFERENCES setlists(id) ON DELETE CASCADE,
    position      INTEGER NOT NULL CHECK (position >= 1),
    track_id      INTEGER NOT NULL REFERENCES tracks(id) ON DELETE RESTRICT,
    source_cell   TEXT,
    PRIMARY KEY (setlist_id, position)
);

CREATE TABLE setlist_contacts (
    id            INTEGER PRIMARY KEY,
    setlist_id    INTEGER NOT NULL REFERENCES setlists(id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    name          TEXT,
    role          TEXT,
    phone         TEXT,
    email         TEXT
);

CREATE TABLE setlist_schedule (
    id            INTEGER PRIMARY KEY,
    setlist_id    INTEGER NOT NULL REFERENCES setlists(id) ON DELETE CASCADE,
    position      INTEGER NOT NULL,
    label         TEXT,
    time          TEXT CHECK (time IS NULL OR time GLOB '[0-2][0-9]:[0-5][0-9]')
);

CREATE INDEX idx_entries_track ON setlist_entries(track_id);
CREATE INDEX idx_setlists_date ON setlists(concert_date);
"""


def connect(path: Path) -> sqlite3.Connection:
    """Ouvre (ou crée) la base et applique le schéma s'il est absent."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        with connection:
            connection.executescript(SCHEMA)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    elif version != SCHEMA_VERSION:
        connection.close()
        raise RuntimeError(
            f"Version de base inattendue : {version} (attendu {SCHEMA_VERSION})"
        )
    return connection


def is_empty(connection: sqlite3.Connection) -> bool:
    """Vrai si la base ne contient encore ni morceau ni setlist."""
    for table in ("tracks", "setlists"):
        if connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
            return False
    return True
