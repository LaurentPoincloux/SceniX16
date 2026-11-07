"""Chiffres affichés autour du dashboard (barre supérieure, barre d'état).

Lit la base en lecture seule (repository) et applique les règles du domaine.
L'instant courant est fourni par l'appelant : aucune lecture d'horloge ici.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from scenix16.domain.dashboard import DEFAULT_SORT, DashboardView, SortOrder, build_dashboard
from scenix16.storage.repository import count_tracks, read_concert_summaries
from scenix16.storage.userdata import database_path


@dataclass(frozen=True)
class DashboardSummary:
    view: DashboardView | None
    track_count: int
    setlist_count: int

    @property
    def upcoming(self) -> int:
        return self.view.upcoming_count if self.view else 0

    @property
    def past(self) -> int:
        return self.view.counters.past if self.view else 0


EMPTY = DashboardSummary(None, 0, 0)


def load_summary(userdata: Path | None, now: datetime,
                 order: SortOrder = DEFAULT_SORT) -> DashboardSummary:
    """Résumé du dashboard. Base absente ou illisible : tous les compteurs à zéro."""
    if userdata is None:
        return EMPTY
    path = database_path(userdata)
    if not path.is_file():
        return EMPTY
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return EMPTY
    try:
        concerts = read_concert_summaries(connection)
        tracks = count_tracks(connection)
    except sqlite3.Error:
        return EMPTY
    finally:
        connection.close()
    return DashboardSummary(build_dashboard(concerts, now, order), tracks, len(concerts))


def plural(count: int, singular: str, plural_form: str) -> str:
    """Accord français : 0 et 1 au singulier."""
    return f"{count} {singular if count <= 1 else plural_form}"


def concerts_label(summary: DashboardSummary) -> str:
    """Repère de la barre supérieure : « N à venir · M passés »."""
    return f"{summary.upcoming} à venir · {plural(summary.past, 'passé', 'passés')}"


def date_label(now: datetime) -> str:
    """Date calendaire du jour (même entre minuit et 6 h)."""
    return now.strftime("%d/%m/%Y")


def status_parts(summary: DashboardSummary) -> list[str]:
    """Barre d'état (section 07) : « SceniX16 · N titres au catalogue · M setlists »."""
    return [
        "SceniX16",
        f"{plural(summary.track_count, 'titre', 'titres')} au catalogue",
        plural(summary.setlist_count, "setlist", "setlists"),
    ]
