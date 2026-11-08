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


# --- fiche du concert (D16, D69 — incrément 2.7a) -------------------------------------------------

@dataclass(frozen=True)
class SetlistTrack:
    """Un morceau de la setlist, à sa position (les répétitions sont des entrées distinctes, D13).

    Les valeurs sont celles de la bibliothèque TRACKS, telles qu'elles sont stockées.
    """

    position: int
    title: str
    key: str | None              # tonalité (KEY)
    mk: str | None               # patch MK
    virus: str | None            # patch VIRUS|TI
    virus_status: str | None     # « ON » / « OFF », tel que saisi


@dataclass(frozen=True)
class Contact:
    name: str | None
    role: str | None
    phone: str | None
    email: str | None


@dataclass(frozen=True)
class ScheduleItem:
    label: str | None
    time: str | None             # HH:MM


@dataclass(frozen=True)
class ConcertDetail:
    """Tout ce que la fiche en consultation affiche d'une setlist (D16)."""

    id: int
    name: str
    concert_date: date | None    # None = « DATE À DÉFINIR » (D5)
    venue: str | None
    address: str | None          # adresse postale (infos pratiques), pas l'adresse de touche
    organizer: str | None
    notes: str | None
    visual_file: str | None      # visuel du concert (Q7), relatif à UserData/media
    status: SetlistStatus
    tracks: tuple[SetlistTrack, ...]
    contacts: tuple[Contact, ...]
    schedule: tuple[ScheduleItem, ...]
