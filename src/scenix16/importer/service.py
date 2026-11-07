"""Import du classeur dans la base SQLite, avec rapport.

L'import se fait dans une base vide uniquement : il ne remplace ni ne
complète jamais des données existantes. Tout est écrit dans une seule
transaction : en cas d'erreur, la base reste inchangée.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from scenix16.importer.excel import WorkbookData, read_workbook
from scenix16.importer.report import build_report
from scenix16.storage import database


class ImportRefused(RuntimeError):
    """L'import est refusé (base non vide, emplacement non accessible…)."""


@dataclass
class ImportResult:
    data: WorkbookData
    tracks: int
    setlists: int
    entries: int
    report_path: Path | None


def import_into(connection: sqlite3.Connection, data: WorkbookData) -> tuple[int, int, int]:
    if not database.is_empty(connection):
        raise ImportRefused(
            "La base contient déjà des morceaux ou des setlists : l'import est refusé "
            "pour ne rien écraser."
        )
    with connection:  # transaction unique
        track_ids: dict[str, int] = {}
        for t in data.tracks:
            cur = connection.execute(
                "INSERT INTO tracks(position, title, key, mk, virus, virus_status, source_cell) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (t.position, t.title, t.key, t.mk, t.virus, t.virus_status, t.source_cell),
            )
            track_ids.setdefault(t.title, cur.lastrowid)
        fold_ids = {}
        for t in data.tracks:
            fold_ids.setdefault(t.title.casefold(), track_ids[t.title])

        entries = 0
        for s in data.setlists:
            cur = connection.execute(
                "INSERT INTO setlists(name, concert_date, venue, status, source_sheet) "
                "VALUES (?, ?, ?, 'maintained', ?)",
                (s.name, s.concert_date.isoformat() if s.concert_date else None, s.venue, s.sheet),
            )
            setlist_id = cur.lastrowid
            for e in s.entries:
                track_id = track_ids.get(e.title) or fold_ids[e.title.casefold()]
                connection.execute(
                    "INSERT INTO setlist_entries(setlist_id, position, track_id, source_cell) "
                    "VALUES (?, ?, ?, ?)",
                    (setlist_id, e.position, track_id, e.source_cell),
                )
                entries += 1

        meta = {
            "import_source": data.source_path.name,
            "import_sha256": data.sha256,
            "import_at": datetime.now().isoformat(timespec="seconds"),
        }
        connection.executemany("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", meta.items())
    return len(data.tracks), len(data.setlists), entries


def import_into_userdata(xlsx: Path, userdata: Path) -> ImportResult:
    """Point d'entrée commun (ligne de commande et future interface).

    L'appelant doit détenir le verrou d'instance de `userdata` : l'application
    le prend au démarrage, la ligne de commande le prend elle-même.
    """
    from scenix16.storage.userdata import database_path

    return import_workbook(xlsx, database_path(userdata), userdata / "logs")


def import_workbook(xlsx: Path, db_path: Path, report_dir: Path | None = None) -> ImportResult:
    data = read_workbook(xlsx)
    connection = database.connect(db_path)
    try:
        tracks, setlists, entries = import_into(connection, data)
    finally:
        connection.close()
    report_path = None
    if report_dir is not None:
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_path = report_dir / f"import-{stamp}.md"
        report_path.write_text(build_report(data, tracks, setlists, entries), encoding="utf-8")
    return ImportResult(data, tracks, setlists, entries, report_path)
