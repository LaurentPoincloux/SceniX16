"""Lecture des données dans SQLite (sans règle métier).

Le repository convertit les lignes de la base en modèles du domaine ; les
règles (états, classement, sélection) sont appliquées par scenix16.domain.
"""

from __future__ import annotations

import sqlite3
from datetime import date

from scenix16.domain.models import ConcertSummary, SetlistStatus


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
