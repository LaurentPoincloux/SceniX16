"""Modèles du domaine, indépendants de l'interface et de SQLite."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class SetlistStatus(Enum):
    """Statut enregistré d'une setlist (D4, D20). « Passé » n'est jamais stocké."""

    MAINTAINED = "maintained"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ConcertSummary:
    """Ce que le dashboard doit savoir d'une setlist."""

    id: int
    name: str
    concert_date: date | None   # None = « DATE À DÉFINIR » (D5)
    venue: str | None
    status: SetlistStatus
    track_count: int
