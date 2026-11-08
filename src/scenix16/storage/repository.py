"""Lecture des données dans SQLite (sans règle métier).

Le repository convertit les lignes de la base en modèles du domaine ; les
règles (états, classement, sélection) sont appliquées par scenix16.domain.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from scenix16.domain.models import (ConcertDetail, ConcertSummary, Contact, ScheduleItem, SetlistStatus,
                                    SetlistTrack)


def count_tracks(connection: sqlite3.Connection) -> int:
    """Nombre de morceaux dans la bibliothèque (TRACKS)."""
    return connection.execute("SELECT count(*) FROM tracks").fetchone()[0]


def read_concert_summaries(connection: sqlite3.Connection) -> list[ConcertSummary]:
    rows = connection.execute(
        """
        SELECT s.id, s.name, s.concert_date, s.venue, s.status,
               (SELECT count(*) FROM setlist_entries e WHERE e.setlist_id = s.id) AS track_count
        FROM setlists s
        ORDER BY s.id
        """
    ).fetchall()
    return [
        ConcertSummary(
            id=row[0],
            name=row[1],
            concert_date=date.fromisoformat(row[2]) if row[2] else None,
            venue=row[3],
            status=SetlistStatus(row[4]),
            track_count=row[5],
        )
        for row in rows
    ]


def read_concert_detail(connection: sqlite3.Connection, setlist_id: int) -> ConcertDetail | None:
    """Détail d'une setlist pour la fiche (D16), ou None si l'identifiant est inconnu.

    Lecture seule. Les morceaux sont lus dans l'ordre de la setlist, répétitions comprises
    (une entrée par position), avec les valeurs de TRACKS telles qu'elles sont stockées.
    """
    row = connection.execute(
        """
        SELECT id, name, concert_date, venue, address, organizer, notes, visual_file, status
        FROM setlists WHERE id = ?
        """, (setlist_id,)).fetchone()
    if row is None:
        return None
    tracks = connection.execute(
        """
        SELECT e.position, t.title, t.key, t.mk, t.virus, t.virus_status
        FROM setlist_entries e JOIN tracks t ON t.id = e.track_id
        WHERE e.setlist_id = ?
        ORDER BY e.position
        """, (setlist_id,)).fetchall()
    contacts = connection.execute(
        "SELECT name, role, phone, email FROM setlist_contacts WHERE setlist_id = ? ORDER BY position, id",
        (setlist_id,)).fetchall()
    schedule = connection.execute(
        "SELECT label, time FROM setlist_schedule WHERE setlist_id = ? ORDER BY position, id",
        (setlist_id,)).fetchall()
    return ConcertDetail(
        id=row[0],
        name=row[1],
        concert_date=date.fromisoformat(row[2]) if row[2] else None,
        venue=row[3],
        address=row[4],
        organizer=row[5],
        notes=row[6],
        visual_file=row[7],
        status=SetlistStatus(row[8]),
        tracks=tuple(SetlistTrack(*r) for r in tracks),
        contacts=tuple(Contact(*r) for r in contacts),
        schedule=tuple(ScheduleItem(*r) for r in schedule),
    )
